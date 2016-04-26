from __future__ import absolute_import
from fabric.api import *
from fabtest import fab
from fab_deploy.crontab import crontab_add, crontab_remove, _get_current, crontab_update, crontab_show
from fab_deploy_tests.utils import setup_ssh
from .base import FabDeployTest

class CrontabTest(FabDeployTest):
    snapshot = 'fabtest-prepared-server'

    def current(self):
        return fab(_get_current)[0]

    def add(self, content, marker):
        return fab(crontab_add, content, marker)[0]

    def remove(self, marker):
        return fab(crontab_remove, marker)[0]

    def update(self, content, marker):
        return fab(crontab_update, content, marker)[0]

    def test_crontab(self):
        line1 = '@reboot echo 123'
        line2 = '@reboot echo 345'
        new_line2 = '@reboot echo 567'

        self.add(line1, 'line1')
        self.add(line2, 'line2')
        current = self.current()

        self.assertTrue(line1 in current)
        self.assertTrue(line2 in current)
        self.assertFalse(new_line2 in current)

        self.update(new_line2, 'line2')
        current = self.current()

        self.assertTrue(line1 in current)
        self.assertFalse(line2 in current)
        self.assertTrue(new_line2 in current)

        self.remove('line1')
        current = self.current()

        self.assertFalse(line1 in current)
        self.assertFalse(line2 in current)
        self.assertTrue(new_line2 in current)

        fab(crontab_show)
