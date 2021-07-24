import pytest
import yaml
import pathlib
from io import StringIO
from mock import patch

from refpapers.conf import Conf, Decisions

MINIMAL_YAML = """
paths:
    index: /tmp/index
    data: /tmp/data
"""

STANDARD_YAML = """
fulltext_chars: 300000
extract_max_seconds: 1.0
use_git: True
git_uncommitted: "WARN"
paths:
    index: "/path/to/index"
    data: "/path/to/data"
software:
    viewers:
        pdf: "evince"
        djvu: "evince"
    extractors:
        pdf: "pdftotext -l 20"
        djvu: "None"
"""


def test_minimal_conf():
    d = yaml.safe_load(MINIMAL_YAML)
    conf = Conf(**d)
    assert 'pdf' in conf.all_endings()


def test_standard_conf():
    d = yaml.safe_load(STANDARD_YAML)
    conf = Conf(**d)
    assert 'pdf' in conf.all_endings()
    assert conf.software.get_viewer('pdf') == 'evince'
    assert conf.software.get_viewer('.pdf') == 'evince'
    with pytest.raises(ValueError):
        conf.software.get_viewer('no_such_file_ending')
    assert conf.software.get_extractor('pdf') == 'pdftotext -l 20'
    assert conf.software.get_extractor('.pdf') == 'pdftotext -l 20'
    assert conf.software.get_extractor('no_such_file_ending') == 'pdftotext'


def mock_exists(path: pathlib.Path):
    return str(path) == '/tmp/test_decisions/decisions'


def test_decisions():
    with patch('pathlib.Path', autospec=True) as MockPath, \
         patch('os.replace') as MockReplace:
        MockPath.return_value.exists = mock_exists
        MockPath.return_value.open = StringIO
        decisions = Decisions(pathlib.Path('/tmp/test_decisions'))
        assert len(list(decisions.get())) == 0
        decisions.add('IGNORE', 'ign')
        decisions.write()
        decisions._path.exists.assert_called()
        decisions._path.open.assert_called()
        MockReplace.assert_called_with(decisions._tmp_path, decisions._path)
        # TODO: check contents of written mock
