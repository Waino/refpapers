.. _Configuration:

Configuration
=============

If you run refpapers without a configuration, it will ask for the information necessary to write a minimal config.
However, to use all the features of refpapers, you should edit the configuration file.

A full-featured example configuration file can be found in
`example_conf/conf.yml <https://github.com/Waino/refpapers/blob/master/example_conf/conf.yml>`_.

Git and git-annex
~~~~~~~~~~~~~~~~~

To enable git-annex, set :code:`use_git: True` and :code:`use_git_annex: True`.
The former speeds up indexing by using git to track when files in the data directory have changed,
and the second uses git-annex to synch files across machines.
It is not recommended to use git without git-annex, as pdfs tend to be quite big.

In order for git to track the files, you need to commit them into git (note that :code:`inbox` does this for you).
The option :code:`git_uncommitted` controls what to do for files that have not been commited:

* :code:`WARN`: prints a warning.
* :code:`IGNORE`: silently ignores the files when indexing.
* :code:`ADD`: sloppily indexes also uncommited files. This can in some cases cause the index to get out of synch.
  To fix, run :code:`refpapers index --full`.

Paths
~~~~~

The paths in which refpapers will look for papers or store its databases are defined in the section :code:`paths`.
In a typical setup, there are three main directories that you should be aware of

* **data**: The path to the directory where you keep your papers (PDFs). 
* **inbox**: The directory where you keep incoming papers until you run the inbox command.
  This should be separate from the above data directory. This directory is not defined in the config.
* **hidden dir**: :code:`~/.refpapers` a hidden dot-directory under your home directory. Typically contains:
    * index: "~/.refpapers/index".  The search database index.
    * log: "~/.refpapers/log".  Logfiles, if you wish to keep them.
    * api_cache: "~/.refpapers/api_cache".  Cache for metadata retrieved from web APIs, to avoid fetching the same metadata again.

Software
~~~~~~~~

You can define viewers and full-text extractors for any file types.
To support a custom file type, all you need to do is add it here.

For example, the following adds viewers for the file types :code:`*.pdf` and :code:`*.djvu`.
The latter will not have its fulltext indexed, because there is no extractor, but you can still search and view the files.

  .. code-block:: yaml

    viewers:
        pdf: "evince"
        djvu: "evince"
    extractors:
        pdf: "pdftotext -l 20"
        djvu: "None"

Extraction parameters
~~~~~~~~~~~~~~~~~~~~~

* fulltext_chars: controls how many characters from the beginning of the full-text to extract.
* ids_chars: controls how many characters from the beginning of the full-text to search for paper identifiers to use in APIs.
* extract_max_seconds: if full-text extraction takes longer than this, the file will be skipped in future indexings.
* max_authors: truncate the list of authors, by replacing the tail of the list with "etAl".
