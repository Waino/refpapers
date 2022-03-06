.. _Installing:

Installing
==========

Installing from PyPI
--------------------

Installing from PyPI using pip is the recommended way.

  .. code-block:: bash

    pip install refpapers

Depenencies (not including those automatically installed from pypi)

* Python 3
* pdftotext (from poppler-utils, Ubuntu: sudo apt install poppler-utils)


Installing from source
----------------------

Alternatively, you can install from source using flit

  .. code-block:: bash

    pip install flit
    git clone https://github.com/Waino/refpapers.git
    cd refpapers
    flit install --symlink
