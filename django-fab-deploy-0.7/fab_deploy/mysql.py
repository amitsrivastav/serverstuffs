from __future__ import with_statement
import posixpath
from datetime import datetime
from fabric.api import *
from fabric.operations import _handle_failure
from fabric.utils import puts
from fab_deploy import utils
from fab_deploy import system


__all__ = ['mysql_execute', 'mysql_install', 'mysql_create_db',
           'mysql_create_user', 'mysql_grant_permissions', 'mysqldump']


MYSQL_CREATE_USER = """CREATE USER '%(db_user)s'@'localhost' IDENTIFIED BY '%(db_password)s';"""

MYSQL_CREATE_DB = """CREATE DATABASE %(db_name)s DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci;"""

MYSQL_GRANT_PERMISSIONS = """
GRANT ALL ON %(db_name)s.* TO '%(db_user)s'@'localhost';
FLUSH PRIVILEGES;
"""

MYSQL_USER_EXISTS = "SHOW GRANTS FOR '%(db_user)s'@localhost"


def _get_root_password():
    """Ask root password only once if needed"""
    if env.conf.DB_ROOT_PASSWORD is None:
        env.conf.DB_ROOT_PASSWORD = prompt('Please enter MySQL root password:')
    return env.conf.DB_ROOT_PASSWORD

def _credentials(db_name=None, db_user=None, db_password=None):
    db_name = db_name or env.conf.DB_NAME
    db_user = db_user or env.conf.DB_USER
    if db_password is None:
        db_password = env.conf.DB_PASSWORD
    return db_name, db_user, db_password

@utils.run_as_sudo
def mysql_install():
    """ Installs mysql. """
    if _mysql_is_installed():
        puts('Mysql is already installed.')
        return

    passwd = _get_root_password()

    # this way mysql won't ask for a password on installation
    # see http://serverfault.com/questions/19367/scripted-install-of-mysql-on-ubuntu
    os = utils.detect_os()
    system.aptitude_install('debconf-utils')

    mysql_versions = {'lenny': '5.0', 'squeeze': '5.1', 'maverick': '5.1'}
    version = mysql_versions[os]

    debconf_defaults = [
        "mysql-server-%s mysql-server/root_password_again password %s" % (version, passwd),
        "mysql-server-%s mysql-server/root_password password %s" % (version, passwd),
    ]

    sudo("echo '%s' | debconf-set-selections" % "\n".join(debconf_defaults))

    warn('\n=========\nThe password for mysql "root" user will be set to "%s"\n=========\n' % passwd)
    system.aptitude_install('mysql-server')

def _mysql_is_installed():
    with settings(warn_only=True):
        output = run('mysql --version')
    return output.succeeded

def _mysql_user_exists(db_user):
    sql = MYSQL_USER_EXISTS % dict(db_user=db_user)
    with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
        result = mysql_execute(sql, 'root')
    return result.succeeded

def mysqldump(dir=None, db_name=None, db_user=None, db_password=None):
    """ Runs mysqldump. Result is stored at <env>/var/backups/ """
    if dir is None:
        dir = env.conf.ENV_DIR + '/var/backups'
        run('mkdir -p ' + dir)

    db_name, db_user, db_password = _credentials(db_name, db_user, db_password)

    now = datetime.now().strftime('%Y.%m.%d-%H.%M')
    filename = '%s%s.sql' % (db_name, now)

    # if dir is absolute then PROJECT_DIR won't affect result path
    # otherwise dir will be relative to PROJECT_DIR
    full_name = posixpath.join(env.conf.PROJECT_DIR, dir, filename)

    run('mysqldump --user="%s" --password="%s" %s > %s' % (
                        db_user, db_password, db_name, full_name))

def mysql_execute(sql, user=None, password=None):
    """ Executes passed sql command using mysql shell. """
    user = user or env.conf.DB_USER

    if user == 'root' and password is None:
        password = _get_root_password()
    elif password is None:
        password = env.conf.DB_PASSWORD

    sql = sql.replace('"', r'\"')
    return run('echo "%s" | mysql --user="%s" --password="%s"' % (sql, user , password))

def mysql_create_user(db_user=None, db_password=None):
    """ Creates mysql user. """
    _, db_user, db_password = _credentials(None, db_user, db_password)

    if db_user == 'root': # do we really need this?
        _handle_failure('MySQL root user can not be created')
        return

    if _mysql_user_exists(db_user):
        puts('User %s already exists' % db_user)
        return

    sql = MYSQL_CREATE_USER % dict(db_user=db_user, db_password=db_password)
    mysql_execute(sql, 'root')

def mysql_create_db(db_name=None, db_user=None):
    """ Creates an empty mysql database. """
    db_name, db_user, _ = _credentials(db_name, db_user, None)

    sql = MYSQL_CREATE_DB % dict(db_name=db_name, db_user=db_user)
    mysql_execute(sql, 'root')

    if db_user != 'root':
        mysql_create_user(db_user=db_user)
        mysql_grant_permissions(db_name=db_name, db_user=db_user)

def mysql_grant_permissions(db_name=None, db_user=None):
    """ Grants all permissions on ``db_name`` for ``db_user``. """
    db_name, db_user, _ = _credentials(db_name, db_user, None)

    sql = MYSQL_GRANT_PERMISSIONS % dict(db_name=db_name, db_user=db_user)
    mysql_execute(sql, 'root')
