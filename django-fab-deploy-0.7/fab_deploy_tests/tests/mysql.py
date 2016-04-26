from __future__ import absolute_import
from fabric.api import *
from fabtest import fab
from fab_deploy.mysql import (mysql_install, _mysql_is_installed, mysqldump,
                              mysql_create_db, mysql_execute, mysql_create_user)
from ..utils import setup_sudo
from .base import FabDeployTest

def mysql_is_installed():
    return fab(_mysql_is_installed)[0]

def database_exists(db_name):
    databases = fab(mysql_execute, 'show databases;', 'root')[0].splitlines()
    return db_name in databases

class MysqlTest(FabDeployTest):
    host = 'root@127.0.0.1:2222'

    def setup_conf(self):
        super(MysqlTest, self).setup_conf()
        env.conf['DB_PASSWORD'] = '123'
        env.conf['DB_NAME'] = 'new_database'

    def test_mysql(self):
        setup_sudo()

        self.assertFalse(mysql_is_installed())

        fab(mysql_install)
        self.assertTrue(mysql_is_installed())

        self.assertFalse(database_exists('new_database'))
        fab(mysql_create_db)
        self.assertTrue(database_exists('new_database'))


class MysqlNonRootTest(FabDeployTest):
    host = 'root@127.0.0.1:2222'

    def setup_conf(self):
        super(MysqlNonRootTest, self).setup_conf()
        env.conf['DB_ROOT_PASSWORD'] = '123'
        env.conf['DB_PASSWORD'] = 'foo123'
        env.conf['DB_NAME'] = 'new_database'
        env.conf['DB_USER'] = 'foo'

    def test_mysql(self):
        setup_sudo()

        self.assertFalse(mysql_is_installed())

        fab(mysql_install)
        self.assertTrue(mysql_is_installed())

        self.assertFalse(database_exists('new_database'))
        fab(mysql_create_db)
        self.assertTrue(database_exists('new_database'))

        # re-creating user shouldn't break anything
        fab(mysql_create_user)

        # this will fail if permissions are not set correctly
        output = fab(mysql_execute, 'use new_database; create table baz (id int); show tables;')[0]
        tables = output.splitlines()[1:]
        self.assertEqual(tables[0], 'baz')

        # mysqldump should work
        fab(mysqldump, env.conf.HOME_DIR)
