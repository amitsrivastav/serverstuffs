from __future__ import with_statement
from fabric.api import run, env, settings, sudo
from fab_deploy import utils
from fab_deploy import system
from fab_deploy import apache


__all__ = ['nginx_install', 'nginx_setup']


@utils.run_as_sudo
def nginx_install():
    """ Installs nginx. """
    os = utils.detect_os()
    options = {'lenny': '-t lenny-backports'}
    system.aptitude_install('nginx', options.get(os, ''))
    sudo('rm -f /etc/nginx/sites-enabled/default')

@utils.run_as_sudo
def nginx_setup():
    """ Updates nginx config and restarts nginx. """
    apache._apache_setup_port()
    name = env.conf['INSTANCE_NAME']
    utils.upload_config_template('nginx.config',
                                 '/etc/nginx/sites-available/%s' % name,
                                 use_sudo=True)
    with settings(warn_only=True):
        sudo('ln -s /etc/nginx/sites-available/%s /etc/nginx/sites-enabled/%s' % (name, name))
    sudo('invoke-rc.d nginx restart')
