from pathlib import Path
from typing import List
from json import JSONDecodeError
import json


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
    def __init__(self, path: Path):
        self.path = path
        self._data = self._read()

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
            return self._data[key]
        val = func()
        self._write(key, val)
        return val
