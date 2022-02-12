import delegator  # type: ignore
import os
from pathlib import Path

from refpapers.conf import Conf
from refpapers.utils import q


def open_in_viewer(path: Path, conf: Conf):
    _, ending = os.path.splitext(path)
    if not ending:
        print(f'Unable to determine ending of path "{path}"')
        return
    viewer = conf.software.get_viewer(ending)
    delegator.run(f'{viewer} {q(path)}', block=False)
