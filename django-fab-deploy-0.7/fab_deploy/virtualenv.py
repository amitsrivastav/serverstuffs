from __future__ import with_statement
from fabric.api import run, env, cd
from fab_deploy import apache
from fab_deploy import utils


__all__ = ['pip', 'pip_install', 'pip_update', 'pip_setup_conf']


@utils.inside_src
def pip(commands=''):
    """ Runs pip command """
    run('pip ' + commands)

@utils.inside_src
def pip_install(what=None, options='', restart=True):
    """ Installs pip requirements listed in ``<PIP_REQUIREMENTS_PATH>/<file>.txt`` file. """
    what = utils._pip_req_path(what or env.conf.PIP_REQUIREMENTS_ACTIVE)
    run('pip install %s -r %s' % (options, what))
    if restart:
        apache.touch()

@utils.inside_src
def pip_update(what=None, options='', restart=True):
    """ Updates pip requirements listed in ``<PIP_REQUIREMENTS_PATH>/<file>.txt`` file. """
    what = utils._pip_req_path(what or env.conf.PIP_REQUIREMENTS_ACTIVE)
    run('pip install %s -U -r %s' % (options, what))
    if restart:
        apache.touch()

def pip_setup_conf():
    """ Sets up pip.conf file """
    run('mkdir -p .pip')
    utils.upload_config_template('pip.conf',
        env.conf.HOME_DIR + '/.pip/pip.conf', skip_unexistent=True)

def virtualenv_create():
    run('mkdir -p envs')
    run('mkdir -p src')
    with cd('envs'):
        run('virtualenv --no-site-packages %s' % env.conf['INSTANCE_NAME'])
