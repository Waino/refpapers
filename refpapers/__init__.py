#!/usr/bin/env python
"""
refpapers - FIXME
"""
from refpapers.view import print_list, print_details
from refpapers.filesystem import yield_all_paths, parse
from refpapers.schema import Paper
from refpapers.search import index_data, search

__all__ = ['print_list', 'print_details', 'yield_all_paths', 'parse',
           'Paper', 'index_data', 'search']

__version__ = '0.0.1'
__author__ = 'Stig-Arne Gronroos'
__author_email__ = "stig-arne.gronroos@aalto.fi"
