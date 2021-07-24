============
Contributing
============

Contributions are welcome, and they are greatly appreciated! 

You can contribute in many ways:

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs at https://github.com/waino/refpapers/issues

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "bug"
and "help wanted" is open to whoever wants to implement a fix for it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

Write Documentation
~~~~~~~~~~~~~~~~~~~

refpapers could always use more documentation, whether as part of
the official docs, in docstrings, or even on the web in blog posts, articles,
and such.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue at
https://github.com/waino/refpapers/issues

If you are proposing a new feature:

* A pull request with an implementation of the feature is the best way. Even rough/partial implementations are welcome.
* If you propose a feature as an issue: Explain in detail how it would work.
  Keep the scope as narrow as possible, to make it easier to implement.

Get Started!
------------

Ready to contribute? Here's how to set up `refpapers` for local
development. Please note this documentation assumes you already have
`virtualenv` and `Git` installed and ready to go.

1. Fork the `refpapers` repo on GitHub.
2. Clone your fork locally:

   .. code-block:: bash

    $ cd path_for_the_repo
    $ git clone git@github.com:YOUR_NAME/refpapers.git


3. Install your local copy into a virtualenv.

   .. code-block:: bash

        $ virtualenv refpapers-env
        $ source refpapers-env/bin/activate
        $ pip install flit
        $ flit install --symlink


4. Create a branch for local development:

   .. code-block:: bash

        $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.


5. When you're done making changes, check that your changes pass the tests:
   `refpapers` uses
   pytest, you can run PyTest. Before you run pytest you should ensure all
   dependancies are installed:

   .. code-block:: bash

        $ pip install -r requirements_dev.txt
        $ mypy --install-types
        $ python -m pytest


6. If your contribution is a bug fix or new feature, you may want to add a test
   to the existing test suite. See section Add a New Test below for details.


7. Commit your changes and push your branch to GitHub:

   .. code-block:: bash

        $ git add .
        $ git commit -m "Your detailed description of why you made your changes."
        $ git push origin name-of-your-bugfix-or-feature


8. Submit a pull request through the GitHub website.


Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.

2. If the pull request adds functionality, the docs should be updated. Put your
   new functionality into a function with a docstring, and add the feature to
   the list in README.rst.

Add a New Test
--------------

When fixing a bug or adding features, it's good practice to add a test to
demonstrate your fix or new feature behaves as expected. These tests should
focus on one tiny bit of functionality and prove changes are correct.

To write and run your new test, follow these steps:

1. Add the new test to either an existing file under the `tests/` directory, or a new file.
   Focus your test on the specific bug or a small part of the new feature.


2. If you have already made changes to the code, stash your changes and confirm
   all your changes were stashed:

   .. code-block:: bash

        $ git stash
        $ git stash list


3. Run your test and confirm that your test fails. If your test does not fail,
   rewrite the test until it fails on the original code:

   .. code-block:: bash

        $ pytest ./tests


4. Proceed work on your bug fix or new feature or restore your changes. To
   restore your stashed changes and confirm their restoration:

   .. code-block:: bash

        $ git stash pop
        $ git stash list


5. Rerun your test and confirm that your test passes. If it passes,
   congratulations!

.. cookiecutter: https://github.com/waino/refpapers
.. virtualenv: https://virtualenv.pypa.io/en/stable/installation
.. git: https://git-scm.com/book/en/v2/Getting-Started-Installing-Git

