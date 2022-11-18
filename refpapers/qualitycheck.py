import Levenshtein
import random
from typing import Sequence, Set, Tuple, List, Union
from whoosh import index, qparser  # type: ignore
from whoosh.sorting import MultiFacet, ScoreFacet, FieldFacet   # type: ignore

from refpapers.conf import Conf
from refpapers.schema import Paper, whoosh_schema
from refpapers.search import result_to_paper

MAX_YEAR_DIFF = 10


def normalize(text: str):
    text = text.replace(' ', '')
    text = text.replace('-', '')
    text = text.replace(':', '')
    text = text.lower()
    return text


def scaled_lev(a: str, b: str) -> float:
    max_len = max(3, max(len(a), len(b)) // 3)
    dist = Levenshtein.distance(a, b, score_cutoff=max_len)
    return dist / (max_len + 1.0)


def prefix_match(a: Sequence, b: Sequence) -> float:
    min_len = min(len(a), len(b))
    match_len = 0
    for ach, bch in zip(a, b):
        if ach != bch:
            break
        match_len += 1
    return 1.0 - (match_len / min_len)


def set_distance(a: set, b: set) -> float:
    union_size = len(a.union(b))
    if union_size == 0:
        return 0.0
    return 1.0 - (len(a.intersection(b)) / union_size)


def bibtex_distance(a: Paper, b: Paper) -> float:
    lev = scaled_lev(str(a.bibtex), str(b.bibtex))
    prefix = prefix_match(str(a.bibtex), str(b.bibtex))
    return min(lev, prefix)


def arxiv_distance(a: Paper, b: Paper) -> float:
    if a.arxiv is None:
        if b.arxiv is None:
            return 0.0
        else:
            return 0.5
    dist = prefix_match(str(a.arxiv), str(b.arxiv))
    return dist


def doi_distance(a: Paper, b: Paper) -> float:
    if a.doi is None:
        if b.doi is None:
            return 0.0
        else:
            return 1.0
    return prefix_match(str(a.doi), str(b.doi))


def author_distance(a: Paper, b: Paper) -> float:
    a_has_etal = any(author == 'etAl' for author in a.authors)
    b_has_etal = any(author == 'etAl' for author in b.authors)
    etal_match = (a_has_etal == b_has_etal)
    a_noetal = [author for author in a.authors if not author == 'etAl']
    b_noetal = [author for author in b.authors if not author == 'etAl']

    prefix = prefix_match(a_noetal, b_noetal)
    perm = set_distance(set(a_noetal), set(b_noetal))

    weighted_parts = [
        (1.0, 0 if etal_match else 1.0),
        (5.0, prefix),
        (2.0, perm),
    ]
    sum_of_weights = sum(w for (w, d) in weighted_parts)
    weighted = sum(w * d for (w, d) in weighted_parts) / sum_of_weights
    return weighted


def year_distance(a: Paper, b: Paper) -> float:
    year_diff = min(abs(a.year - b.year), MAX_YEAR_DIFF)
    return year_diff**2 / MAX_YEAR_DIFF**2


def title_distance(a: Paper, b: Paper) -> float:
    lev = scaled_lev(normalize(a.title), normalize(b.title))
    prefix = prefix_match(a.title, b.title)
    return min(lev, prefix)


def tag_distance(a: Paper, b: Paper) -> float:
    return set_distance(set(a.tags), set(b.tags))


def pub_type_distance(a: Paper, b: Paper) -> float:
    return set_distance(set(a.pub_type), set(b.pub_type))


def number_distance(a: Paper, b: Paper) -> float:
    if a.number is None and b.number is None:
        return 0.0
    if a.number == b.number:
        return 0.0
    return 1.0


def paper_distance(a: Paper, b: Paper) -> float:
    weighted_parts = [
        (1.0, bibtex_distance(a, b)),
        (3.0, title_distance(a, b)),
        (2.0, author_distance(a, b)),
        (1.0, year_distance(a, b)),
        (0.5, pub_type_distance(a, b)),
        (1.0, tag_distance(a, b)),
        (0.5, number_distance(a, b)),
        (0.5, arxiv_distance(a, b)),
        (0.5, doi_distance(a, b)),
    ]
    sum_of_weights = sum(w for (w, d) in weighted_parts)
    weighted = sum(w * d for (w, d) in weighted_parts) / sum_of_weights
    return weighted


def find_close_matches(query: Union[str, Paper], conf: Conf, limit=10, max_dist=0.35) -> Tuple[Paper, List[Paper]]:
    if isinstance(query, Paper):
        reference, candidates = more_like_paper(query, conf, limit)
    else:
        reference, candidates = more_like_query(query, conf, limit)
    # sort by custom distance measure
    candidates_with_distance = [(paper_distance(reference, candidate), candidate) for candidate in candidates]
    candidates_with_distance = sorted(candidates_with_distance, key=lambda x: x[0])
    # truncate list, filter high distances
    candidates_with_distance = candidates_with_distance[:limit]
    candidates_with_distance = [
        (dist, candidate) for (dist, candidate) in candidates_with_distance
        if dist <= max_dist
    ]
    return reference, [candidate for dist, candidate in candidates_with_distance]


def more_like_query(
    query: str, conf: Conf, limit=10,
) -> Tuple[Paper, Set[Paper]]:
    fields = ["bibtex", "authors", "title"]
    ix = index.open_dir(conf.paths.index)
    qp = qparser.MultifieldParser(fields, schema=whoosh_schema)
    q = qp.parse(query)
    # sort first by score, using as tiebreaker year
    # (can't break ties using first author in this scheme)
    sortedby = MultiFacet([
        ScoreFacet(),
        FieldFacet('year', reverse=True),
    ])

    out: Set[Paper] = set()
    with ix.searcher() as s:
        results = s.search(q, limit=1, sortedby=sortedby)
        if results.is_empty():
            raise Exception('No papers matched the query')
        reference = results[0]
        reference_paper = result_to_paper(reference)
        for field in fields:
            results = reference.more_like_this(field, top=limit)
            for result in results:
                paper = result_to_paper(result)
                out.add(paper)
        return reference_paper, out


def more_like_paper(
    paper: Paper, conf: Conf, limit=10,
) -> Tuple[Paper, Set[Paper]]:
    triples = set()
    for _ in range(3):
        title_words = paper.title.split()
        random.shuffle(title_words)
        while len(title_words) >= 3:
            triples.add(tuple(title_words[:3]))
            title_words = title_words[3:]
    queries = [
        ' '.join(f'title:{word}' for word in triple)
        for triple in triples
    ]
    queries.append(f'authors:{paper.authors[0]}')

    out: Set[Paper] = set()
    fields = ["bibtex", "authors", "title"]
    ix = index.open_dir(conf.paths.index)
    qp = qparser.MultifieldParser(fields, schema=whoosh_schema)
    with ix.searcher() as s:
        for query in queries:
            q = qp.parse(query)
            results = s.search(q, limit=limit)
            if results.is_empty():
                continue
            for result in results:
                result_paper = result_to_paper(result)
                out.add(result_paper)
    return paper, out
