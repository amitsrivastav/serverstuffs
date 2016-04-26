from __future__ import absolute_import
import os
from fab_deploy.utils import run_as
from fabric.api import *
from fabtest import fab, vbox_urlopen
from fab_deploy.deploy import deploy_project, push, undeploy
from fab_deploy.mysql import mysql_create_db
from fab_deploy.apache import (apache_make_config, apache_make_wsgi,
                               apache_restart, apache_install)
from .base import FabDeployTest
from ..utils import setup_ssh, setup_sudo
from ..test_project.fabfile import foo_site, bar_site
from ..test_project2.fabfile import foo_site as foo_site2

def get_file_content(remote_file):
    @run_as('root')
    def cat():
        with(hide('stdout')):
            return run('cat '+remote_file)
    return fab(cat)[0]

def get_ports():
    @run_as('root')
    def ports():
        return run('netstat -A inet -lnp')
    return fab(ports)[0]

def is_local_port_binded(port):
    port_string = '127.0.0.1:%s' % port
    ports = get_ports()
    return port_string in ports

class FabDeployProjectTest(FabDeployTest):
    snapshot = 'fabtest-prepared-server'
    project = 'test_project'

    def assertResponse(self, url, data):
        self.assertEqual(vbox_urlopen(url).read(), data)

    def assertNoFile(self, path):
        with(settings(warn_only=True)):
            res = get_file_content(path)
        self.assertFalse(res.succeeded)

    def assertFileExists(self, path):
        with(settings(warn_only=True)):
            self.assertTrue(get_file_content(path))

    def setup_conf(self):
        self.cwd = os.getcwd()
        os.chdir(self.project)
        fab(foo_site)

    def tearDown(self):
        os.chdir(self.cwd)
        super(FabDeployProjectTest, self).tearDown()


class ApacheSetupTest(FabDeployProjectTest):

    def assertPortBinded(self, port):
        self.assertTrue(is_local_port_binded(port))

    def assertPortNotBinded(self, port):
        self.assertFalse(is_local_port_binded(port))

    def test_apache_config(self):
        fab(apache_install)

        # first site
        fab(foo_site)
        fab(apache_make_config)

        foo_port = env.conf.APACHE_PORT
        self.assertPortNotBinded(foo_port)
        self.assertFileExists('/etc/apache2/sites-enabled/foo')

        fab(apache_restart)
        self.assertPortBinded(foo_port)

        # second site
        fab(bar_site)
        fab(apache_make_config)

        bar_port = env.conf.APACHE_PORT
        self.assertNotEqual(foo_port, bar_port)
        self.assertPortNotBinded(bar_port)

        fab(apache_restart)
        self.assertPortBinded(bar_port)

        # re-configuring doesn't lead to errors
        fab(apache_make_config)
        fab(apache_restart)
        self.assertPortBinded(bar_port)

    def test_apache_make_wsgi(self):
        self.assertNoFile(env.conf.ENV_DIR+'/var/wsgi/foo.py')
        fab(apache_make_wsgi)
        self.assertFileExists(env.conf.ENV_DIR+'/var/wsgi/foo.py')


class DeployTest(FabDeployProjectTest):

    def test_deploy(self):
        # deploy first site
        fab(foo_site)
        fab(deploy_project)

        # first site works
        self.assertResponse('http://foo.example.com/instance/', 'foo')

        # deploy second site
        fab(bar_site)
        fab(deploy_project)

        # second site works
        self.assertResponse('http://bar.example.com/instance/', 'bar')
        # first site is still available
        self.assertResponse('http://foo.example.com/instance/', 'foo')


class CustomLayoutDeployTest(FabDeployProjectTest):
    project = 'test_project2'

    def setUp(self):
        super(CustomLayoutDeployTest, self).setUp()

    def test_deploy(self):
        url = 'http://foo.example.com/instance/'
        fab(foo_site2)

        setup_sudo()
        setup_ssh()

        fab(mysql_create_db)
        fab(deploy_project)
        self.assertResponse(url, 'foo2')

        # just check that blank push doesn't break anything
        # TODO: proper push tests
        fab(push, 'pip_update', 'syncdb')
        self.assertResponse(url, 'foo2')

        # check that updeploy disables the site
        # TODO: more undeploy tests
        fab(undeploy, confirm=False)
        self.assertRaises(Exception, vbox_urlopen, url)

        # deploying project again should be possible
        fab(deploy_project)
        self.assertResponse(url, 'foo2')

    def test_push_callback(self):

        def before_restart():
            before_restart.called = True
        before_restart.called = False

        def my_push(*args):
            return push(*args, before_restart=before_restart)

        fab(foo_site2)

        setup_sudo()
        setup_ssh()

        fab(mysql_create_db)
        fab(deploy_project)
        fab(my_push)
        self.assertTrue(before_restart.called)
