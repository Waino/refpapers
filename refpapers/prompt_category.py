import prompt_toolkit
from collections import Counter, defaultdict
from prompt_toolkit.completion import Completer, Completion
from typing import List

from refpapers.utils import DeepDefaultDict


class CategoryCompleter(Completer):
    def __init__(self, categories: List[str], search_func):
        self._category_dict = self._prepare_data(categories)
        self._search_func = search_func

    def get_completions(self, document, complete_event):
        query = document.text
        completions = list(self._literal_phase(query))
        if len(completions) == 0:
            completions = self._search_phase(query)
        yield from completions

    def _literal_phase(self, query):
        parts = query.split()
        prefix = parts[:-1]
        suffix = parts[-1]

        cursor = self._category_dict
        for part in prefix:
            if part not in cursor:
                return
            cursor = cursor[part]

        by_key = defaultdict(list)
        for key, completion in cursor.all_descendants(prefix):
            by_key[key].append(completion)

        for key, completions in by_key.items():
            if self._match(key, suffix):
                for completion in completions:
                    yield Completion(' '.join(completion), start_position=-len(query))

    def _match(self, key, suffix):
        """ is the key a hit for the suffix of the search query """
        return key.startswith(suffix)

    def _search_phase(self, query):
        papers = self._search_func(query)
        hit_categories = Counter(('/'.join(paper.tags) for paper in papers))
        for completion, _ in hit_categories.most_common():
            yield Completion(completion, start_position=-len(query))

    def _prepare_data(self, categories):
        category_dict = DeepDefaultDict()
        for cat in categories:
            cursor = category_dict
            for component in cat.split('/'):
                if len(component) == 0:
                    continue
                cursor = cursor[component]
        return category_dict

    # print(category_dict)
    # for tpl in category_dict['nlp']['machineTranslation'].all_descendants(['pref']):
    #     print(tpl)


def prompt_category(categories: List[str], search_func):
    completer = CategoryCompleter(categories, search_func)
    result = prompt_toolkit.prompt('Category: ', completer=completer)
    return result
