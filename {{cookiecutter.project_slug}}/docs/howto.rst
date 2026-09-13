How To - Project Documentation
======================================================================

Get Started
----------------------------------------------------------------------

Documentation can be written as rst files in the `docs` directory at the root of the project.

{% if cookiecutter.use_docker == 'n' %}
To build and serve docs, use the command::

    uv run make livehtml

from inside that `docs` directory.
{% else %}
To build and serve docs, use the commands::

    docker compose -f docker-compose.docs.yml up

{% endif %}

Changes to the files in `docs`, and to the application code they document, are picked up and reloaded automatically.

`Sphinx <https://www.sphinx-doc.org/>`_ is the tool used to build documentation.

Docstrings to Documentation
----------------------------------------------------------------------

The sphinx extension `apidoc <https://www.sphinx-doc.org/en/master/man/sphinx-apidoc.html>`_ is used to automatically document code using signatures and docstrings.

Numpy or Google style docstrings will be picked up from project files and available for documentation. See the `Napoleon <https://sphinxcontrib-napoleon.readthedocs.io/en/latest/>`_ extension for details.

For an in-use example, see the `page source <_sources/users.rst.txt>`_ for :ref:`users`.

To compile all docstrings automatically into documentation source files, use the command:
    ::

        uv run make apidocs

{% if cookiecutter.use_docker == 'y' %}
This can be done in the docker container:
    ::

        docker compose -f docker-compose.docs.yml run --rm docs make apidocs
{% endif -%}
