import re
from dataclasses import dataclass
from functools import total_ordering
from pathlib import Path
from typing import Tuple, Optional, Union
from whoosh.analysis import StemmingAnalyzer, RegexTokenizer  # type: ignore
from whoosh.fields import Schema, TEXT, KEYWORD, ID, NUMERIC  # type: ignore

RE_BIBTEX = re.compile('^([a-z-].*)([0-9]{4})([a-z-].*)$')
RE_TITLE_WORD = re.compile('^([a-z].*)$')
SKIP_TITLE_WORDS = {'a', 'an', 'on', 'in', 'the'}
RE_UNWANTED = re.compile(r'[^\w\+\.-]')


@dataclass(unsafe_hash=True)
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

    @staticmethod
    def title_word(title):
        for word in title.split():
            word = word.lower()
            word = RE_UNWANTED.sub('', word)
            if not RE_TITLE_WORD.match(word):
                continue
            if word in SKIP_TITLE_WORDS:
                continue
            return word
        return ''

    def __str__(self):
        return f'{self.author}{self.year}{self.word}'


@total_ordering
@dataclass(unsafe_hash=True, eq=True)
class Paper:
    path: Path
    bibtex: BibtexKey
    title: str
    authors: Tuple[str, ...]
    year: int
    pub_type: Tuple[str, ...]
    tags: Tuple[str, ...]
    number: Optional[str]
    doi: Optional[str]
    arxiv: Optional[str]

    @property
    def suffix(self):
        return self.path.suffix

    def __lt__(self, other: "Paper"):
        my_bibtex = str(self.bibtex)
        other_bibtex = str(other.bibtex)
        if my_bibtex < other_bibtex:
            return True
        if other_bibtex < my_bibtex:
            return False
        else:
            return str(self) < str(other)


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


SCHEMA_VERSION = 'v0.2'

# Tokenize bibtex key alphabetic and numeric parts separately
rt = RegexTokenizer(r'([a-z]+|[0-9]+)')

whoosh_schema = Schema(
    path=ID(stored=True),
    bibtex=TEXT(stored=True, analyzer=rt, field_boost=100.0),
    title=TEXT(stored=True, field_boost=30.0),
    comment=TEXT(stored=True, field_boost=30.0),
    authors=KEYWORD(stored=True, commas=True, lowercase=True, scorable=True, field_boost=60.0),
    year=NUMERIC(stored=True, signed=False, sortable=True, field_boost=30.0),
    body=TEXT(analyzer=StemmingAnalyzer()),
    pub_type=KEYWORD(stored=True),
    tags=KEYWORD(stored=True),
    number=NUMERIC(stored=True, signed=False, sortable=True),
    doi=ID(stored=True, field_boost=5.0),
    arxiv=ID(stored=True, field_boost=5.0),
)
