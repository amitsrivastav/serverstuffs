from fab_deploy import *

def foo_site():
    env.hosts = ['foo@127.0.0.1:2222']
    env.conf = dict(
        DB_PASSWORD = '123',
        VCS = 'none',
        SERVER_NAME = 'foo.example.com'
    )
    update_env()

def bar_site():
    env.hosts = ['foo@127.0.0.1:2222']
    env.conf = dict(
        DB_PASSWORD = '123',
        VCS = 'none',
        SERVER_NAME = 'bar.example.com',
        INSTANCE_NAME = 'bar',
    )
    update_env()
