#!/usr/bin/env python
"""
refpapers - Manage and search bibliography from the command line
"""
from refpapers.refpapers import cli
from refpapers.view import print_list, print_details
from refpapers.filesystem import yield_all_paths, parse
from refpapers.schema import Paper
from refpapers.search import index_data, search

__all__ = ['print_list', 'print_details', 'yield_all_paths', 'parse',
           'Paper', 'index_data', 'search', 'cli']

__version__ = '1.0.0'
__author__ = 'Stig-Arne Gronroos'
__author_email__ = "stig.gronroos@gmail.com"
