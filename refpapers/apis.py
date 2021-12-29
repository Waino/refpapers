from crossref.restful import Works  # type: ignore

from refpapers.schema import Paper, BibtexKey


class CrossrefApi:
    def __init__(self):
        self.works = Works()

    def metadata_from_doi(self, doi, path=None):
        meta = self._fetch(doi)
        title = ''.join(meta.get('title', []))
        subtitle = ''.join(meta.get('subtitle', []))
        if subtitle:
            title = f'{title} - {subtitle}'
        year = self._get_year(meta)
        authors = self._get_authors_family(meta)

        if len(authors) == 0:
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

    def _fetch(self, doi):
        # FIXME: cache the results
        meta = self.works.doi(doi)
        return meta

    @staticmethod
    def _get_year(meta):
        for key in ('published', 'issued', 'published-print', 'published-online'):
            try:
                return meta[key]['date-parts'][0][0]
            except KeyError:
                pass
        return None

    @staticmethod
    def _get_authors_family(meta):
        result = []
        for author in meta['author']:
            result.append(author['family'])
        return result
