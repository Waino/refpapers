import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union
from whoosh.analysis import StemmingAnalyzer  # type: ignore
from whoosh.fields import Schema, TEXT, KEYWORD, ID, NUMERIC  # type: ignore

RE_BIBTEX = re.compile('^([a-z].*)([0-9]{4})([a-z].*)$')


@dataclass
class BibtexKey:
    author: str
    year: int
    word: str

    @classmethod
    def parse(cls, string: str):
        m = RE_BIBTEX.match(string)
        if not m:
            raise ValueError(f'Unable to parse BibtexKey {string}')
        author, year, word = m.groups()
        return cls(author, int(year), word)

    def __str__(self):
        return f'{self.author}{self.year}{self.word}'


@dataclass
class Paper:
    path: Path
    bibtex: BibtexKey
    title: str
    authors: List[str]
    year: int
    pub_type: List[str]
    tags: List[str]
    number: Optional[str]

    @property
    def suffix(self):
        return self.path.suffix


@dataclass
class IndexingAction:
    # Initial actions: A, M, D, ??, ...
    # Processing should reduce these to aither A or D
    action: str
    paper: Union[Path, Paper]

    @property
    def path(self):
        if isinstance(self.paper, Path):
            return self.paper
        else:
            return self.paper.path


SCHEMA_VERSION = 'v0.1'

whoosh_schema = Schema(
    path=ID(stored=True),
    bibtex=ID(stored=True),
    title=TEXT(stored=True, field_boost=10.0),
    comment=TEXT(stored=True, field_boost=10.0),
    authors=KEYWORD(stored=True, commas=True, lowercase=True, scorable=True, field_boost=20.0),
    year=NUMERIC(stored=True, signed=False, sortable=True),
    body=TEXT(analyzer=StemmingAnalyzer()),
    pub_type=KEYWORD(stored=True),
    tags=KEYWORD(stored=True),
    number=NUMERIC(stored=True, signed=False, sortable=True),
)
