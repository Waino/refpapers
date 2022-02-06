import re
import os
from collections import Counter, defaultdict
from copy import copy
from dataclasses import dataclass
from pathlib import Path
from prompt_toolkit.completion import Completer, Completion, WordCompleter
from shutil import move
from typing import List, Optional, Callable, Dict, Any
from unidecode import unidecode

from refpapers.apis import CrossrefApi, ArxivApi, ScholarApi, paper_from_metadata
from refpapers.conf import AllCategories
from refpapers.doctypes import open_in_viewer
from refpapers.filesystem import generate, parse, yield_all_paths
from refpapers.git import git_annex_add, git_annex_sync
from refpapers.logger import logger
from refpapers.schema import Paper
from refpapers.search import search, extract_fulltext, extract_ids_from_fulltext, index_data
from refpapers.utils import DeepDefaultDict, q
from refpapers.view import LongTask, print_fulltext, print_details, question, prompt, console


class CategoryCompleter(Completer):
    def __init__(self, categories: AllCategories, search_func):
        self._category_dict = self._prepare_data(categories)
        self._search_func = search_func

    def get_completions(self, document, complete_event):
        query = document.text
        completions = list(self._literal_phase(query))
        if len(completions) == 0:
            completions = self._search_phase(query)
        yield from completions

    def _literal_phase(self, query):
        parts = query.split('/')
        prefix = parts[:-1]
        suffix = parts[-1]

        # restrict search to descendants of already filled-in part
        cursor = self._category_dict
        for part in prefix:
            if part not in cursor:
                return
            cursor = cursor[part]

        # if the same key is used in several parts of the tree, yield them all
        by_key = defaultdict(list)
        for key, completion in cursor.all_descendants(prefix):
            by_key[key].append(completion)

        # filter to keep only matching keys
        for key, completions in by_key.items():
            if self._match(key, suffix):
                for completion in completions:
                    yield Completion('/'.join(completion), start_position=-len(query))

    def _match(self, key, suffix):
        """ is the key a hit for the suffix of the search query """
        return key.startswith(suffix)

    def _search_phase(self, query):
        papers = self._search_func(query)
        hit_categories = Counter(('/'.join(paper.tags) for paper in papers))
        for completion, _ in hit_categories.most_common():
            yield Completion(completion, start_position=-len(query))

    def _prepare_data(self, categories: AllCategories):
        category_dict = DeepDefaultDict()
        for cat in categories:
            cursor = category_dict
            for component in cat:
                if len(component) == 0:
                    continue
                cursor = cursor[component]
        return category_dict


def prompt_category(categories: AllCategories, search_func) -> str:
    completer = CategoryCompleter(categories, search_func)
    result = prompt('Category: ', completer=completer)
    return result


def prompt_edit_path(path: Path) -> Path:
    result = prompt('Path: ', default=str(path))
    return Path(result)


RE_NONWORD = re.compile(r'\W')
RE_MULTISPACE = re.compile(r'\s\s*')
RE_TRAILING_NUMBER = re.compile(r'[0-9]*$')


@dataclass
class PromptField:
    field: str
    pattern: Optional[str] = None
    prefunc: Optional[Callable] = None
    postfunc: Optional[Callable] = None
    extra: Optional[List[str]] = None


def prompt_metadata(fields: List[PromptField], fulltext: str) -> Dict[str, Any]:
    fulltext = RE_NONWORD.sub(' ', fulltext)
    fulltext = RE_MULTISPACE.sub(' ', fulltext)
    words = set(fulltext.split())
    for word in set(words):
        words.add(word.lower())
    results: Dict[str, Any] = dict()
    for field in fields:
        if field.pattern:
            pat = re.compile(field.pattern)
            filtered_words = [word for word in sorted(words) if pat.match(word)]
        else:
            filtered_words = list(sorted(words))
        if field.prefunc:
            filtered_words = list(sorted(set(field.prefunc(word) for word in filtered_words)))
        if field.extra:
            filtered_words.extend(field.extra)
        completer = WordCompleter(filtered_words)
        fieldname = f'{field.field.capitalize()}:'
        result = None
        while result is None:
            result = prompt(f'{fieldname:9} ', completer=completer)
            try:
                if field.postfunc:
                    result = field.postfunc(result)
            except Exception:
                console.print(f'[warning]Invalid input[/warning]. Must be accepted by {field.postfunc}')
                result = None
        results[field.field] = result
    return results


def prep_author_completion(author: str) -> str:
    author = RE_TRAILING_NUMBER.sub('', author)
    author = unidecode(author, errors='replace', replace_str='_')
    return author


class AutoRenamer:
    def __init__(self, conf, storedstate, decisions, categories):
        self.conf = conf
        self.storedstate = storedstate
        self.decisions = decisions
        self.categories = categories

        self._crossref = CrossrefApi(conf)
        self._arxiv = ArxivApi(conf)
        self._scholar = ScholarApi(conf) if conf.use_scholar else None

    def rename(self, path):
        fulltext = extract_fulltext(path, self.conf, self.decisions)

        # preprocess fulltext and display it
        fulltext_top = [line for line in fulltext.split('\n') if len(line.strip()) > 0]
        fulltext_top = fulltext_top[:15]
        print_fulltext(fulltext_top, path)

        # extract identifiers that can be used to retrieve metadata from apis
        paper: Optional[Paper] = None
        doi, arxiv = extract_ids_from_fulltext(fulltext, path, self.conf)
        if doi:
            with LongTask(f'Crossref DOI query... ({doi})') as ltask:
                paper = self._crossref.paper_from_doi(doi)
                if paper:
                    ltask.set_status(ltask.OK)
        if not paper and arxiv:
            with LongTask(f'ArXiv query... (arXiv:{arxiv})') as ltask:
                paper = self._arxiv.paper_from_id(arxiv)
                if paper:
                    ltask.set_status(ltask.OK)

        if not paper:
            fulltext_top_joined = '\n'.join(fulltext_top)
            # prompt for missing metadata and fill in the rest based on scholar, if turned on
            if self.conf.use_scholar:
                meta = prompt_metadata([PromptField(field='title')], fulltext_top_joined)
                with LongTask('Scholar query...') as ltask:
                    paper = self._scholar.paper_from_title(meta['title'])
                    if paper:
                        ltask.set_status(ltask.OK)
            else:
                meta = prompt_metadata(
                    [
                        PromptField(field='title', postfunc=lambda x: x.strip()),
                        PromptField(
                            field='year',
                            pattern=r'^[12]\d{3}$',
                            postfunc=int,
                        ),
                        PromptField(
                            field='authors',
                            pattern=r'^[^0-9a-z].*',
                            prefunc=prep_author_completion,
                            postfunc=lambda x: x.split(),
                            extra=['etAl']
                        )
                    ],
                    fulltext_top_joined
                )
                paper = paper_from_metadata(meta, path, self.conf.max_authors)

        # TODO: prompt for pubtype

        # prompt for a category
        def _search(query: str):
            return search(query, self.conf, self.decisions, limit=10, silent=True)

        category = prompt_category(self.categories, _search)
        self.categories.add(category.split('/'))
        paper = self._generate_path(paper, category, suffix=path.suffix)

        if paper:
            new_path = paper.path
            # display results
            parsed_paper, error = parse(new_path, root=self.conf.paths.data)
            while not parsed_paper:
                console.print(error.describe())
                new_path = prompt_edit_path(new_path)
                if new_path == Path(''):
                    console.print('[status]empty path given, aborting[/status]')
                    return None
                parsed_paper, error = parse(new_path, root=self.conf.paths.data)
            print_details(parsed_paper)
            if paper.path.exists():
                logger.warning(f'File already exists, will not overwrite: {new_path}')
                return None
            # prompt for confirmation
            choice = question('Apply the rename', ['yes', 'no', 'edit'])
            if choice == 'edit':
                new_path = prompt_edit_path(new_path)
                choice = 'yes'
            # apply rename
            if choice == 'yes':
                dir_path = new_path.parent
                if not dir_path.exists():
                    with LongTask('creating subdirectory ...') as ltask:
                        os.makedirs(dir_path, exist_ok=True)
                        if dir_path.exists():
                            ltask.set_status(ltask.OK)
                    # FIXME: remove root dir, split at separators. Save when done.
                    # self.categories.add(new_category)
                print(f'mv -i {q(path)} {q(new_path)}')
                with LongTask('moving...') as ltask:
                    move(path, new_path)
                    if new_path.exists():
                        ltask.set_status(ltask.OK)
                        return new_path
                    else:
                        return None
            else:
                return None
        else:
            logger.warning('Failed to gather metadata for renaming')
            return None

    def ingest_inbox(self, path: Path, open_before_rename: bool):
        if not self._check_inbox_path(path):
            return
        # glob based on the suffixes that refpapers recognizes
        for ia in yield_all_paths(path, self.conf):
            if open_before_rename:
                open_in_viewer(ia.path, self.conf)
            new_path = self.rename(ia.path)
            if not new_path:
                continue
            if self.conf.use_git_annex:
                with LongTask('add to git annex...') as ltask:
                    git_annex_add(self.conf.paths.data, new_path)
                    ltask.set_status(ltask.OK)
        if self.conf.use_git_annex:
            with LongTask('sync git annex...') as ltask:
                git_annex_sync(self.conf.paths.data)
                ltask.set_status(ltask.OK)
        index_data(full=False, conf=self.conf, storedstate=self.storedstate, decisions=self.decisions)

    def _check_inbox_path(self, path: Path):
        special_paths = [
            self.conf.paths.index,
            self.conf.paths.data,
            self.conf.paths.log,
            self.conf.paths.api_cache,
            self.conf.paths.confdir,
        ]
        path = path.resolve()
        for special_path in special_paths:
            if not special_path:
                continue
            special_path = special_path.resolve()
            if path == special_path:
                console.print(
                    f'[warning]Inbox path "{path}" equals one of the special paths defined in the conf. '
                    'You do not want this. Aborting.[/warning]'
                )
                return False
        return True

    def _generate_path(self, paper: Paper, category: str, suffix: str):
        tags = category.split('/')
        path = Path(generate(paper, root=self.conf.paths.data, tags=tags))
        # This violates the usual immutability of Paper, but we are modifying a copy
        result = copy(paper)
        result.path = path
        result.tags = tags
        return result
