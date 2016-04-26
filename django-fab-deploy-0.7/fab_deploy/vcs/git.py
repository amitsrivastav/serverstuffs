from fabric.api import *
from fab_deploy.utils import upload_config_template

BRANCH_OPTION = 'GIT_BRANCH'

def init():
    run('git init')
    run('git config receive.denyCurrentBranch ignore') # allow update current branch

def up(branch):
    run('git checkout --force %s' % branch) # overwrite local changes

def push():
    user, host = env.hosts[0].split('@')
    local('git push --force ssh://%s/~%s/src/%s/ %s' % (env.hosts[0], user,
        env.conf.INSTANCE_NAME, env.conf.GIT_BRANCH))

def configure():
    pass
