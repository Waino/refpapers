import delegator  # type: ignore
from pathlib import Path
from typing import Generator, Iterator, List, Tuple

from refpapers.logger import logger
from refpapers.schema import IndexingAction
from refpapers.utils import q


# main actions are A: add, M: modify, D: delete, (??: untracked)
# others: C: copied, R: renamed (not seeing this though, seeing D and A),
# T: type change, U: unmerged, X: unknown, B: pairing broken


def current_commit(gitdir: Path) -> str:
    result = delegator.run(f'git -C {q(gitdir)} rev-parse HEAD')
    if not result.return_code == 0:
        if "ambiguous argument 'HEAD': unknown revision" in result.err:
            return 'initial'
        raise Exception(f'failed {result} {result.err}')
    return result.out


def git_difftree(gitdir: Path, commit: str) -> List[IndexingAction]:
    """ Parses the git diff-tree command to retrieve changes between
    the last indexed commit and HEAD """
    result = delegator.run(f'git -C {q(gitdir)} diff-tree -r --name-status -z {commit} HEAD')
    if not result.return_code == 0:
        raise Exception(f'failed {result} {result.err}')
    fields = null_delimited(result.out)
    actions = list(parse_difftree(fields, gitdir))
    return actions


def null_delimited(output: str) -> Generator[str, None, None]:
    yield from output.split('\0')


def parse_difftree(fields: Iterator[str], gitdir: Path) -> Generator[IndexingAction, None, None]:
    try:
        while True:
            action = next(fields)
            path = gitdir / Path(next(fields))
            yield IndexingAction(action, path)
    except StopIteration:
        pass


def git_status(gitdir: Path) -> Tuple[List[IndexingAction], List[IndexingAction]]:
    """ Parses the git status command to retrieve staged and untracked changes """
    result = delegator.run(f'git -C {q(gitdir)} status --porcelain=1 --untracked-files')
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
            path = gitdir / Path(path_str)
            if action in ('M', 'A'):
                staged.append(IndexingAction(action, path))
            elif action == '??':
                untracked.append(IndexingAction(action, path))
            elif action == 'D':
                # ignoring uncommitted deletions
                pass
            elif action == 'R':
                from_path, to_path = path_str.split(' -> ', 1)
                staged.append(IndexingAction('D', gitdir / Path(from_path)))
                staged.append(IndexingAction('A', gitdir / Path(to_path)))
            else:
                logger.warning(f'Did not understand git status: "{line}"')
        except Exception:
            logger.warning(f'Did not understand git status: "{line}"')
    return staged, untracked


def git_annex_add(gitdir: Path, paper_path: Path):
    command = f'git -C {q(gitdir)} annex add {paper_path}'
    print(command)
    result = delegator.run(command)
    if not result.return_code == 0:
        raise Exception(f'failed {result} {result.err}')


def git_annex_sync(gitdir: Path):
    command = f'git -C {q(gitdir)} annex sync --content'
    print(command)
    result = delegator.run(command)
    if not result.return_code == 0:
        raise Exception(f'failed {result} {result.err}')
