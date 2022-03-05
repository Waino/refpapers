import delegator  # type: ignore
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Generator, Tuple, Optional
from whoosh import index, qparser  # type: ignore
from whoosh.sorting import MultiFacet, ScoreFacet, FieldFacet   # type: ignore
from rich.progress import track

from refpapers.conf import Conf, StoredState, Decisions, AllCategories, GitNew
from refpapers.filesystem import yield_actions, parse, apply_all_filters
from refpapers.git import current_commit, git_difftree, git_status
from refpapers.logger import logger
from refpapers.schema import Paper, BibtexKey, whoosh_schema, IndexingAction, SCHEMA_VERSION
from refpapers.utils import q
from refpapers.view import print_git_indexingaction, console


RE_DOI = re.compile(
    r'(?:https://|info:)?\s*doi(?:\.org)?/?:?\s*'
    r'(10\.[0-9]{4,}(?:[\./][0-9A-Z]+)?(?:[\.-][0-9A-Z]+)*)',
    flags=re.IGNORECASE
)
RE_ARXIV = re.compile(
    r'arXiv:\s*[0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?',
    flags=re.IGNORECASE
)
RE_ARXIV_PREFIX = re.compile(r'arXiv:\s*', flags=re.IGNORECASE)


def index_data(full: bool, conf: Conf, storedstate: StoredState, decisions: Decisions):
    commit = None
    if not full:
        existing_schema_version = storedstate.read('schema_version')
        if existing_schema_version is None:
            console.print('[status]First indexing, performing full indexing[/status]')
            full = True
        elif existing_schema_version != SCHEMA_VERSION:
            console.print('[status]Existing index uses different schema version, performing full indexing[/status]')
            full = True
    if not full and not conf.use_git:
        console.print('[status]Not configured to use git, performing full indexing[/status]')
        full = True
    if not full:
        commit = storedstate.read('last_indexed_commit')
        if not commit or commit == 'initial':
            console.print('[status]No recorded git commit, performing full indexing[/status]')
            full = True

    papers: List[IndexingAction] = _find_papers_to_index(full=full, conf=conf, decisions=decisions, commit=commit)

    if len(papers) == 0:
        console.print('[status]Up to date, nothing to index[/status]')
    else:
        _index_papers(papers, full=full, conf=conf, decisions=decisions)
        storedstate.write('schema_version', SCHEMA_VERSION)

    if conf.use_git:
        commit = current_commit(conf.paths.data)
        storedstate.write('last_indexed_commit', commit)


def _find_papers_to_index(
    full: bool,
    conf: Conf,
    decisions: Decisions,
    commit: Optional[str]
) -> List[IndexingAction]:
    if full:
        actions = list(yield_actions(conf.paths.data, conf, decisions))
    else:
        assert commit is not None
        console.print(f'[status]Performing incremental indexing from commit {commit}')
        actions = git_difftree(conf.paths.data, commit)
        if not (conf.git_uncommitted == GitNew.IGNORE and conf.git_untracked == GitNew.IGNORE):
            staged: List[IndexingAction]
            untracked: List[IndexingAction]
            staged, untracked = git_status(conf.paths.data)
            staged = list(apply_all_filters(staged, conf, decisions))
            untracked = list(apply_all_filters(untracked, conf, decisions))

            if conf.git_uncommitted == GitNew.WARN:
                for ia in staged:
                    print_git_indexingaction(ia, 'STAGED')
            elif conf.git_uncommitted == GitNew.ADD:
                # add staged actions to index
                actions.extend(staged)

            if conf.git_untracked == GitNew.WARN:
                for ia in untracked:
                    print_git_indexingaction(ia, 'UNTRACKED')
                pass
            elif conf.git_untracked == GitNew.ADD:
                # add untracked actions to index
                for ia in untracked:
                    # convert '??' to 'A'
                    actions.append(IndexingAction('A', ia.paper))

        actions = list(apply_all_filters(actions, conf, decisions))

    papers = []
    for ia in actions:
        paper, error = parse(ia.path, conf.paths.data)
        if not paper:
            continue
        papers.append(IndexingAction(ia.action, paper))

    return papers


def _index_papers(papers: List[IndexingAction], full: bool, conf: Conf, decisions: Decisions):
    os.makedirs(conf.paths.index, exist_ok=True)
    all_categories = AllCategories(conf)
    if full:
        ix = index.create_in(conf.paths.index, whoosh_schema)
    else:
        ix = index.open_dir(conf.paths.index)
        all_categories.read()

    too_slow = set(x.arg1 for x in decisions.get(decisions.FULLTEXT_TOO_SLOW))

    if not full:
        # avoid duplicates from mixed full and incremental indexing
        papers = deduplicate(papers, conf)

    if len(papers) == 0:
        console.print('[status]Already up to date[/status]')
        return

    start = datetime.now()
    w = ix.writer()
    added = 0
    deleted = 0
    for ia in track(papers, description='Indexing...'):
        if ia.paper is None:
            continue
        if not isinstance(ia.paper, Paper):
            raise Exception(f'Indexing requires a Paper, not a {type(ia.paper).__name__}')

        paper = ia.paper
        if paper is None:
            continue
        assert paper.path.is_absolute(), f'Relative path in indexing: {paper.path}'
        path = str(paper.path)

        if ia.action == 'A':
            if path in too_slow:
                logger.info(f'Skipping this file (was too slow previously): {path}')
            else:
                body = extract_fulltext(paper.path, conf, decisions)
                doi, arxiv = extract_ids_from_fulltext(body, paper.path, conf)
            added += 1
            fields = {
                'path': path,
                'bibtex': str(paper.bibtex),
                'title': paper.title,
                'comment': '',
                'authors': ', '.join(paper.authors),
                'year': paper.year,
                'body': body,
                'pub_type': ' '.join(paper.pub_type),
                'tags': ' '.join(paper.tags),
            }
            if paper.number:
                fields['number'] = paper.number
            if doi:
                fields['doi'] = doi
            if arxiv:
                fields['arxiv'] = arxiv
            w.add_document(**fields)
            all_categories.add(tuple(paper.tags))
        elif ia.action == 'D':
            deleted += 1
            w.delete_by_term('path', path)
    w.commit()
    decisions.write()
    all_categories.write()
    delta = datetime.now() - start
    total = delta.total_seconds()
    per_paper = total / len(papers)
    add_del = '' if full else f' ({added} added/{deleted} deleted)'
    console.print(
        f'[status]Indexed [status.hi]{len(papers)} papers{add_del}[/status.hi]'
        f' in [status.hi]{total} seconds[/status.hi] ({per_paper} per paper)[/status]'
    )


def deduplicate(papers: List[IndexingAction], conf) -> List[IndexingAction]:
    result: List[IndexingAction] = []
    for ia in papers:
        if ia.action != 'A':
            # only deduplicate adds
            result.append(ia)
            continue
        if len(list(search(str(ia.path), conf=conf, decisions=None, limit=1, fields=['path']))) > 0:
            print(f'Path already indexed: {ia.path}')
            continue
        result.append(ia)
    return result


def result_to_paper(result) -> Paper:
    if len(result['pub_type']) > 0:
        pub_type = result['pub_type'].split(' ')
    else:
        pub_type = []
    number = result.get('number', None)
    doi = result.get('doi', None)
    arxiv = result.get('arxiv', None)
    return Paper(
        path=Path(result['path']),
        bibtex=BibtexKey.parse(result['bibtex']),
        title=result['title'],
        authors=result['authors'].split(', '),
        year=result['year'],
        pub_type=pub_type,
        tags=result['tags'].split(' '),
        number=number,
        doi=doi,
        arxiv=arxiv,
    )


def print_count(results):
    found = results.scored_length()
    if results.has_exact_length():
        total = len(results)
        flag = ''
    else:
        total = results.estimated_length()
        flag = '~'
    if total > found:
        print(f'{found} of {flag}{total} hits')
    elif found > 1:
        print(f'{found} hits')


def search(
    query: str, conf: Conf, decisions: Decisions = None, limit=10, fields: List[str] = None, silent: bool = False
) -> Generator[Paper, None, None]:
    if fields is None:
        fields = ["bibtex", "authors", "title", "comment", "body"]
    ix = index.open_dir(conf.paths.index)
    qp = qparser.MultifieldParser(fields, schema=whoosh_schema)
    q = qp.parse(query)
    # sort first by score, using as tiebreaker year
    # (can't break ties using first author in this scheme)
    sortedby = MultiFacet([
        ScoreFacet(),
        FieldFacet('year', reverse=True),
    ])

    with ix.searcher() as s:
        results = s.search(q, limit=limit, sortedby=sortedby)
        for result in results:
            paper = result_to_paper(result)
            yield paper
        if limit > 1 and not silent:
            print_count(results)


def extract_fulltext(path: Path, conf: Conf, decisions: Decisions) -> str:
    if path is None:
        return ''
    _, ending = os.path.splitext(path)
    extractor = conf.software.get_extractor(ending)
    if not extractor or extractor.lower() == 'none':
        return ''
    resolved_path = path.resolve()
    start = datetime.now()
    result = delegator.run(f'{extractor} {q(resolved_path)} -')
    delta = datetime.now() - start
    total = delta.total_seconds()
    if not result.return_code == 0:
        print(f'Extraction failed for {resolved_path}')
        return ''
    fulltext = result.out
    if conf.fulltext_chars and len(fulltext) > conf.fulltext_chars:
        fulltext = fulltext[:conf.fulltext_chars]
    # keep track of slow files to skip next time
    if total > conf.extract_max_seconds:
        logger.warning(
            f'Full text extraction was too slow {total} > {conf.extract_max_seconds} seconds,'
            f' will skip file in the future: {path}')
        decisions.add(decisions.FULLTEXT_TOO_SLOW, path)
    return fulltext


def extract_ids_from_fulltext(fulltext: str, path: Path, conf: Conf) -> Tuple[Optional[str], Optional[str]]:
    fulltext = fulltext[:conf.ids_chars]
    dois = set(RE_DOI.findall(fulltext))
    arxivs = set(RE_ARXIV_PREFIX.sub('', x) for x in RE_ARXIV.findall(fulltext))
    if len(dois) > 1:
        logger.warning(f'Found too many DOIs in {path}: {dois}')
    if len(arxivs) > 1:
        logger.warning(f'Found too many arXiv ids in {path}: {arxivs}')
    doi = list(dois)[0] if len(dois) == 1 else None
    arxiv = list(arxivs)[0] if len(arxivs) == 1 else None
    return doi, arxiv
