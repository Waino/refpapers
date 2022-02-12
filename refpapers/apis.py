from abc import ABC, abstractmethod
from crossref.restful import Works  # type: ignore
from pathlib import Path
from scholarly import scholarly, ProxyGenerator  # type: ignore
from typing import Optional, List, Dict, Any
import arxiv  # type: ignore
import os

from refpapers.conf import Conf
from refpapers.schema import Paper, BibtexKey
from refpapers.utils import JsonFileCache


def paper_from_metadata(meta: Dict[str, Any], path: Path, max_authors: int = -1) -> Paper:
    authors = meta['authors']
    if max_authors and max_authors > 1:
        # replace too many authors with etAl
        if len(authors) > max_authors:
            authors = authors[:(max_authors - 1)] + ['etAl']
    bibtex = BibtexKey(authors[0].lower(), meta['year'], BibtexKey.title_word(meta['title']))
    return Paper(
        path=path,
        bibtex=bibtex,
        title=meta['title'],
        authors=authors,
        year=meta['year'],
        pub_type=[],
        tags=[],
        number=None,
        doi=None,
        arxiv=None,
    )


class CachedApi(ABC):
    def _init_cache(self, conf: Conf, name: str):
        if conf.paths.api_cache:
            os.makedirs(conf.paths.api_cache, exist_ok=True)
            cache_dir = conf.paths.api_cache
        else:
            cache_dir = Path('/tmp')
        return JsonFileCache(
            cache_dir / f'{name}.jsonl',
            hit_func=self._cache_hit
        )

    def _tags_from_path(self, file_path: Path) -> List[str]:
        dir_path, file_name = os.path.split(file_path)
        tags = dir_path.split(os.path.sep)
        return tags

    def _cache_hit(self, key):
        print(f'Using cached metadata for "{key}"')

    @abstractmethod
    def _fetch(self, id: str) -> Optional[Dict[str, Any]]:
        pass


class CrossrefApi(CachedApi):
    def __init__(self, conf: Conf):
        self._conf = conf
        self._works = Works()
        self._cache = self._init_cache(conf, 'crossref')

    def paper_from_doi(self, doi: str, path=None) -> Optional[Paper]:
        meta = self._cache.get(doi, self._fetch)
        if not meta:
            return None
        return paper_from_metadata(meta, path, self._conf.max_authors)

    def _fetch(self, doi: str) -> Optional[Dict[str, Any]]:
        """ Returns metadata or None if DOI not found """
        result = self._works.doi(doi)
        title = ''.join(result.get('title', []))
        subtitle = ''.join(result.get('subtitle', []))
        if subtitle:
            title = f'{title} - {subtitle}'
        year = self._get_year(result)
        authors = self._get_authors_family(result)

        if len(authors) == 0:
            return None
        if not year:
            return None

        # TODO: only extracts data needed for Paper. Bibtex output needs more.
        return {
            'title': title,
            'year': year,
            'authors': authors,
            'doi': doi,
        }

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
        for author in meta['authors']:
            result.append(author['family'])
        return result


class ArxivApi(CachedApi):
    def __init__(self, conf: Conf):
        self._conf = conf
        self._cache = self._init_cache(conf, 'arxiv')

    def paper_from_id(self, id: str, path=None) -> Optional[Paper]:
        if id.startswith('arXiv:'):
            id = id.replace('arXiv:', '', 1)
        meta = self._cache.get(id, self._fetch)
        if not meta:
            return None
        return paper_from_metadata(meta, path, self._conf.max_authors)

    def _fetch(self, id: str) -> Optional[Dict[str, Any]]:
        """ Returns metadata or None if id not found """
        try:
            results = arxiv.Search(id_list=[id]).results()
            result = next(results)
            title = result.title
            year = result.published.year
            authors = [author.name.split()[-1] for author in result.authors]
            try:
                doi = result.doi
            except AttributeError:
                doi = None
            return {
                'title': title,
                'year': year,
                'authors': authors,
                'doi': doi,
                'arxiv': id,
            }
        except Exception:
            return None


class ScholarApi(CachedApi):
    def __init__(self, conf: Conf):
        self._conf = conf
        self._cache = self._init_cache(conf, 'scholar')
        self._proxy_setup()

    def paper_from_title(self, title: str, path=None) -> Optional[Paper]:
        meta = self._cache.get(title, self._fetch)
        if not meta:
            return None
        return paper_from_metadata(meta, path, self._conf.max_authors)

    def _proxy_setup(self):
        pg = ProxyGenerator()
        pg.FreeProxies()
        scholarly.use_proxy(pg)

    def _fetch(self, title: str) -> Optional[Dict[str, Any]]:
        """ Returns metadata or None if id not found """
        try:
            results = scholarly.search_pubs(title)
            result = next(results)
            title = result['bib']['title']
            year = int(result['bib']['pub_year'])
            authors = [author.split()[-1] for author in result['bib']['author']]
            url = result.get('eprint_url', None)

            if not all((title, year, authors)):
                return None
            return {
                'title': title,
                'year': year,
                'authors': authors,
                'url': url,
            }
        except Exception:
            return None
