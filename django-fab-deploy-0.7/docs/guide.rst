User Guide
==========

The basic workflow for setting up a new web site is
described in this guide. If this workflow doesn't fit for some reason then
django-fab-deploy can still be used as a collection of scripts, a lot of
them can be used independently.

Prerequisites
-------------

1. Clean Debian Lenny, Debian Squeeze or Ubuntu 10.10 server/VPS with
   root or sudo-enabled user ssh access;
2. working ssh key authentication;

.. warning::

    OpenVZ has serious issues with memory management
    (VIRT is counted and limited instead of RSS) so a lot of software
    (including apache2, Java and mysql's InnoDB engine) is nearly unusable on
    OpenVZ while being memory-wise and performant on XEN/KVM. So please try to
    avoid OpenVZ or Virtuozzo VPS's, use XEN or KVM or real servers.


Prepare the project
-------------------

1. Install django-fab-deploy its requirements::

       pip install django-fab-deploy
       pip install jinja2
       pip install "fabric >= 1.0.0"

2. Create :file:`fabfile.py` at project root. It should provide one or more
   function putting server details into Fabric environment. Otherwise it's just
   a standart Fabric's fabfile (e.g. project-specific scripts can also be put
   here). Example::

        # my_project/fabfile.py
        from fab_deploy import *

        def my_site():
            env.hosts = ['my_site@example.com']
            env.conf = dict(
                DB_PASSWORD = 'password',

                # uncomment this line if the project is not stored in VCS
                # default value is 'hg', 'git' is also supported
                # VCS = 'none',
            )
            update_env()

        my_site()

   In order to make things simple set the username in :attr:`env.hosts` string
   to your project name. It should be a valid python identifier.
   Don't worry if there is no such user on server, django-fab-deploy can
   create linux user and setup ssh access for you, and it is
   preferrable to have linux user per project if possible.

   .. note::

       There are some defaults, e.g. :attr:`DB_USER <env.conf.DB_USER>`
       is 'root' by default, :attr:`DB_NAME <env.conf.DB_NAME>`
       equals to :attr:`INSTANCE_NAME <env.conf.INSTANCE_NAME>`,
       and :attr:`INSTANCE_NAME <env.conf.INSTANCE_NAME>` equals
       to username obtained from :attr:`env.hosts`.

       Read :doc:`fabfile` for more details.

3. Copy ``config_templates`` folder from django-fab-deploy to your project
   root, manually or by running the following command from the project root::

       django-fab-deploy config_templates

   Read the configs and adjust them if it is needed. Basic configs
   are usually a good starting point and should work as-is.

   .. note::

       {{ variables }} can be used in config templates (engine is jinja2).
       They will be replaced with values from :attr:`env.conf` on server.

       If you change web server config file or :attr:`env.conf` variables
       after initial deployment, apply the changes in web server configs
       by running ::

           fab setup_web_server


4. Create :file:`config.server.py` at project root. This file will become
   :file:`config.py` on server. Example::

        # my_project/config.server.py
        # config file for environment-specific settings

        DEBUG = False
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': '{{ DB_NAME }}',
                'USER': '{{ DB_USER }}',
                'PASSWORD': '{{ DB_PASSWORD }}',
                'HOST': '',
                'PORT': '',
                'OPTIONS': {
                    "init_command": "SET storage_engine=INNODB"
                },
            }
        }

   Then create :file:`config.py` for local development.
   Import config in project's :file:`settings.py`::

       # Django settings for my_project project.
       # ...
       from config import *
       # ...

   ``config.py`` trick is also known as ``local_settings.py``
   (make sure ``config.py`` is ignored in your VCS if one is used).

   .. note::

       {{ variables }} can be used in :file:`config.server.py`. They will be
       replaced with values from :attr:`env.conf` on server.

       If you change :file:`config.server.py` or :attr:`env.conf` variables
       after initial deployment, apply the changes to :file:`config.server.py`
       by running ::

           fab update_django_config


5. Create ``reqs`` folder at project root. This folder should contain
   text files with `pip requirements <http://pip.openplans.org/requirement-format.html>`_.

   You can get basic/example ``reqs`` folder by running ::

       django-fab-deploy example_reqs

   One file is special: :file:`reqs/all.txt`. This is the main requirements
   file. List all project requirements here one-by-one or (preferrable) by
   including other requirement files using "-r" syntax.

   There is also

       django-fab-deploy generate_reqs

   command. It creates ``reqs`` folder with :file:`all.txt` file containing
   a list of currently installed packages (obtained from ``pip freeze``).


The project should look like that after finishing steps 1-5::

    my_project
        ...
        config_templates <- this folder should be copied from django-fab-deploy
            apache.config
            django_wsgi.py
            hgrc
            nginx.config

        reqs             <- a folder with project's pip requirement files
            all.txt      <- main requirements file, list all requirements in this file
            active.txt   <- put recently modified requirements here
            ...          <- you can provide extra files and include them with '-r' syntax in e.g. all.txt

        config.py        <- this file should be included in settings.py and ignored in .hgignore
        config.server.py <- this is a production django config template
        fabfile.py       <- your project's Fabric deployment script
        settings.py
        manage.py

.. note::

    django-fab-deploy does not enforce this layout; if it doesn't fit for some
    reason (e.g. you prefer single pip requirements file or django
    project in subfolder), take a look at :ref:`custom-project-layouts`.

The project is now ready to be deployed.

Prepare the server
------------------

1. If the server doesn't have sudo installed (e.g. clean Lenny or Squeezy)
   then install sudo on server::

       fab install_sudo

2. If there is no linux account for user specified in :attr:`env.hosts`
   then add a new linux server user, manually or using

   ::

       fab create_linux_account:"/home/kmike/.ssh/id_rsa.pub"

   You'll need the ssh public key.
   :func:`create_linux_account <fab_deploy.system.create_linux_account>`
   creates a new linux user and uploads provided ssh key. Test that ssh
   login is working::

       ssh my_site@example.com

   .. note::

       Fabric commands should be executed in shell from the project root
       on local machine (not from the python console, not on server shell).

   SSH keys for other developers can be added at any time::

       fab ssh_add_key:"/home/kmike/coworker-keys/ivan.id_dsa.pub"

3. Setup the database. django-fab-deploy can install mysql and create empty
   DB for the project::

       fab mysql_install
       fab mysql_create_db

   :func:`mysql_install <fab_deploy.mysql.mysql_install>` does
   nothing if mysql is already installed on server. Otherwise it installs
   mysql-server package and set root password to
   :attr:`env.conf.DB_ROOT_PASSWORD`. If this option is empty, mysql_install
   will ask for a password.

   :func:`mysql_create_db <fab_deploy.mysql.mysql_create_db>` creates a new
   empty database named :attr:`env.conf.DB_NAME` (it equals to
   :attr:`env.conf.INSTANCE_NAME` by default, which equals to
   the user from :attr:`env.hosts` by default).
   :func:`mysql_create_db <fab_deploy.mysql.mysql_create_db>` will
   ask for a mysql root password if :attr:`DB_USER <env.conf.DB_USER>`
   is not 'root'.

   .. note::

        If the DB enging is not mysql then DB should be created manually now.


4. If you feel brave you can now run ``fab full_deploy`` from the project root
   and get a working django site.

   This command:

   * installs necessary system and python packages;
   * configures apache and ngnix;
   * creates virtualenv;
   * uploads project to the server;
   * runs ``python manage.py syncdb`` and ``python manage.py migrate`` commands
     on server.

   Project sources will be available under ``~/src/<INSTANCE_NAME>``, virtualenv
   will be placed in ``~/envs/<INSTANCE_NAME>``.

   .. warning::

      django-fab-deploy disables 'default' apache and nginx sites and
      takes over 'ports.conf' so apache is no longer listening to 80 port.

      If there are other sites on server (not managed by django-fab-deploy)
      they may become unaccessible due to these changes.

Working with the server
-----------------------

django-fab-deploy provides additional commands that should be useful for
updating the server:

1. Source changes are deployed with :func:`fab_deploy.deploy.push` command::

       fab push

   Another example (deploy changes on 'prod' server, update pip
   requirements and perform migrations in one step::

       fab prod push:pip_update,migrate

2. Update web server configuration::

       fab setup_web_server

3. Update django configuration (:file:`config.server.py`)::

       fab update_django_config

4. Requirements are updated with :func:`fab_deploy.virtualenv.pip_update`
   command. Update requirements listed in reqs/active.txt::

       fab pip_update

   Update requirements listed in reqs/my_apps.txt::

       fab pip_update:my_apps

5. Remotely change branch or revision (assuming :attr:`env.conf.VCS`
   is not 'none')::

       fab up:my_branch

Full list of commands can be found :doc:`here <reference>`.

:doc:`Customization guide <customization>` is also worth reading.
