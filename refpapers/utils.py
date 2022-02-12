from pathlib import Path
from typing import List, Optional, Callable
from json import JSONDecodeError
import json
import re
import shlex


class DeepDefaultDict(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = self.__class__()
        return super().__getitem__(key)

    def all_descendants(self, prefix: List[str]):
        for key, child in self.items():
            new_prefix = prefix + [key]
            yield (key, new_prefix)
            try:
                yield from child.all_descendants(new_prefix)
            except AttributeError:
                # ignore values that are not DeepDefaultDict-like
                pass


class JsonFileCache:
    """ Json-L file-backed append-only key-value cache """
    def __init__(self, path: Path, hit_func: Optional[Callable] = None):
        self.path = path
        self._data = self._read()
        self.hit_func = hit_func

    def _read(self):
        result = dict()
        if self.path.exists():
            with self.path.open('r') as fin:
                try:
                    for i, line in enumerate(fin):
                        lst = json.loads(line)
                        if len(lst) != 2:
                            raise ValueError(
                                f'Can not parse line {i} of {self.path}: saw {len(lst)} values, expecting 2.'
                            )
                        key, val = lst
                        result[key] = val
                except JSONDecodeError as e:
                    raise ValueError(f'Can not parse line {i} of {self.path}: {e}')
        return result

    def _write(self, key, val):
        self._data[key] = val
        with self.path.open('a') as fout:
            json.dump([key, val], fout)
            fout.write('\n')

    def get(self, key, func):
        if key in self._data:
            if self.hit_func:
                self.hit_func(key)
            return self._data[key]
        val = func(key)
        self._write(key, val)
        return val


HYPHEN_JOIN_PREFIXES = ['cross', 'low', 'multi', 'n', 'non', 'pre', 'semi', 'sub']
HYPHEN_PATTERNS = [
    re.compile(r'\b(' + prefix + r')-([\w])', flags=re.IGNORECASE)
    for prefix in HYPHEN_JOIN_PREFIXES
]
RE_INTRAWORD_HYPHEN = re.compile(r'([\w])-([\w])', flags=re.IGNORECASE)


def beautify_hyphen_compounds(text: str) -> str:
    # The selected prefixes are joined to the suffix by removal of the hyphe
    for pattern in HYPHEN_PATTERNS:
        text = pattern.sub(r'\1\2', text)
    # The remaining intraword hyphens are converted to spaces
    text = RE_INTRAWORD_HYPHEN.sub(r'\1 \2', text)
    return text


CONTRACTIONS = [
    ("n't", "nt"),
    ("ll'em", "ll them"),
    ("I'm", "I am"),
    ("'s", "s"),
    ("won't", "wont"),
]
CONTRACTION_PATTERNS = [(re.compile(pat + r'\b'), repl) for (pat, repl) in CONTRACTIONS]


def beautify_contractions(text: str) -> str:
    for pattern, replacement in CONTRACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def q(path: Path):
    return shlex.quote(str(path))
