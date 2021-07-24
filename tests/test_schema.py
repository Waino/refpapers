import pytest

from refpapers.schema import BibtexKey


@pytest.mark.parametrize(
    'inp,author,year,word',
    [
        ('foo2021bar', 'foo', 2021, 'bar'),
        ('a1000b', 'a', 1000, 'b'),
        ('hyphen-name1024multiWord', 'hyphen-name', 1024, 'multiWord'),
        ('aa9999word2profit', 'aa', 9999, 'word2profit'),
    ]
)
def test_bibtexkey(inp, author, year, word):
    bibtex = BibtexKey.parse(inp)
    assert bibtex.author == author
    assert bibtex.year == year
    assert bibtex.word == word
    assert str(bibtex) == inp


@pytest.mark.parametrize(
    'inp',
    [
        'foobar',
        'author2021',
        '2021foo',
        '1900',
    ]
)
def test_bibtexkey_invalid(inp):
    with pytest.raises(ValueError):
        BibtexKey.parse(inp)
