FAQ
===

.. index:: FAQ, 12-Factor App

Why is there a django.contrib.sites directory in moldordie?
-----------------------------------------------------------

It is there to add a migration so you don't have to manually change the ``sites.Site`` record from ``example.com`` to whatever your domain is. Instead, your ``{{cookiecutter.domain_name}}`` and ``{{cookiecutter.project_name}}`` value is placed by **Cookiecutter** in the domain and name fields respectively.

See `0003_set_site_domain_and_name.py`_.

.. _`0003_set_site_domain_and_name.py`: https://github.com/matsakelarsson/moldordie/blob/main/%7B%7Bcookiecutter.project_slug%7D%7D/%7B%7Bcookiecutter.project_slug%7D%7D/contrib/sites/migrations/0003_set_site_domain_and_name.py


Why aren't you using just one configuration file (12-Factor App)
----------------------------------------------------------------------

A settings module belongs to a kind of configuration: development, tests or a deployment. ``config/settings/`` has one of each on top of ``base.py``, because those kinds differ in code. The development module installs the debug toolbar, for example, and the production module sets up the storage backends.

What differs between deployments is their variables, as the 12-Factor App asks. ``dev``, ``test`` and ``production`` all run ``config/settings/production.py`` and differ only in their env files.
