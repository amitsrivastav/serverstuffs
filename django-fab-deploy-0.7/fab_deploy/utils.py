from __future__ import with_statement
import os
import posixpath
import pprint
from re import match
from functools import wraps
from fabric.api import *
from fabric.contrib import files
from fabric import state
from fabric import network
from fabric import operations


__all__ = ['run_as', 'update_env', 'inside_project', 'inside_virtualenv',
           'inside_src', 'delete_pyc', 'print_env', 'detect_os']

DETECTION_ERROR_MESSAGE = """
OS detection failed. This probably means your OS is not
supported by django-fab-deploy. If you really know what
you are doing, set env.conf.OS variable to desired OS
name in order to bypass this error message.
If you believe the OS is supported but the detection
fails or you want to get your OS supported, please fire an issue at
https://bitbucket.org/kmike/django-fab-deploy/issues/new
"""

def _codename(distname, version, id):
    patterns = [
        ('lenny', ('debian', '^5', '')),
        ('squeeze', ('debian', '^6', '')),
        ('maverick', ('Ubuntu', '^10.10', '')),
    ]
    for name, p in patterns:
        if match(p[0], distname) and match(p[1], version) and match(p[2], id):
            return name

def detect_os():
    if 'conf' in env and 'OS' in env.conf:
        return env.conf['OS']
    output = run('python -c "import platform; print platform.dist()"')
    name = _codename(*eval(output))
    if name is None:
        abort(DETECTION_ERROR_MESSAGE)

    puts('%s detected' % name)
    return name

def run_as(user):
    """
    Decorator. Runs fabric command as specified user. It is most useful to
    run commands that require root access to server.
    """
    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            old_user, host, port = network.normalize(env.host_string)
            env.host_string = network.join_host_strings(user, host, port)
            result = func(*args, **kwargs)
            env.host_string = network.join_host_strings(old_user, host, port)
            return result
        return inner
    return decorator

def run_as_sudo(func):
    """
    Decorator. By default all commands are executed as user without
    sudo access for security reasons. Use this decorator to run fabric
    command as user with sudo access (:attr:`env.conf.SUDO_USER`)::

        from fabric.api import run
        from fab_deploy import utils

        @utils.run_as_sudo
        def aptitude_update():
            run('aptitude update')
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return run_as(env.conf.SUDO_USER)(func)(*args, **kwargs)
    return wrapper

def upload_config_template(name, to=None, skip_unexistent=False, **kwargs):
    if to is None:
        base_dir = env.conf['ENV_DIR'] + "/etc/"
        run('mkdir -p ' + base_dir)
        to = base_dir + name
    config_template = _config_template_path(name)

    if config_template is None:
        if skip_unexistent:
            return
        operations._handle_failure('Config template "%s" is not found' % name)

    files.upload_template(config_template, to, env.conf, use_jinja=True,
                          **kwargs)

def update_env():
    """
    Updates :attr:`env.conf` configuration with some defaults and converts
    it to state._AttributeDict (that's a dictionary subclass enabling attribute
    lookup/assignment of keys/values).

    Call :func:`update_env` at the end of each server-configuring function.

    ::

        from fab_deploy import *

        def my_site():
            env.hosts = ['my_site@example.com']
            env.conf = dict(
                DB_PASSWORD = 'password',
            )
            update_env()
    """
    assert len(env.hosts) == 1, "Multiple hosts in env.hosts are not supported now. (%s)" % env.hosts
    user, host, port = network.normalize(env.hosts[0])

    env.conf = getattr(env, 'conf', {})

    env.conf.setdefault('INSTANCE_NAME', user)
    env.conf.setdefault('PROJECT_PATH', '')

    HOME_DIR = '/home/%s' % user if user != 'root' else '/root'
    SRC_DIR = posixpath.join(HOME_DIR, 'src', env.conf['INSTANCE_NAME'])
    PROJECT_DIR = posixpath.join(SRC_DIR, env.conf['PROJECT_PATH']).rstrip('/')

    defaults = state._AttributeDict(
        HG_BRANCH='default',
        GIT_BRANCH='master',
        DB_NAME=env.conf['INSTANCE_NAME'],
        DB_USER='root',
        SUDO_USER='root',
        PROCESSES=1,
        THREADS=15,
        SERVER_NAME=host,
        SERVER_ADMIN='example@example.com',
        VCS='hg',

        PROJECT_PATH='',
        LOCAL_CONFIG='config.py',
        REMOTE_CONFIG_TEMPLATE='config.server.py',
        CONFIG_TEMPLATES_PATHS=['config_templates'],

        PIP_REQUIREMENTS_PATH='reqs',
        PIP_REQUIREMENTS='all.txt',
        PIP_REQUIREMENTS_ACTIVE='active.txt',

        # these options shouldn't be set by user
        HOME_DIR=HOME_DIR,
        ENV_DIR=posixpath.join(HOME_DIR, 'envs', env.conf['INSTANCE_NAME']),
        SRC_DIR=SRC_DIR,
        PROJECT_DIR=PROJECT_DIR,
        USER=user,
    )
    defaults.update(env.conf)

    env.conf = defaults

    if env.conf.DB_USER == 'root':
        if 'DB_ROOT_PASSWORD' in env.conf and 'DB_PASSWORD' in env.conf:
            msg = "DB_ROOT_PASSWORD and DB_PASSWORD must be the same because DB_USER is root"
            assert env.conf.DB_ROOT_PASSWORD == env.conf.DB_PASSWORD, msg
        else:
            # auto-fill the missing option
            password = env.conf.get('DB_ROOT_PASSWORD',
                                    env.conf.get('DB_PASSWORD', None))
            if password is not None:
                env.conf.DB_PASSWORD = env.conf.DB_ROOT_PASSWORD = password

    for vcs in ['git', 'hg', 'none']: # expand VCS name to full import path
        if env.conf.VCS == vcs:
            env.conf.VCS = 'fab_deploy.vcs.' + vcs


def virtualenv():
    """
    Context manager. Use it for perform actions with virtualenv activated::

        with virtualenv():
            # virtualenv is active here

    """
    return prefix('source %s/bin/activate' % env.conf.ENV_DIR)

def inside_virtualenv(func):
    """
    Decorator. Use it for perform actions with virtualenv activated::

        @inside_virtualenv
        def my_command():
            # virtualenv is active here

    """
    @wraps(func)
    def inner(*args, **kwargs):
        with virtualenv():
            return func(*args, **kwargs)
    return inner

def inside_src(func):
    """
    Decorator. Use it to perform actions inside remote source dir
    (repository root) with virtualenv activated.
    """
    @wraps(func)
    def inner(*args, **kwargs):
        with cd(env.conf.SRC_DIR):
            with virtualenv():
                return func(*args, **kwargs)
    return inner

def inside_project(func):
    """
    Decorator. Use it to perform actions inside remote project dir
    (that's a folder where :file:`manage.py` resides) with
    virtualenv activated::

        from fabric.api import *
        from fab_deploy.utils import inside_project

        @inside_project
        def cleanup():
            # the current dir is a project source dir and
            # virtualenv is activated
            run('python manage.py cleanup')

    """
    @wraps(func)
    def inner(*args, **kwargs):
        with cd(env.conf.PROJECT_DIR):
            with virtualenv():
                return func(*args, **kwargs)
    return inner

@inside_project
def delete_pyc():
    """ Deletes *.pyc files from project source dir """
    run("find . -name '*.pyc' -delete")

def print_env():
    """ Prints env values. Useful for debugging. """
    puts(pprint.pformat(env))

def _data_path(fname):
    """Return the path to a data file of ours."""
    return os.path.join(os.path.split(__file__)[0], fname)

def _project_path(name):
    return os.path.join(env.conf.PROJECT_PATH, name)

def _remote_project_path(name):
    return posixpath.join(env.conf.PROJECT_DIR, name)

def _pip_req_path(name):
    if not name.endswith(('.txt', '.pip',)):
        name += '.txt'
    return posixpath.join(env.conf.PIP_REQUIREMENTS_PATH, name)

def _config_template_path(name):
    for dir in env.conf.CONFIG_TEMPLATES_PATHS:
        path = os.path.join(dir, name)
        if os.path.exists(path):
            return path
