import pytest
import yaml
from pathlib import Path

from refpapers.conf import Conf
from refpapers.filesystem import (
    ending_globs,
    keep_valid_endings,
    is_in_gitdir,
    uncapword,
    capword,
    parse,
    generate,
)
from refpapers.schema import IndexingAction
from .test_conf import STANDARD_YAML


def test_ending_globs():
    d = yaml.safe_load(STANDARD_YAML)
    conf = Conf(**d)
    result = ending_globs(conf)
    assert len(result) >= 0
    assert all(glob.startswith('*.') for glob in result)


def test_keep_valid_endings():
    inp = [
        IndexingAction('A', Path('foo.pdf')),
        IndexingAction('A', Path('foo.djvu')),
        IndexingAction('A', Path('foo.no_such_ending')),
        IndexingAction('D', Path('foo.exe')),
        IndexingAction('D', Path('bar.pdf')),
    ]
    expected = [
        IndexingAction('A', Path('foo.pdf')),
        IndexingAction('A', Path('foo.djvu')),
        IndexingAction('D', Path('bar.pdf')),
    ]
    d = yaml.safe_load(STANDARD_YAML)
    conf = Conf(**d)
    out = list(keep_valid_endings(inp, conf))
    assert out == expected


@pytest.mark.parametrize(
    'path,expected',
    [
        ('foo', False),
        ('foo/bar', False),
        ('foo/git', False),
        ('foo/git/bar', False),
        ('foo/.git', True),
        ('foo/.git/bar', True),
    ]
)
def test_is_in_gitdir(path, expected):
    assert is_in_gitdir(Path(path)) is expected


@pytest.mark.parametrize(
    'inp,expected',
    [
        ('lower', 'lower'),
        ('Upper', 'Upper'),
        ('FooBar', 'Foo bar'),
        ('MultiWordFoo', 'Multi word foo'),
        ('AWord', 'A word'),
        ('InAMiddle', 'In a middle'),
        ('HTML', 'HTML'),
    ]
)
def test_uncapword(inp, expected):
    assert uncapword(inp) == expected


@pytest.mark.parametrize(
    'inp,expected',
    [
        ('single', 'Single'),
        ('foo bar', 'FooBar'),
        ('foo bar baz', 'FooBarBaz'),
        ('HTML', 'Html'),
        ('Sanchez-Cartagena', 'SanchezCartagena'),
    ]
)
def test_capword(inp, expected):
    assert capword(inp) == expected


@pytest.mark.parametrize(
    'path',
    [
        'r/nlp/machineTranslation/nmt/systems/Bojar_etAl_-_FindingsOfThe2017ConferenceOnMachineTranslation_Wmt17_2017.pdf',  # noqa: E501
        'r/machineLearning/activeLearning/Sener_Savarese_-_ActiveLearningForConvolutionalNeuralNetworks_ACoreSetApproach_2018.pdf',  # noqa: E501
        'r/machineLearning/deepNeuralNetworks/Cho_-_FoundationsAndAdvancesInDeepLearning_thesis_2014.pdf',
        'r/A_-_T_2021.pdf',
        'r/Author_-_Title_book_2021.pdf',
        'r/Author_-_Title_survey_2021.pdf',
        'r/05_Author_-_Title_slides_2021.pdf',
        # 'r/Author_-_Title_1000.djvu',     # TODO: currently always generates .pdf
    ]
)
def test_parse_generate(path):
    root = 'r'
    paper, error = parse(Path(path), root)
    out = generate(paper, root)
    assert out == path, f'{path}\n -> {paper}\n -> {out}'


@pytest.mark.parametrize(
    'path',
    [
        r'r/foo/no_separator_2021.pdf',
        r'r/foo/01_-_no_authors_2021.pdf',
        r'r/foo/2a1_foo_-_non_author_2021.pdf',
        r'r/foo/author_-_no_year.pdf',
    ]
)
def test_parse_errors(path):
    root = 'r'
    paper, error = parse(Path(path), root)
    assert paper is None
    assert error is not None


def test_suffix():
    root = 'r'
    assert parse(Path('r/A_-_T_2021.pdf'), root)[0].suffix == '.pdf'
    assert parse(Path('r/A_-_T_2021.djvu'), root)[0].suffix == '.djvu'


def test_path():
    root = 'r'
    path = Path('r/A_-_T_2021.pdf')
    paper, error = parse(path, root)

    ia_path = IndexingAction('A', path)
    ia_paper = IndexingAction('A', paper)
    assert ia_path.path == path
    assert ia_paper.path == path
    assert ia_path.path == ia_paper.path
