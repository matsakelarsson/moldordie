.. {{ cookiecutter.project_name }} documentation master file, created by
   sphinx-quickstart.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to {{ cookiecutter.project_name }}'s documentation!
======================================================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   howto
   frontend
   users
{%- if cookiecutter.identity_provider != 'none' %}
   authentication
{%- endif %}
{%- if cookiecutter.observability == 'prometheus' %}
   observability
{%- endif %}



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
