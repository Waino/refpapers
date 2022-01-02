import prompt_toolkit
import re
from collections import Counter, defaultdict
from copy import copy
from pathlib import Path
from prompt_toolkit.completion import Completer, Completion, WordCompleter
from typing import List, Optional, Tuple

from refpapers.apis import CrossrefApi, ArxivApi, ScholarApi, paper_from_metadata
from refpapers.conf import AllCategories
from refpapers.filesystem import generate
from refpapers.schema import Paper
from refpapers.search import search, extract_fulltext, extract_ids_from_fulltext
from refpapers.utils import DeepDefaultDict
from refpapers.view import LongTask, print_fulltext, print_details, question


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


def prompt_category(categories: AllCategories, search_func):
    completer = CategoryCompleter(categories, search_func)
    result = prompt_toolkit.prompt('Category: ', completer=completer)
    return result


RE_NONWORD = re.compile(r'\W')
RE_MULTISPACE = re.compile(r'\s\s*')


def prompt_metadata(fields: List[Tuple[str, Optional[str]]], fulltext: str):
    fulltext = RE_NONWORD.sub(' ', fulltext)
    fulltext = RE_MULTISPACE.sub(' ', fulltext)
    words = set(fulltext.split())
    for word in set(words):
        words.add(word.lower())
    results = dict()
    for field, pattern in fields:
        if pattern:
            pat = re.compile(pattern)
            filtered_words = [word for word in sorted(words) if pat.match(word)]
        else:
            filtered_words = sorted(words)
        completer = WordCompleter(filtered_words)
        result = prompt_toolkit.prompt(f'{field.capitalize()}: ', completer=completer)
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
                meta = prompt_metadata([('title', None)], fulltext_top_joined)
                with LongTask('Scholar query...') as ltask:
                    paper = self._scholar.paper_from_title(meta['title'])
                    if paper:
                        ltask.set_status(ltask.OK)
            else:
                meta = prompt_metadata(
                    [('title', None), ('year', r'^[12]\d{3}$'), ('authors', r'^[^0-9a-z].*')],
                    fulltext_top_joined
                )
                paper = paper_from_metadata(meta)

        # TODO: prompt for pubtype

        # prompt for a category
        def _search(query: str):
            return search(query, self.conf, self.decisions, limit=10, silent=True)

        category = prompt_category(self.categories, _search)
        paper = self._generate_path(paper, category)

        if paper:
            # display results
            print_details(paper)
            # prompt for confirmation
            choice = question('Apply the rename', ['yes', 'no'])
            # apply rename
            if choice == 'yes':
                print(f'mv -i "{path}" "{paper.path}"')
        else:
            print('Renaming failed')

    def rename_all(self, path):
        # glob based on suffixes
        # call auto_rename
        # add to git annex
        # sync git annex
        # index
        pass

    def _generate_path(self, paper: Paper, category: str):
        # FIXME: replace too many authors with etAl (too late to do here)
        tags = category.split('/')
        path = Path(generate(paper, root=self.conf.paths.data, tags=tags))
        # This violates the usual immutability of Paper, but we are modifying a copy
        result = copy(paper)
        result.path = path
        result.tags = tags
        return result
