import prompt_toolkit
import sys
from enum import Enum
from itertools import groupby
from pathlib import Path
from prompt_toolkit import HTML
from prompt_toolkit.completion import Completer, WordCompleter
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from typing import List, Iterable, Union, Optional, Tuple, Dict

from refpapers.schema import Paper, BibtexKey, IndexingAction

Renderable = Union[str, Text]

MAX_LEN_AUTHORS = 50


def to_prompt_toolkit(val):
    bold = 'bold ' in val
    dim = not bold and 'dim ' in val
    val = val.replace('bold ', '').replace('dim ', '').strip()

    out_bold = 'bold ' if bold else ''
    out_bright = 'bright' if not dim else ''
    if val == 'white':
        out_bright = ''
    return f'{out_bold}ansi{out_bright}{val}'


THEME = {
    'authors': 'bold black',
    'authors.first': 'white',
    'bib': 'dim cyan',
    'year': 'bold white',
    'title.even': 'white',
    'title.odd': 'bold black',
    'thesis': 'red',
    'survey': 'bold white',
    'heading': 'bold cyan',
    'path': 'bold black',
    'prompt': 'bold white',
    'status': 'bold black',
    'status.hi': 'white',
    'choice': 'red',
    'staged': 'red',
    'untracked': 'yellow',
    'action': 'bold white',
    'warning': 'bold red',
    'rule.line': 'dim cyan',
}
console = Console(theme=Theme(THEME))
prompt_toolkit_style = Style.from_dict({
    key: to_prompt_toolkit(val)
    for key, val in THEME.items()
})

PUB_TYPE_FLAGS = {
    'book': 'B',
    'slides': 'Pres',
    'survey': '[survey]S[/survey]',
    'thesis': '[thesis]T[/thesis]',
}


def to_html(rich_str: str) -> HTML:
    for tag, _ in THEME.items():
        rich_str = rich_str.replace(f'[{tag}]', f'<{tag}>')
        rich_str = rich_str.replace(f'[/{tag}]', f'</{tag}>')
    return HTML(rich_str)


def blending_columns(left: Renderable, right: Renderable) -> Table:
    """ Produces a single renderable
    that allows two columns to blend into each other """
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(max_width=2)
    grid.add_column(justify="right")
    grid.add_row(left, '  ', right)
    return grid


def render_authors(authors: List[str], truncate=True) -> str:
    out = ['[authors.first]{}[/authors.first]'.format(authors[0])]
    if len(authors) > 1:
        out.append('[authors], ')
        if truncate and len(', '.join(authors)) > MAX_LEN_AUTHORS:
            out.append('etAl')
        else:
            out.append(', '.join(authors[1:]))
    return ''.join(out)


def render_bibtex(bibtex: BibtexKey) -> str:
    return f'[bib]{bibtex.author}[/bib][year]{bibtex.year}[/year][bib]{bibtex.word}[/bib]'


def render_list_item(paper: Paper, i: int, grid: Table) -> None:
    even = 'even' if i % 2 == 0 else 'odd'
    flags = ''.join(PUB_TYPE_FLAGS.get(pub_type, '') for pub_type in paper.pub_type)
    authors = render_authors(paper.authors)
    left = blending_columns(
        authors,
        Text(paper.bibtex.author, style='bib', no_wrap=True)
    )
    mid = Text(str(paper.bibtex.year), style='year')
    right = blending_columns(
        Text(paper.bibtex.word, style='bib', no_wrap=True),
        flags
    )
    grid.add_row(left, mid, right, ' ', Text(paper.title, style=f'title.{even}'))


def print_list_section(papers: Iterable[Paper], right_width: int) -> None:
    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)                    # left: authors, bibauthor
    grid.add_column(min_width=4, max_width=4)   # mid: year
    grid.add_column(min_width=right_width)      # right: bibword, flags
    grid.add_column(max_width=1)                # padding
    grid.add_column(ratio=2)                    # title
    for (i, paper) in enumerate(papers):
        render_list_item(paper, i, grid)
    console.print(grid)


def print_section_heading(heading: Union[str, Iterable[str]], field: str = None) -> None:
    if field == 'tags':
        heading = ' / '.join(heading)
    console.rule(f'[rule.line]─ [heading]{heading}[/heading]', align='left')


def sorted_groups(papers: List[Paper], grouping_key) -> List[Tuple[str, List[Paper]]]:
    ranked_papers = sorted(enumerate(papers), key=lambda x: x[1].__getattribute__(grouping_key))
    grouped = groupby(ranked_papers, key=lambda x: x[1].__getattribute__(grouping_key))
    grouped_dict: Dict[str, List[Paper]] = {}
    group_scores: List[Tuple[float, str]] = []
    for key, ranked_group in grouped:
        key = tuple(key)
        group_ranks, group_papers = zip(*ranked_group)
        # the group score combines the best rank and the average rank
        group_score = min(group_ranks) + (sum(group_ranks) / len(group_ranks))
        group_scores.append((group_score, key))
        grouped_dict[key] = list(group_papers)
    result: List[Tuple[str, List[Paper]]] = []
    for group_score, key in sorted(group_scores):
        result.append((key, grouped_dict[key]))
    return result


def print_list(papers: List[Paper], grouped=None) -> None:
    if len(papers) == 0:
        return
    longest_bibword = max(len(paper.bibtex.word) for paper in papers)
    right_width = longest_bibword + 2 + len('Pres')
    if grouped:
        for key, group in sorted_groups(papers, grouped):
            print_section_heading(key, grouped)
            print_list_section(group, right_width)
    else:
        print_list_section(papers, right_width)


def print_details(paper: Paper) -> None:
    print_section_heading(paper.title, 'title')
    if len(str(paper.path)) >= console.size.width:
        console.print(Text(str(paper.path), style='path', overflow='ignore'), crop=False)
    else:
        console.print(Text(str(paper.path), style='path', justify='right'))
    grid = Table.grid(expand=True)
    grid.add_column(max_width=2)    # indent
    grid.add_column(ratio=4)        # bibtex
    grid.add_column(ratio=10)       # authors
    grid.add_column(ratio=1)        # year
    grid.add_column(ratio=2)        # pub_type
    grid.add_column(ratio=5)        # paper.tags
    grid.add_row(
        '  ',
        render_bibtex(paper.bibtex),
        render_authors(paper.authors, truncate=False),
        str(paper.year),
        ', '.join(paper.pub_type),
        ' / '.join(paper.tags),
    )
    console.print(grid)
    if paper.doi or paper.arxiv:
        doi = f'DOI: {paper.doi}' if paper.doi else ''
        arxiv = f'arXiv:{paper.arxiv}' if paper.arxiv else ''
        joiner = '\t\t' if paper.doi and paper.arxiv else ''
        console.print(f'{doi}{joiner}{arxiv}')


def expand_choice(prefix: str, choices: List[str]) -> Optional[str]:
    for choice in choices:
        if choice.startswith(prefix):
            return choice
    return None


def question(prompt_str: str, choices: List[str]) -> Optional[str]:
    assert len(set(choice[0] for choice in choices)) == len(choices), \
        'Choices must have unique first chars'
    text = [f'[prompt]{prompt_str}:[/prompt]']
    for choice in choices:
        text.append(f' [choice]({choice[0]})[/choice]{choice[1:]}')
    text.append(' ? ')
    completer = WordCompleter(choices)
    prefix = prompt(''.join(text), completer=completer)
    expanded = expand_choice(prefix, choices)
    return expanded


def prompt(
    prompt_str: str, completer: Optional[Completer] = None, default: Optional[str] = None
) -> str:
    if sys.stdin.isatty():
        prompt_str = f'[prompt]{prompt_str}[/prompt]'
        default = default if default else ''
        return prompt_toolkit.prompt(
            to_html(prompt_str),
            completer=completer,
            default=default,
            style=prompt_toolkit_style,
        )
    else:
        # input is a non-interactive (e.g. pipe)
        return console.input(prompt_str)


def print_git_indexingaction(ia: IndexingAction, phase: str):
    action_map = {'A': 'added', 'M': 'modified', 'D': 'deleted', '??': 'untracked'}
    expanded = action_map.get(ia.action, ia.action)
    console.print(f'[{phase.lower()}]{phase}[/{phase.lower()}] [action]{expanded}[/action] {ia.paper}')


class LongTaskStatus(Enum):
    OK = 1
    WARN = 2
    FAIL = 3


class LongTask:
    """ A status tracker for long tasks that don't report intermediary results """
    OK = LongTaskStatus.OK
    WARN = LongTaskStatus.WARN
    FAIL = LongTaskStatus.FAIL
    _status_map = {
        LongTaskStatus.OK: Text.assemble(
            ('[', 'bold white'),
            ('OK', 'green'),
            (']', 'bold white'),
        ),
        LongTaskStatus.WARN: Text.assemble(
            ('[', 'bold white'),
            ('WARN', 'bold yellow'),
            (']', 'bold white'),
        ),
        LongTaskStatus.FAIL: Text.assemble(
            ('[', 'bold white'),
            ('FAIL', 'black on red'),
            (']', 'bold white'),
        ),
    }

    def __init__(self, message: Union[str, Text]):
        self.message = message
        self.status: Union[str, Text] = ''
        self._live = None

    def set_status(self, status: Union[str, Text, LongTaskStatus]):
        if isinstance(status, LongTaskStatus):
            self.status = self._status_map[status]
        else:
            self.status = status
        if self._live:
            self._live.update(self._render(), refresh=True)

    def _render(self):
        grid = Table.grid(expand=True)
        grid.add_column()
        grid.add_column(justify="right")
        grid.add_row(self.message, self.status)
        return grid

    def __enter__(self):
        self._live = Live(self._render(), auto_refresh=False).__enter__()
        return self

    def __exit__(self, *args, **kwargs):
        if not self.status:
            # If you didn't set a status before exit, then it failed
            self.set_status(LongTaskStatus.FAIL)
        else:
            # ensure that the correct status is shown
            self._live.update(self._render(), refresh=True)
        self._live.__exit__(*args, **kwargs)
        self._live = None


def print_fulltext(fulltext: List[str], path: Path) -> None:
    console.rule(f'[rule.line]─ [heading]Head of {path}[/heading]', align='left')
    for line in fulltext:
        print(line)
    console.rule()
