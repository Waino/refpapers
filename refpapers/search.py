import delegator  # type: ignore
import os
from datetime import datetime
from pathlib import Path
from typing import List, Generator
from whoosh import index, qparser  # type: ignore
from rich.progress import track

from refpapers.logger import logger
from refpapers.conf import Conf, Decisions
from refpapers.schema import Paper, BibtexKey, whoosh_schema, IndexingAction
from refpapers.view import console


def index_data(papers: List[IndexingAction], full: bool, conf: Conf, decisions: Decisions):
    os.makedirs(conf.paths.index, exist_ok=True)
    if full:
        ix = index.create_in(conf.paths.index, whoosh_schema)
    else:
        ix = index.open_dir(conf.paths.index)

    too_slow = set(x.arg1 for x in decisions.get(decisions.FULLTEXT_TOO_SLOW))

    start = datetime.now()
    w = ix.writer()
    for ia in track(papers, description="Indexing..."):
        if ia.paper is None:
            continue
        if not isinstance(ia.paper, Paper):
            raise Exception(f'Indexing requires a Paper, not a {type(ia.paper).__name__}')
        if ia.action == 'A':
            paper = ia.paper
            if paper is None:
                continue
            path = str(paper.path)
            if path in too_slow:
                logger.info(f'Skipping this file (was too slow previously): {path}')
            else:
                body = extract_fulltext(paper.path, conf, decisions)
            w.add_document(
                    path=path,
                    bibtex=str(paper.bibtex),
                    title=paper.title,
                    comment='',
                    authors=', '.join(paper.authors),
                    year=paper.year,
                    body=body,
                    pub_type=' '.join(paper.pub_type),
                    tags=' '.join(paper.tags),
                    number=paper.number,
            )
    w.commit()
    decisions.write()
    delta = datetime.now() - start
    total = delta.total_seconds()
    per_paper = total / len(papers)
    console.print(
        f'[status]Indexed [status.hi]{len(papers)} papers[/status.hi]'
        f' in [status.hi]{total} seconds[/status.hi] ({per_paper} per paper)[/status]'
    )


def result_to_paper(result) -> Paper:
    if len(result['pub_type']) > 0:
        pub_type = result['pub_type'].split(' ')
    else:
        pub_type = []
    return Paper(
        path=Path(result['path']),
        bibtex=BibtexKey.parse(result['bibtex']),
        title=result['title'],
        authors=result['authors'].split(', '),
        year=result['year'],
        pub_type=pub_type,
        tags=result['tags'].split(' '),
        number=result['number'],
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
    else:
        print('No papers matched the query')


def search(
    query: str, conf: Conf, decisions: Decisions, limit=10, fields: List[str] = None
) -> Generator[Paper, None, None]:
    if fields is None:
        fields = ["authors", "title", "comment", "body"]
    ix = index.open_dir(conf.paths.index)
    qp = qparser.MultifieldParser(fields, schema=whoosh_schema)
    q = qp.parse(query)
    with ix.searcher() as s:
        results = s.search(q, limit=limit)
        for result in results:
            paper = result_to_paper(result)
            yield paper
        if limit > 1:
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
    result = delegator.run(f'{extractor} {resolved_path} -')
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
