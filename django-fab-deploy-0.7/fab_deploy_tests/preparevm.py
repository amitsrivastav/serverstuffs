#!/usr/bin/env python
import sys
from fabric.api import env, run
from fabtest import fab, VirtualBox
from utils import setup_ssh, setup_sudo, private_key_path

from fab_deploy.utils import update_env
from fab_deploy.system import prepare_server
from fab_deploy.apache import apache_install
from fab_deploy.nginx import nginx_install
from fab_deploy.mysql import mysql_install

def activate_snapshot(box, name):
    box.stop()
    box.snapshot('restore', name)
    box.start()

def deep_prepare(name):
    """ Deep VM preparation for test speedups.
    Should only be run if all related tests are passed.

    It now prepares an extra snapshot with basic software,
    apache, nginx and mysql installed.

    VM is not executed in headless mode because snapshot taking
    seems to be broken in this mode.
    """
    env.hosts = ['foo@127.0.0.1:2222']
    env.password = '123'
    env.disable_known_hosts = True
    env.conf = {'DB_PASSWORD': '123'}
    env.key_filename = private_key_path()
    update_env()

    box = VirtualBox(name)

    if not box.snapshot_exists('fabtest-prepared-server'):
        activate_snapshot(box, 'fabtest-initial')
        setup_sudo()
        setup_ssh()
        fab(prepare_server)
        fab(apache_install)
        fab(nginx_install)
        fab(mysql_install)
        box.snapshot('take', 'fabtest-prepared-server')

    box.stop()


if __name__ == '__main__':
    deep_prepare(sys.argv[1])

