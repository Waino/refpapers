import json
import os
import sys
import yaml
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, validator, root_validator
from typing import Dict, Generator, Optional, Set, Tuple, Sequence

from refpapers.logger import add_file_handler
from refpapers.view import question, prompt, console

HOMEDIR = os.environ.get('HOME', '.')
DEFAULT_CONFDIR = Path(HOMEDIR) / '.refpapers'


# #############
# Configuration
# #############

class Paths(BaseModel):
    index: Path
    data: Path
    log: Optional[Path]
    api_cache: Optional[Path]
    confdir: Optional[Path]

    @validator('*', pre=True)
    def expanduser(value):
        return Path(os.path.expanduser(value))


class Software(BaseModel):
    viewers: Dict[str, str]
    extractors: Dict[str, str]
    _has_warned_about: Set[str] = set()

    def get_viewer(self, ending: str):
        ending = ending.strip('.')
        if ending not in self.viewers:
            raise ValueError(f'To use this command, a viewer must set for ending: {ending}')
        return self.viewers[ending]

    def get_extractor(self, ending: str, default='pdftotext'):
        ending = ending.strip('.')
        if ending in self.extractors:
            extractor = self.extractors[ending]
        else:
            if ending not in self._has_warned_about:
                print(f'No extractor set for {ending}, defaulting to {default}', file=sys.stderr)
                self._has_warned_about.add(ending)
            extractor = default
        return extractor

    @validator('*', pre=True)
    def strip_dots(value):
        out = {key.strip('.'): val for key, val in value.items()}
        return out


class GitNew(Enum):
    WARN = 1
    IGNORE = 2
    ADD = 3

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError('Enum values must be given as strings')
        return cls.__getattr__(v)


class Conf(BaseModel):
    fulltext_chars: Optional[int] = None
    ids_chars: Optional[int] = 5000
    max_authors: int = -1
    extract_max_seconds: float = 3.0
    use_git: bool = False
    use_git_annex: bool = False
    git_uncommitted: GitNew = GitNew.WARN
    git_untracked: GitNew = GitNew.WARN
    use_scholar: bool = False
    paths: Paths
    software: Software = Software(viewers=dict(), extractors=dict())

    @classmethod
    def from_yaml(cls, file_path: Path) -> "Conf":
        with open(file_path) as conffile:
            d = yaml.safe_load(conffile)
            if not d:
                raise ValueError(f'Configuration file {file_path} can not be empty')
            conf = Conf(**d)
            if conf.paths.log:
                add_file_handler(conf.paths.log)
            if not conf.paths.confdir:
                conf.paths.confdir = file_path.parent
        return conf

    def all_endings(self):
        endings = set()
        endings.update(self.software.viewers.keys())
        endings.update(self.software.extractors.keys())
        if len(endings) == 0:
            endings = ('pdf', 'djvu')
        return endings

    # validators
    @root_validator
    def check_git(cls, values):
        if values.get('use_git_annex') and not values.get('use_git'):
            raise ValueError('use_git_annex requires use_git')
        return values


# #####################################
# State stored in one file per variable
# #####################################

class StoredState:
    VARIABLES = ['last_indexed_commit', 'schema_version']

    def __init__(self, confdir: Path = DEFAULT_CONFDIR):
        self.confdir = confdir

    def read(self, variable):
        assert variable in self.VARIABLES
        path = self.confdir / variable
        if not path.exists():
            return None
        with open(path) as fin:
            return fin.readline().strip()

    def write(self, variable, value):
        assert variable in self.VARIABLES
        path = self.confdir / variable
        with open(path, 'w') as fout:
            print(value, file=fout)


# #########
# Decisions
# #########

@dataclass(frozen=True, order=True)
class Decision:
    relation: str
    arg1: str
    arg2: str


class Decisions:
    IGNORE = 'IGNORE'
    FULLTEXT_TOO_SLOW = 'FULLTEXT_TOO_SLOW'

    def __init__(self, confdir: Path = DEFAULT_CONFDIR):
        self._path = confdir / 'decisions'
        self._tmp_path = confdir / '.decisions.tmp'
        self.decisions = list(self.read())

    def read(self):
        if not self._path.exists():
            yield from []
        else:
            with self._path.open() as lines:
                for line in lines:
                    line = line.strip()
                    parts = line.split(None, 3)
                    if len(parts) == 1:
                        continue
                    if len(parts) == 2:
                        parts.append(None)
                    yield Decision(*parts)

    def add(self, relation: str, arg1, arg2=None):
        arg2 = str(arg2) if arg2 else None
        self.decisions.append(Decision(relation, str(arg1), arg2))

    def get(self, relation: Optional[str] = None) -> Generator[Decision, None, None]:
        for decision in self.decisions:
            if relation and not relation == decision.relation:
                continue
            yield decision

    def write(self):
        with self._tmp_path.open('w') as fout:
            for decision in sorted(set(self.decisions)):
                if decision.arg2 is None:
                    print(f'{decision.relation}\t{decision.arg1}', file=fout)
                else:
                    print(f'{decision.relation}\t{decision.arg1}\t{decision.arg2}', file=fout)
        os.replace(self._tmp_path, self._path)


# ##############
# All categories
# ##############

class AllCategories:
    def __init__(self, conf: Conf):
        if conf.paths.confdir:
            self.all_categories_path = conf.paths.confdir / 'all_categories.json'
        else:
            raise Exception('conf.paths.confdir must be set')
        # each category is stored as a tuple of keywords
        self.all_categories: Set[Tuple[str, ...]] = set()

    def add(self, category: Sequence[str]):
        category_tpl: Tuple[str, ...] = tuple(category)
        if category_tpl not in self.all_categories:
            self.all_categories.add(category_tpl)
            self.write()

    def read(self):
        if self.all_categories_path.exists():
            with self.all_categories_path.open('r') as fin:
                self.all_categories = set(tuple(x) for x in json.load(fin))
        return self

    def write(self):
        with self.all_categories_path.open('w') as fout:
            json.dump(list(sorted(self.all_categories)), fout)

    def __iter__(self) -> Generator[Tuple[str, ...], None, None]:
        yield from sorted(self.all_categories)


def load_conf(confdir: Path = DEFAULT_CONFDIR):
    conf = Conf.from_yaml(confdir / 'conf.yml')
    storedstate = StoredState(confdir)
    decisions = Decisions(confdir)
    return conf, storedstate, decisions


def ensure_conf(confdir: Path = DEFAULT_CONFDIR):
    path = confdir / 'conf.yml'
    if path.exists():
        return True
    create = question(
        f'No [italic]conf.yml[/italic] found in [italic]{confdir}[/italic].'
        ' Do you want to create a minimal conf?',
        ['No', 'yes']
    )
    if create == 'yes':
        write_minimal_conf(confdir)
        console.print(
            '[warning]N.B:[/warning] It is highly recommended that you check out the example conf.')


MINIMAL_YAML = """
paths:
    index: {index}
    data: {data}
"""


def write_minimal_conf(confdir: Path = DEFAULT_CONFDIR):
    path = confdir / 'conf.yml'
    data = Path(prompt('Path to the directory where you keep your papers (PDFs): '))
    index = Path(prompt('Path where you want the search database to be stored: '))
    if (data / '.git').exists():
        console.print(
            f'[warning]N.B:[/warning] {data}/.git found: consider turning on the [italic]use_git[/italic] feature'
            ' for faster indexing. See the example conf.'
        )
    with open(path, 'w') as fout:
        print(MINIMAL_YAML.format(index=index, data=data), file=fout)
