"""Command line interface for refpapers."""

import click
import delegator  # type: ignore
import os
from pathlib import Path
from typing import List, Iterable

from refpapers.conf import ensure_conf, load_conf, Conf, GitNew, DEFAULT_CONFDIR
from refpapers.filesystem import yield_actions, parse, apply_all_filters
from refpapers.git import current_commit, git_difftree, git_status
from refpapers.schema import Paper, IndexingAction, SCHEMA_VERSION
from refpapers.search import index_data, search
from refpapers.view import (
    print_details,
    print_git_indexingaction,
    print_list,
    print_section_heading,
    question,
    console,
)


@click.group()
def cli() -> None:
    pass


@cli.command(help='Refresh the search index')
@click.option('--full', is_flag=True,
              help='Perform a full indexing, as opposed to incremental.')
@click.option('--confdir', type=Path, default=DEFAULT_CONFDIR,
              help='Path to directory containing conf.yml and stored state.'
              f' Default: {DEFAULT_CONFDIR}')
def index(full: bool, confdir: Path) -> None:
    ensure_conf(confdir)
    conf, storedstate, decisions = load_conf(confdir)
    if not full:
        existing_schema_version = storedstate.read('schema_version')
        if existing_schema_version is None:
            console.print('[status]First indexing, performing full indexing[/status]')
            full = True
        elif existing_schema_version != SCHEMA_VERSION:
            console.print('[status]Existing index uses different schema version, performing full indexing[/status]')
            full = True
    if not full and not conf.use_git:
        console.print('[status]Not configured to use git, performing full indexing[/status]')
        full = True
    if not full:
        commit = storedstate.read('last_indexed_commit')
        if not commit:
            console.print('[status]No recorded git commit, performing full indexing[/status]')
            full = True

    if full:
        actions = list(yield_actions(conf.paths.data, conf, decisions))
    else:
        console.print(f'[status]Performing incremental indexing from commit {commit}')
        actions = git_difftree(conf.paths.data, commit)
        if not (conf.git_uncommitted == GitNew.IGNORE and conf.git_untracked == GitNew.IGNORE):
            staged: List[IndexingAction]
            untracked: List[IndexingAction]
            staged, untracked = git_status(conf.paths.data)
            staged = list(apply_all_filters(staged, conf, decisions))
            untracked = list(apply_all_filters(untracked, conf, decisions))

            if conf.git_uncommitted == GitNew.WARN:
                for ia in staged:
                    print_git_indexingaction(ia, 'STAGED')
            elif conf.git_uncommitted == GitNew.ADD:
                # add staged actions to index
                actions.extend(staged)

            if conf.git_untracked == GitNew.WARN:
                for ia in untracked:
                    print_git_indexingaction(ia, 'UNTRACKED')
                pass
            elif conf.git_untracked == GitNew.ADD:
                # add untracked actions to index
                for ia in untracked:
                    # convert '??' to 'A'
                    actions.append(IndexingAction('A', ia.paper))

        actions = list(apply_all_filters(actions, conf, decisions))

    papers = []
    for ia in actions:
        paper = parse(ia.path, conf.paths.data)
        if not paper:
            continue
        papers.append(IndexingAction(ia.action, paper))

    if len(papers) == 0:
        console.print('[status]Up to date, nothing to index[/status]')
    else:
        index_data(papers, full=full, conf=conf, decisions=decisions)
        storedstate.write('schema_version', SCHEMA_VERSION)

    if conf.use_git:
        commit = current_commit(conf.paths.data)
        storedstate.write('last_indexed_commit', commit)


@cli.command(name='search', help='Search for papers')
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


@cli.command(help='Show details of one paper')
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


@cli.command(name='open', help='Open one paper in viewer')
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
    _, ending = os.path.splitext(path)
    viewer = conf.software.get_viewer(ending)
    delegator.run(f'{viewer} {path}', block=False)


@cli.command(help='Check for data issues')
@click.option('--confdir', type=Path, default=DEFAULT_CONFDIR,
              help='Path to directory containing conf.yml and stored state.'
              f' Default: {DEFAULT_CONFDIR}')
def check(confdir: Path) -> None:
    ensure_conf(confdir)
    conf, storedstate, decisions = load_conf(confdir)
    actions = yield_actions(conf.paths.data, conf, decisions)

    print_section_heading('Filename syntax')
    console.print(
        'Checking that filenames follow the parser format.'
        ' To avoid seeing these errors again,'
        ' either rename the file and choose [choice]ok[/choice],'
        ' or [choice]ignore[/choice] it in the future.'
    )
    for ia in actions:
        path = ia.path
        paper = parse(path, conf.paths.data)
        if paper is None:
            choice = question(
                '?',
                ['ok', 'ignore it in the future', 'quit'])
            if choice == 'ignore it in the future':
                decisions.add(decisions.IGNORE, path)
            if choice == 'quit':
                break
    decisions.write()


if __name__ == '__main__':
    cli()
