from typing import List


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
