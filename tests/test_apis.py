import pytest
from pathlib import Path

from refpapers.schema import Paper, BibtexKey
from refpapers.apis import paper_from_metadata


@pytest.mark.parametrize(
    'inp,expected',
    [
        (
            {
                'authors': ['foo'],
                'year': 2022,
                'title': 'an example title here',
            },
            Paper(
                path=Path('.'),
                bibtex=BibtexKey(author='foo', year=2022, word='example'),
                title='an example title here',
                authors=['foo'],
                year=2022,
                pub_type=[],
                tags=[],
                number=None,
                doi=None,
                arxiv=None,
            ),
        ),
    ],
)
def test_paper_from_metadata(inp, expected):
    result = paper_from_metadata(inp, path=Path('.'))
    assert result == expected
