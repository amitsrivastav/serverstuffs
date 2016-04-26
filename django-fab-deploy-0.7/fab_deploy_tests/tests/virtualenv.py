from __future__ import absolute_import
from fabric.api import *
from fabtest import fab
from fab_deploy.virtualenv import pip_setup_conf
from .deploy import FabDeployProjectTest

class NoPipSetupTest(FabDeployProjectTest):
    def test_no_pip_conf(self):
        self.assertNoFile(env.conf.HOME_DIR+'/pip.conf')
        fab(pip_setup_conf)
        self.assertNoFile(env.conf.HOME_DIR+'/pip.conf')

class PipSetupTest(FabDeployProjectTest):
    project = 'test_project2'

    def test_pip_conf(self):
        self.assertNoFile(env.conf.HOME_DIR+'/pip.conf')
        fab(pip_setup_conf)
        self.assertFileExists(env.conf.HOME_DIR+'/pip.conf')
