import delegator  # type: ignore
from pathlib import Path
from typing import Generator, Iterator, List, Tuple

from refpapers.logger import logger
from refpapers.schema import IndexingAction


# main actions are A: add, M: modify, D: delete, (??: untracked)
# others: C: copied, R: renamed (not seeing this though, seeing D and A),
# T: type change, U: unmerged, X: unknown, B: pairing broken


def current_commit(gitdir: Path) -> str:
    result = delegator.run(f'git -C {gitdir} rev-parse HEAD')
    if not result.return_code == 0:
        raise Exception(f'failed {result} {result.err}')
    return result.out


def git_difftree(gitdir: Path, commit: str) -> List[IndexingAction]:
    """ Parses the git diff-tree command to retrieve changes between
    the last indexed commit and HEAD """
    result = delegator.run(f'git -C {gitdir} diff-tree --name-status -z {commit} HEAD')
    if not result.return_code == 0:
        raise Exception(f'failed {result} {result.err}')
    fields = null_delimited(result.out)
    actions = list(parse_difftree(fields))
    return actions


def null_delimited(output: str) -> Generator[str, None, None]:
    yield from output.split('\0')


def parse_difftree(fields: Iterator[str]) -> Generator[IndexingAction, None, None]:
    try:
        while True:
            action = next(fields)
            path = Path(next(fields))
            yield IndexingAction(action, path)
    except StopIteration:
        pass


def git_status(gitdir: Path) -> Tuple[List[IndexingAction], List[IndexingAction]]:
    """ Parses the git status command to retrieve staged and untracked changes """
    result = delegator.run(f'git -C {gitdir} status --porcelain=1 --untracked-files')
    if not result.return_code == 0:
        raise Exception(f'failed {result} {result.err}')
    staged = []
    untracked = []
    for line in result.out.split('\n'):
        line = line.strip()
        if len(line) == 0:
            continue
        try:
            action, path_str = line.split(None, 1)
            path = Path(path_str)
            if action in ('M', 'A'):
                staged.append(IndexingAction(action, path))
            elif action == '??':
                untracked.append(IndexingAction(action, path))
            elif action == 'D':
                # ignoring uncommitted deletions
                pass
            else:
                logger.warning(f'Did not understand git status: "{line}"')
        except Exception:
            logger.warning(f'Did not understand git status: "{line}"')
    return staged, untracked
