#coding: utf-8
from __future__ import with_statement
from fabric.api import *
from fabric.contrib import console
from fabric.contrib import files

from fab_deploy import utils
from fab_deploy import virtualenv
from fab_deploy import django_commands as dj_cmd
from fab_deploy import system
from fab_deploy import apache
from fab_deploy import nginx
from fab_deploy import vcs


__all__ = ['full_deploy', 'deploy_project', 'make_clone',
           'update_django_config', 'up', 'setup_web_server', 'push',
           'undeploy']


def full_deploy():
    """ Prepares server and deploys the project. """
    os = utils.detect_os()
    if not console.confirm("Is the OS detected correctly (%s)?" % os, default=False):
        abort("Detection fails. Please set env.conf.OS to correct value.")
    system.prepare_server()
    deploy_project()

def deploy_project():
    """ Deploys project on prepared server. """
    virtualenv.virtualenv_create()
    make_clone()

    virtualenv.pip_install(env.conf.PIP_REQUIREMENTS, restart=False)

    setup_web_server()
    update_django_config()

    dj_cmd.syncdb()
    dj_cmd.migrate()

def make_clone():
    """ Creates repository clone on remote server. """
    run('mkdir -p ' + env.conf.SRC_DIR)
    with cd(env.conf.SRC_DIR):
        with settings(warn_only=True):
            vcs.init()
    vcs.push()
    with cd(env.conf.SRC_DIR):
        vcs.up()
    update_django_config(restart=False)
    vcs.configure()

def update_django_config(restart=True):
    """ Updates :file:`config.py` on server (using :file:`config.server.py`) """
    files.upload_template(
        utils._project_path(env.conf.REMOTE_CONFIG_TEMPLATE),
        utils._remote_project_path(env.conf.LOCAL_CONFIG),
        env.conf, True
    )
    if restart:
        apache.touch()

def up(branch=None, before_restart=lambda: None):
    """ Runs vcs ``up`` or ``checkout`` command on server and reloads
    mod_wsgi process. """
    utils.delete_pyc()
    with cd('src/' + env.conf['INSTANCE_NAME']):
        vcs.up(branch)
    before_restart()
    apache.touch()

def setup_web_server():
    """ Sets up a web server (apache + nginx). """
    apache.apache_install()
    nginx.nginx_install()

    apache.apache_setup()
    nginx.nginx_setup()

def push(*args, **kwargs):
    ''' Run it instead of your VCS push command.

    The following strings are allowed as positional arguments:

    * 'notest' - don't run tests
    * 'syncdb' - run syncdb before code reloading
    * 'migrate' - run migrate before code reloading
    * 'pip_update' - run virtualenv.pip_update before code reloading
    * 'norestart' - do not reload source code

    Keyword arguments:

    * before_restart - callable to be executed after code uploading
      but before the web server reloads the code.

    Customization example can be found  :ref:`here <fab-push-customization>`.

    '''
    allowed_args = set(['notest', 'syncdb', 'migrate', 'pip_update', 'norestart'])
    for arg in args:
        if arg not in allowed_args:
            puts('Invalid argument: %s' % arg)
            puts('Valid arguments are: %s' % allowed_args)
            return

    vcs.push()
    utils.delete_pyc()
    with cd('src/' + env.conf['INSTANCE_NAME']):
        vcs.up()

    if 'pip_update' in args:
        virtualenv.pip_update(restart=False)
    if 'syncdb' in args:
        dj_cmd.syncdb()
    if 'migrate' in args:
        dj_cmd.migrate()

    # execute 'before_restart' callback
    kwargs.get('before_restart', lambda: None)()

    if 'norestart' not in args:
        apache.touch()
    if 'notest' not in args:
        dj_cmd.test()

def undeploy(confirm=True):
    """ Shuts site down. This command doesn't clean everything, e.g.
    user data (database, backups) is preserved. """

    if confirm:
        message = "Do you wish to undeploy host %s?" % env.hosts[0]
        if not console.confirm(message, default=False):
            abort("Aborting.")

    @utils.run_as_sudo
    def wipe_web():
        sudo('rm -f /etc/nginx/sites-enabled/' + env.conf['INSTANCE_NAME'])
        sudo('a2dissite ' + env.conf['INSTANCE_NAME'])
        sudo('invoke-rc.d nginx reload')
        sudo('invoke-rc.d apache2 reload')

    wipe_web()
    run('rm -rf %s' % env.conf.SRC_DIR)
    for folder in ['bin', 'include', 'lib', 'src']:
        run('rm -rf %s' % env.conf.ENV_DIR + '/' + folder)
