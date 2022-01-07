import re
import os
from collections import Counter, defaultdict
from copy import copy
from pathlib import Path
from prompt_toolkit.completion import Completer, Completion, WordCompleter
from typing import List, Optional, Tuple, Callable
from shutil import move

from refpapers.apis import CrossrefApi, ArxivApi, ScholarApi, paper_from_metadata
from refpapers.conf import AllCategories
from refpapers.filesystem import generate, yield_all_paths
from refpapers.git import git_annex_add, git_annex_sync
from refpapers.logger import logger
from refpapers.schema import Paper
from refpapers.search import search, extract_fulltext, extract_ids_from_fulltext
from refpapers.utils import DeepDefaultDict
from refpapers.view import LongTask, print_fulltext, print_details, question, prompt


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


def prompt_metadata(fields: List[Tuple[str, Optional[str], Optional[Callable]]], fulltext: str):
    fulltext = RE_NONWORD.sub(' ', fulltext)
    fulltext = RE_MULTISPACE.sub(' ', fulltext)
    words = set(fulltext.split())
    for word in set(words):
        words.add(word.lower())
    results = dict()
    for field, pattern, postfunc in fields:
        if pattern:
            pat = re.compile(pattern)
            filtered_words = [word for word in sorted(words) if pat.match(word)]
        else:
            filtered_words = sorted(words)
        completer = WordCompleter(filtered_words)
        result = prompt(f'{field.capitalize()}: ', completer=completer)
        if postfunc:
            result = postfunc(result)
        results[field] = result
    return results


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
            with LongTask(f'ArXiv query... ({arxiv})') as ltask:
                # FIXME: decide whether "arXiv:" is part of id or not
                paper = self._arxiv.paper_from_id(arxiv)
                if paper:
                    ltask.set_status(ltask.OK)

        if not paper:
            fulltext_top_joined = '\n'.join(fulltext_top)
            # prompt for missing metadata and fill in the rest based on scholar, if turned on
            if self.conf.use_scholar:
                meta = prompt_metadata([('title', None, None)], fulltext_top_joined)
                with LongTask('Scholar query...') as ltask:
                    paper = self._scholar.paper_from_title(meta['title'])
                    if paper:
                        ltask.set_status(ltask.OK)
            else:
                meta = prompt_metadata(
                    [('title', None, lambda x: x.strip()),
                     ('year', r'^[12]\d{3}$', None),
                     ('authors', r'^[^0-9a-z].*', lambda x: x.split())],
                    fulltext_top_joined
                )
                paper = paper_from_metadata(meta, path)

        # TODO: prompt for pubtype

        # prompt for a category
        def _search(query: str):
            return search(query, self.conf, self.decisions, limit=10, silent=True)

        category = prompt_category(self.categories, _search)
        paper = self._generate_path(paper, category, suffix=path.suffix)

        if paper:
            new_path = paper.path
            # display results
            print_details(paper)
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
                print(f'mv -i "{path}" "{new_path}"')
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

    def ingest_inbox(self, path):
        # glob based on the suffixes that refpapers recognizes
        for ia in yield_all_paths(path, self.conf):
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
        # FIXME: index

    def _generate_path(self, paper: Paper, category: str, suffix: str):
        tags = category.split('/')
        path = Path(generate(paper, root=self.conf.paths.data, tags=tags))
        # This violates the usual immutability of Paper, but we are modifying a copy
        result = copy(paper)
        result.path = path
        result.tags = tags
        return result
