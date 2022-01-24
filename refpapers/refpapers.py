"""Command line interface for refpapers."""

import click
import logging
from pathlib import Path
from typing import Iterable

from refpapers.conf import ensure_conf, load_conf, Conf, DEFAULT_CONFDIR, AllCategories
from refpapers.doctypes import open_in_viewer
from refpapers.filesystem import yield_actions, parse
from refpapers.logger import ch
from refpapers.schema import Paper
from refpapers.search import index_data, search
from refpapers.view import (
    print_details,
    print_list,
    print_section_heading,
    question,
    console,
)
from refpapers.rename import AutoRenamer


class AliasedGroup(click.Group):

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx)
                   if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


@click.command(cls=AliasedGroup)
def cli() -> None:
    pass


@cli.command(help='Refresh the search index')  # type: ignore
@click.option('--full', is_flag=True,
              help='Perform a full indexing, as opposed to incremental.')
@click.option('--confdir', type=Path, default=DEFAULT_CONFDIR,
              help='Path to directory containing conf.yml and stored state.'
              f' Default: {DEFAULT_CONFDIR}')
def index(full: bool, confdir: Path) -> None:
    ensure_conf(confdir)
    conf, storedstate, decisions = load_conf(confdir)

    index_data(full, conf, storedstate, decisions)


@cli.command(name='search', help='Search for papers')  # type: ignore
@click.argument('query', type=str, nargs=-1)
@click.option('--nogroup', is_flag=True,
              help='Do not group by tags')
@click.option('--sort',
              type=click.Choice(Paper.__dataclass_fields__.keys()),  # type: ignore
              help='Sort by field (default: order of relevance)')
@click.option('--limit', type=int, default=10,
              help='Maximum number of results to show')
@click.option('--confdir', type=Path, default=DEFAULT_CONFDIR,
              help='Path to directory containing conf.yml and stored state.'
              f' Default: {DEFAULT_CONFDIR}')
def subcommand_search(query: str, nogroup: bool, sort: str, limit: int, confdir: Path):
    conf, storedstate, decisions = load_conf(confdir)
    query = ' '.join(query)
    papers = list(search(query, conf, decisions, limit=limit))
    if len(papers) == 0:
        print('No papers matched the query')
        return
    if sort:
        papers = sorted(papers, key=lambda x: x.__getattribute__(sort))
    if nogroup:
        print_list(papers)
    else:
        print_list(papers, 'tags')


@cli.command(help='Show details of one paper')  # type: ignore
@click.argument('query', type=str, nargs=-1)
@click.option('--confdir', type=Path, default=DEFAULT_CONFDIR,
              help='Path to directory containing conf.yml and stored state.'
              f' Default: {DEFAULT_CONFDIR}')
def one(query: str, confdir: Path) -> None:
    conf, storedstate, decisions = load_conf(confdir)
    query = ' '.join(query)
    papers = list(search(query, conf, decisions, limit=1, fields=['bibtex', 'authors', 'title']))
    if len(papers) > 0:
        print_details(papers[0])
    else:
        print('No papers matched the query')


@cli.command(name='open', help='Open one paper in viewer')  # type: ignore
@click.argument('query', type=str, nargs=-1)
@click.option('--confdir', type=Path, default=DEFAULT_CONFDIR,
              help='Path to directory containing conf.yml and stored state.'
              f' Default: {DEFAULT_CONFDIR}')
def subcommand_open(query: Iterable[str], confdir: Path) -> None:
    conf, storedstate, decisions = load_conf(confdir)
    conf = Conf.from_yaml(confdir / 'conf.yml')
    query = ' '.join(query)
    papers = list(search(query, conf, decisions, limit=1, fields=['bibtex', 'authors', 'title']))
    if len(papers) == 0:
        print('No papers matched the query')
        return
    path = papers[0].path
    open_in_viewer(path, conf)


@cli.command(help='Check for data issues')  # type: ignore
@click.option('--confdir', type=Path, default=DEFAULT_CONFDIR,
              help='Path to directory containing conf.yml and stored state.'
              f' Default: {DEFAULT_CONFDIR}')
def check(confdir: Path) -> None:
    ch.setLevel(logging.ERROR)
    ensure_conf(confdir)
    conf, storedstate, decisions = load_conf(confdir)
    actions = list(yield_actions(conf.paths.data, conf, decisions))

    print_section_heading('Filename syntax')
    console.print(
        'Checking that filenames follow the parser format.'
        ' To avoid seeing these errors again,'
        ' either rename the file and choose [choice]ok[/choice],'
        ' or [choice]ignore[/choice] it in the future.'
    )
    parse_results = [parse(ia.path, conf.paths.data) for ia in actions]
    errors = [error for paper, error in parse_results if error is not None]
    total = len(errors)
    console.print(f'[status]Detected {total} files with problems[/status]')
    for i, error in enumerate(errors):
        console.print(error.describe())
        path = error.path
        choice = question(
            f'({i + 1}/{total}) ?',
            ['ok', 'ignore it in the future', 'quit'])
        if choice == 'ignore it in the future':
            decisions.add(decisions.IGNORE, path)
        if choice == 'quit':
            break
    decisions.write()


@cli.command(help='Propose renaming file automatically')  # type: ignore
@click.argument('path', type=Path)
@click.option('--confdir', type=Path, default=DEFAULT_CONFDIR,
              help='Path to directory containing conf.yml and stored state.'
              f' Default: {DEFAULT_CONFDIR}')
def rename(path: Path, confdir: Path) -> None:
    conf, storedstate, decisions = load_conf(confdir)
    categories = AllCategories(conf).read()

    auto_renamer = AutoRenamer(conf, storedstate, decisions, categories)
    auto_renamer.rename(path)


@cli.command(help='Ingest files in inbox: auto-rename, commit, sync, index')  # type: ignore
@click.option('--open', is_flag=True,
              help='Open files in viewer before renaming.')
@click.option('--path', type=Path, default=Path('.'),
              help='Path to inbox (default: current working directory)')
@click.option('--confdir', type=Path, default=DEFAULT_CONFDIR,
              help='Path to directory containing conf.yml and stored state.'
              f' Default: {DEFAULT_CONFDIR}')
def inbox(open: bool, path: Path, confdir: Path) -> None:
    conf, storedstate, decisions = load_conf(confdir)
    categories = AllCategories(conf).read()

    auto_renamer = AutoRenamer(conf, storedstate, decisions, categories)
    auto_renamer.ingest_inbox(path, open_before_rename=open)


if __name__ == '__main__':
    cli()
