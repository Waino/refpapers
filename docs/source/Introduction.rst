.. _Introduction:

Introduction
============

Motivation
~~~~~~~~~~
* Research involves reading a large number of scientific papers, and being able to later refer back to what you have read.
  Each time searching again in online databases or search engines is cumbersome,
  and unless remembering the exact title, you are likely to find new papers instead of the one you read previously.
* Keeping a personal database of the papers you read solves this problem.
  Such a collection grows rapidly, necessitating a performant local search engine.

File names as source of truth
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Refpapers uses the files themselves as a source of truth.
  Metadata, such as authors, title, and publication year are encoded in the filename.
  Full text is extracted from the file contents.
* For performance reasons, the data is indexed into a whoosh database.
  However, the database is only a cache: All the data is stored directly in the file.
* Using the file as a source of truth is useful in several ways:
    * If you send pdf files to other people or to yourself on machines without refpapers installed,
      your files will be systematically named with all the information you need.
    * You can choose to stop using refpapers, and the work you put into curating your collection will not be wasted.

Refpapers is opinionated
~~~~~~~~~~~~~~~~~~~~~~~~

* The naming scheme is fixed: The basic pattern is :code:`FirstAuthor_SecondAuthor_-_PaperTitle_0000.pdf`.
  The main fields are given in a fixed order, and the separator is mandatory.
  However, you don't need to write this format yourself: the automatic renaming tool takes care of it for you.
* Bibtex keys are in the form :code:`surname0000word`,
  with the surname of the first author, year, and the first word of the title (excluding stopwords).
* If you like, other naming formats that encode the same information could be supported.
  All the code for implementing this is in :code:`filesystem.py`. Pull requests are welcome!

Features
--------

* Powerful **full-text search**.
* **Fast**, even with a large collection of papers.
* Use **git-annex** to track newly added papers to speed up indexing (optional).
* Automatically **retrieve metadata** from several APIs: ArXiv, crossref, Google Scholar.
* Userfriendly **autocomplete** when manually entering metadata.
* **Configurable**. Can support any document format, if you provide a tool to extract plain text. 

Planned features
~~~~~~~~~~~~~~~~

* BibTeX integration.
* Improved data quality check, e.g. deduplication.

Features that will not be implemented
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Built-in synch:** refpapers is designed to work well together with git-annex.
  To synch your papers between multiple machines, you should use git-annex.

Alternatives
------------

* **papers** https://github.com/perrette/papers . Similar renaming functionality and API integrations. BibTeX integration.
* **zotero** https://www.zotero.org/ . A feature-rich GUI tool.
* **mendeley** https://www.mendeley.com/ . A proprietary tool, owned by Elsevier.


Acknowledgements
----------------

Thank you to arXiv for use of its open access interoperability.

Citing
------

If you find refpapers to be useful when writing your thesis or other scientific publications, please consider acknowledgeing it

  .. code-block:: bibtex

    @misc{refpapers,
        title={Refpapers: Lightweight command-line tool to manage bibliography},
        author={Grönroos, Stig-Arne},
        year={2022},
        note={\url{https://github.com/Waino/refpapers}},
    }
