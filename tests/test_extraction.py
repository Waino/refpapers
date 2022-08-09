import pytest
from pathlib import Path
from unittest.mock import MagicMock

from refpapers.search import remove_prefixes, extract_ids_from_fulltext


@pytest.mark.parametrize(
    'inp,expected',
    [
        ({'aaaa', 'aaa', 'aaaaa', 'baaa'}, {'aaaaa', 'baaa'}),
        ({'10.1145/3299869.3314036', '10.1145/3299869'}, {'10.1145/3299869.3314036'}),
        ({'1404.7828', '1404.7828v4'}, {'1404.7828v4'}),
    ]
)
def test_remove_prefixes(inp, expected):
    result = remove_prefixes(inp)
    assert result == expected


@pytest.mark.parametrize(
    'inp,expected_doi,expected_arxiv',
    [
        (
            'Foo bar baz doi: 10.1101/708206 quux',
            '10.1101/708206', None
        ),
        (
            'Mumble mumble stuff arXiv:2004.04002 also foo',
            None, '2004.04002',
        ),
        (
            'Mumble mumble stuff arXiv:2004.04002 but this version is arXiv:2004.04002v2',
            None, '2004.04002v2',
        ),
        (
            'This doi 10.1145/3299869. 3314036 gets chopped'
            ' while this doi 10.1145/3299869.3314036 is whole',
            '10.1145/3299869.3314036', None
        ),
        (
            'Both a doi 10.1145/3299869.3314036 and arXiv:2004.04002'
            ' although not for the same paper lol',
            '10.1145/3299869.3314036', '2004.04002'
        ),
    ]
)
def test_extract_ids_from_fulltext(inp, expected_doi, expected_arxiv):
    mock_conf = MagicMock(ids_chars=5000)
    result_doi, result_arxiv = extract_ids_from_fulltext(inp, Path('.'), mock_conf)
    assert result_doi == expected_doi
    assert result_arxiv == expected_arxiv
