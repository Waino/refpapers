import glob
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Match, Generator, Iterable, Optional, Tuple
from unidecode import unidecode

from refpapers.logger import logger
from refpapers.conf import Decisions, Conf
from refpapers.schema import Paper, BibtexKey, IndexingAction
from refpapers.utils import beautify_hyphen_compounds, beautify_contractions


RE_NAME = re.compile(r'^[A-Za-z].*$')
RE_NUMBER = re.compile(r'^[0-9]+$')
RE_MAIN = re.compile(r'(.*)_.*([0-9]{4})')
RE_BOOK = re.compile(r'_[Bb]ook')
RE_SLIDES = re.compile(r'_[Ss]lides')
RE_SURVEY = re.compile(r'_[Ss]urvey')
RE_THESIS = re.compile(r'_[Tt]hesis')
RE_CAPWORDS = re.compile(r'([^A-Z])([A-Z])')
RE_A_FOO = re.compile(r'(?<![A-Z])(A)([A-Z])')
RE_MULTISPACE = re.compile(r'  *')
RE_MULTIUNDER = re.compile(r'__*')
RE_UNWANTED = re.compile(r'[^\w\+\.-]')

SEPARATOR = '_-_'
FMT_PARSE_ERROR = 'Unable to parse filename: {reason:18} - {file_path}'


def is_in_gitdir(path: Path) -> bool:
    return any(part == '.git' for part in path.parts)


@lru_cache(None)
def _ending_globs(all_endings: Iterable[str]) -> List[str]:
    out = []
    for ending in all_endings:
        ending_glob = ['*.'] + ['[{}{}]'.format(char, char.upper()) for char in ending]
        out.append(''.join(ending_glob))
    return out


def ending_globs(conf: Conf) -> List[str]:
    all_endings = tuple(sorted(conf.all_endings()))
    return _ending_globs(all_endings)


def yield_all_paths(root, conf: Conf) -> Generator[IndexingAction, None, None]:
    for ending_glob in ending_globs(conf):
        for path in sorted(Path(root).rglob(ending_glob)):
            yield IndexingAction('A', path)


def apply_decisions(actions: Iterable[IndexingAction], decisions: Decisions) -> Generator[IndexingAction, None, None]:
    ignored = set(x.arg1 for x in decisions.get(decisions.IGNORE))
    actions = filter(lambda ia: str(ia.paper) not in ignored, actions)
    yield from actions


def keep_valid_endings(actions: Iterable[IndexingAction], conf: Conf) -> Generator[IndexingAction, None, None]:
    endings = conf.all_endings()
    for ia in actions:
        suffix = ia.paper.suffix.lstrip('.')
        if suffix in endings:
            yield ia


def yield_actions(root, conf: Conf, decisions: Decisions) -> Generator[IndexingAction, None, None]:
    """ Yield the paths of all the documents that should be indexed """
    all_paths = yield_all_paths(root, conf)
    paths = filter(lambda ia: not is_in_gitdir(ia.path), all_paths)
    filtered_paths = apply_decisions(paths, decisions)
    yield from filtered_paths


def apply_all_filters(
    all_actions: Iterable[IndexingAction], conf: Conf, decisions: Decisions
) -> Generator[IndexingAction, None, None]:
    """Apply all filters to the given IndexingActions, keeping only the documents that should be indexed"""
    non_git_actions = filter(lambda ia: not is_in_gitdir(ia.path), all_actions)
    ending_actions = keep_valid_endings(non_git_actions, conf)
    filtered_actions = apply_decisions(ending_actions, decisions)
    yield from filtered_actions


def uncapword(text: str) -> str:
    text = RE_A_FOO.sub(_uncapword, text)
    text = RE_CAPWORDS.sub(_uncapword, text)
    return text


def _uncapword(m: Match) -> str:
    return '{} {}'.format(m.group(1), m.group(2).lower())


def capword(text: str) -> str:
    text = text.replace('-', ' ')
    return ''.join(word.capitalize() for word in text.split())


def yield_all_subdirs(root: Path):
    yield from glob.glob(f'{root}/**/', recursive=True)


@dataclass
class ParseError:
    path: Path
    reason: str

    def describe(self):
        return f'{self.reason:18} - {self.path}'


def parse(file_path: Path, root: Path) -> Tuple[Optional[Paper], Optional[ParseError]]:
    dir_path, file_name = os.path.split(file_path)
    tags = dir_path.split(os.path.sep)
    # remove root dir from tags
    tags = tags[len(str(root).split(os.path.sep)):]
    try:
        authors_part, title = file_name.split(SEPARATOR)
    except ValueError:
        reason_raw = f'missing separator "{SEPARATOR}"'
        reason_fmt = f'missing separator "[warning]{SEPARATOR}[/warning]"'
        logger.warning(FMT_PARSE_ERROR.format(
            reason=reason_raw, file_path=file_path
        ))
        return None, ParseError(file_path, reason_fmt)
    authors = authors_part.split('_')
    number: Optional[str] = None
    if RE_NUMBER.match(authors[0]):
        number = authors[0]
        authors = authors[1:]
    if len(authors) == 0:
        reason_raw = 'no authors'
        reason_fmt = '[warning]no authors[/warning]'
        logger.warning(FMT_PARSE_ERROR.format(
            reason=reason_raw, file_path=file_path
        ))
        return None, ParseError(file_path, reason_fmt)
    if any(not RE_NAME.match(author) for author in authors):
        authors_joined = ', '.join(authors)
        reason_raw = f'non-name author in {authors_joined}'
        reason_fmt = f'non-name author in [warning]{authors_joined}[/warning]'
        logger.warning(FMT_PARSE_ERROR.format(
            reason=reason_raw, file_path=file_path
        ))
        return None, ParseError(file_path, reason_fmt)
    m = RE_MAIN.match(title)
    if not m:
        reason_raw = 'no year'
        reason_fmt = '[warning]no year[/warning]'
        logger.warning(FMT_PARSE_ERROR.format(
            reason=reason_raw, file_path=file_path
        ))
        return None, ParseError(file_path, reason_fmt)
    title = m.group(1)
    pub_type = []
    if RE_BOOK.findall(title):
        pub_type.append('book')
        title = RE_BOOK.sub('', title)
    if RE_SLIDES.findall(title):
        pub_type.append('slides')
        title = RE_SLIDES.sub('', title)
    if RE_SURVEY.findall(title):
        pub_type.append('survey')
        title = RE_SURVEY.sub('', title)
    if RE_THESIS.findall(title):
        pub_type.append('thesis')
        title = RE_THESIS.sub('', title)
    title = title.replace('_', ' - ')
    title = uncapword(title)
    title = RE_MULTISPACE.sub(' ', title)
    year = int(m.group(2)[-4:])
    bibtex = BibtexKey(authors[0].lower(), year, BibtexKey.title_word(title))
    try:
        BibtexKey.parse(str(bibtex))
    except Exception:
        reason_raw = f'invalid BibTex key {bibtex}'
        reason_fmt = f'invalid BibTex key [warning]{bibtex}[/warning]'
        logger.warning(FMT_PARSE_ERROR.format(
            reason=reason_raw, file_path=file_path
        ))
        return None, ParseError(file_path, reason_fmt)
    doi = None
    arxiv = None

    return (
        Paper(file_path, bibtex, title, authors, year, pub_type, tags, number, doi, arxiv),
        None
    )


def generate(paper: Paper, root=None, tags=None, suffix: str = 'pdf') -> str:
    authors = '_'.join(capword(author) if author != 'etAl' else author
                       for author in paper.authors)
    title = paper.title
    title = beautify_hyphen_compounds(title)
    title = beautify_contractions(title)
    title = title.replace(': ', '_ ')
    title = title.replace('-', '_ ')
    title = title.replace('?', ' ')
    title = RE_MULTISPACE.sub(' ', title)
    title = capword(title)
    if len(paper.pub_type) > 0:
        flags = '_' + '_'.join(paper.pub_type)
    else:
        flags = ''
    if paper.number:
        number = f'{paper.number}_'
    else:
        number = ''
    filename = f'{number}{authors}_-_{title}{flags}_{paper.year}.{suffix}'
    filename = RE_UNWANTED.sub('_', filename)
    filename = filename.lstrip('.')
    filename = unidecode(filename, errors='replace', replace_str='_')
    filename = RE_MULTIUNDER.sub('_', filename)
    tags = tags if tags else paper.tags
    path = os.path.join(*tags, filename)
    if root:
        path = os.path.join(root, path)
    return path
