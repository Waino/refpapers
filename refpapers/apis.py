from crossref.restful import Works  # type: ignore
from pathlib import Path
from typing import Optional, List
import arxiv  # type: ignore
import os

from refpapers.conf import Conf
from refpapers.schema import Paper, BibtexKey
from refpapers.utils import JsonFileCache


class CrossrefApi:
    def __init__(self, conf: Conf):
        self._works = Works()
        if conf.paths.api_cache:
            os.makedirs(conf.paths.api_cache, exist_ok=True)
            cache_dir = conf.paths.api_cache
        else:
            cache_dir = Path('/tmp')
        self._cache = JsonFileCache(cache_dir / 'crossref.jsonl')

    def metadata_from_doi(self, doi: str, path=None) -> Optional[Paper]:
        meta = self._fetch(doi)
        if not meta:
            return None
        title = ''.join(meta.get('title', []))
        subtitle = ''.join(meta.get('subtitle', []))
        if subtitle:
            title = f'{title} - {subtitle}'
        year = self._get_year(meta)
        authors = self._get_authors_family(meta)

        if len(authors) == 0:
            return None
        if not year:
            return None

        bibtex = BibtexKey(authors[0], year, BibtexKey.title_word(title))

        # FIXME: only extracts data needed for Paper. Bibtex output needs more.
        return Paper(
            path=path,
            bibtex=bibtex,
            title=title,
            authors=authors,
            year=year,
            pub_type=[],
            tags=[],
            number=None,
            doi=doi,
            arxiv=None
        )

    def _fetch(self, doi: str):
        """ Returns metadata or None if DOI not found """
        meta = self._cache.get(doi, lambda: self._works.doi(doi))
        return meta

    @staticmethod
    def _get_year(meta) -> Optional[int]:
        for key in ('published', 'issued', 'published-print', 'published-online'):
            try:
                return meta[key]['date-parts'][0][0]
            except KeyError:
                pass
        return None

    @staticmethod
    def _get_authors_family(meta) -> List[str]:
        result = []
        for author in meta['author']:
            result.append(author['family'])
        return result


class ArxivApi:
    def __init__(self, conf: Conf):
        if conf.paths.api_cache:
            os.makedirs(conf.paths.api_cache, exist_ok=True)
            cache_dir = conf.paths.api_cache
        else:
            cache_dir = Path('/tmp')
        self._cache = JsonFileCache(cache_dir / 'arxiv.jsonl')

    def metadata_from_id(self, id: str, path=None) -> Optional[Paper]:
        meta = self._fetch(id)

        title = meta.title
        year = meta.published.year
        authors = [author.name.split()[-1] for author in meta.authors]
        try:
            doi = meta.doi
        except AttributeError:
            doi = None

        bibtex = BibtexKey(authors[0], year, BibtexKey.title_word(title))

        return Paper(
            path=path,
            bibtex=bibtex,
            title=title,
            authors=authors,
            year=year,
            pub_type=[],
            tags=[],
            number=None,
            doi=doi,
            arxiv=id,
        )

    def _fetch(self, id: str):
        """ Returns metadata or None if id not found """

        def _uncached_fetch():
            try:
                results = arxiv.Search(id_list=[id]).results()
                return next(results)
            except Exception:
                return None

        meta = self._cache.get(id, _uncached_fetch)
        return meta
