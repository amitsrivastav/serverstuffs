from __future__ import absolute_import
from fabric.api import *
from fabric.state import _AttributeDict
from fabtest import FabTest
from fab_deploy.utils import update_env
from fab_deploy_tests.utils import get_package_state, private_key_path

class FabDeployTest(FabTest):
    host = 'foo@127.0.0.1:2222'
    key_filename = [private_key_path()]

    def setup_env(self):
        super(FabDeployTest, self).setup_env()
        self.setup_conf()
        update_env()

    def setup_conf(self):
        env.conf = _AttributeDict()

    def assertPackageInstalled(self, name):
        self.assertEqual(get_package_state(name), 'i')

    def assertPackageNotInstalled(self, name):
        self.assertNotEqual(get_package_state(name), 'i')

    def assertUserIs(self, user):
        # use it inside fab commands
        output = run('whoami')
        self.assertEqual(output, user)

