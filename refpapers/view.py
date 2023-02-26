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
    'title.even': 'cyan',
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


def render_authors(authors: Tuple[str, ...], truncate=True) -> str:
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
    flags = ''.join(PUB_TYPE_FLAGS.get(pub_type, '') for pub_type in paper.pub_type)
    authors = render_authors(paper.authors)
    left = blending_columns(
        '•',
        Text(paper.bibtex.author, style='bib', no_wrap=True)
    )
    mid = Text(str(paper.bibtex.year), style='year')
    right = blending_columns(
        Text(paper.bibtex.word, style='bib', no_wrap=True),
        flags
    )
    grid.add_row(left, mid, right, ' ', authors)
    grid.add_row('', '', '', ' ', Text(paper.title, style='title.even'))


def print_list_section(papers: Iterable[Paper], left_width: int, right_width: int) -> None:
    grid = Table.grid(expand=True)
    grid.add_column(width=left_width)           # left: bibauthor
    grid.add_column(min_width=4, max_width=4)   # mid: year
    grid.add_column(min_width=right_width)      # right: bibword, flags
    grid.add_column(max_width=1)                # padding
    grid.add_column(ratio=6)                    # authors / title
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
    longest_author = max(len(paper.bibtex.author) for paper in papers)
    longest_bibword = max(len(paper.bibtex.word) for paper in papers)
    left_width = max(12, longest_author + 3)
    right_width = longest_bibword + 2 + len('Pres')
    if grouped:
        for key, group in sorted_groups(papers, grouped):
            print_section_heading(key, grouped)
            print_list_section(group, left_width, right_width)
    else:
        print_list_section(papers, left_width, right_width)


def print_details(paper: Paper) -> None:
    print_section_heading(paper.title, 'title')
    if len(str(paper.path)) >= console.size.width:
        console.print(Text(str(paper.path), style='path', overflow='ignore'), crop=False)
    else:
        console.print(Text(str(paper.path), style='path', justify='right'))
    grid = Table.grid(expand=True)
    grid.add_column(min_width=35, max_width=50)
    grid.add_column(ratio=1)
    grid.add_row(
        '  ' + render_bibtex(paper.bibtex),
        render_authors(paper.authors, truncate=False),
    )
    tags_and_ids = ' / '.join(paper.tags)
    if paper.doi or paper.arxiv:
        doi = f'DOI: {paper.doi}' if paper.doi else ''
        arxiv = f'arXiv:{paper.arxiv}' if paper.arxiv else ''
        joiner = '\t\t' if paper.doi and paper.arxiv else ''
        tags_and_ids += f'    {doi}{joiner}{arxiv}'
    grid.add_row(
        ', '.join(paper.pub_type),
        tags_and_ids,
    )
    console.print(grid)


def expand_choice(query: str, choices: Dict[str, str]) -> Optional[str]:
    if query in choices:
        # keys have priority
        return choices[query]
    matches = [choice for choice in choices.values() if query in choice]
    if len(matches) == 1:
        # accept any unique substring
        return matches[0]
    matches = [choice for choice in matches if choice.startswith(query)]
    if len(matches) == 1:
        # accept a unique query even if it occurs as a substring later
        return matches[0]
    # otherwise too ambiguous
    return None


def question(prompt_str: str, choices: Union[List[str], Dict[str, str]]) -> Optional[str]:
    if isinstance(choices, list):
        assert len(set(choice[0] for choice in choices)) == len(choices), \
            'Choices must have unique first chars'
        choices_dict: Dict[str, str] = {choice[0]: choice for choice in choices}
        choices_list = choices
    else:
        for key in choices.keys():
            assert len(key) == 1, f'Choice keys must be single characters, got "{key}"'
        choices_dict = choices
        choices_list = list(choices.values())
    choice_texts = []
    for key, choice in choices_dict.items():
        choice_texts.append(choice.replace(key, f'[choice]({key})[/choice]', 1))
    choice_texts_flat = ', '.join(choice_texts)
    text = f'[prompt]{prompt_str}:[/prompt] {choice_texts_flat}? '
    completer = WordCompleter(choices_list)
    prefix = prompt(text, completer=completer)
    expanded = expand_choice(prefix, choices_dict)
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
    console.print(f'[{phase.lower()}]{phase:10}[/{phase.lower()}] [action]{expanded:10}[/action] {ia.paper}')


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
    print('\n')
    console.rule(f'[rule.line]─ [heading]Head of {path}[/heading]', align='left')
    for line in fulltext:
        print(line)
    console.rule()
