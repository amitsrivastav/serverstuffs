import datetime
import time
import sys
import urllib2
from fabric.api import env, run, cd, settings, sudo, parallel
from fabric.contrib.project import rsync_project
import os, logging
import boto.ec2.networkinterface
from time import mktime
from fabric import api as fab
from boto import ec2
from boto.ec2 import elb, ec2object
from fabric.operations import run, put

logger = logging.getLogger('AMIBackup')
hdlr = logging.FileHandler('fab.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)
 
SERVER_USER = 'ubuntu'
SSH_KEY_FILE = 'id_rsa.pem'
lb_conn = elb.connect_to_region("ap-southeast-1")
ec_conn = ec2.connect_to_region("ap-southeast-1")
env = fab.env
local = fab.local
cd = fab.cd
run = fab.run

env.user = 'ubuntu'
env.disable_known_hosts = "True"  # for EC2
env.key = 'id_rsa.pem'
env.key_filename = '/home/ubuntu/id_rsa.pem'
env.dir = '/home/ubuntu/src/apps/'
# Sets the number of concurrent processes to use
# when executing tasks in parallel
env.pool_size = 5

### Get ELB instances ID to perform another action on them
@fab.task 
def elb_instances(elb):
    'Get a list of instance IDs for the ELB'
    instances = []
    lb = lb_conn.get_all_load_balancers(load_balancer_names=[elb])[0]
    instances.extend(lb.instances)
    ids = [i.id for i in instances]
    print ids
    return prepare_deploy_list(ids)
 
def aws(elb):
    fab.env.hosts = elb_instances(elb)
    fab.env.key_filename = SSH_KEY_FILE
    fab.env.user = SERVER_USER
    fab.env.parallel = True

## To deregister an instance from ELB instances
@fab.task
def elb_deregister(elb, instance):
    'deregister instance from elb'
    lb = lb_conn.get_all_load_balancers(load_balancer_names=[elb])[0]
    result = lb.deregister_instances(instance)
    return result

# to register instance to ELB instance
@fab.task
def elb_register(elb, instance):
    'Deregister instances from elb'
    lb = lb_conn.get_all_load_balancers(load_balancer_names=[elb])[0]
    result = lb.register_instances(instance)
    return result

# Create an AMI For the instance
@fab.task
def ami_backup(instance,desc):
    'create an ami of instance'
    current_datetime = datetime.datetime.now()
    date_stamp = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
    ami_name = date_stamp
    i = ec_conn.get_all_instances(instance)[0]
    for instance in i.instances:
        ami_name = desc + instance.id + '_' + date_stamp
        result = instance.create_image(ami_name, description='Tagged release: {}'.format(date_stamp), no_reboot=True, dry_run=False)
        print result
    return result


@fab.task
def prepare_deploy_list(instances):
    'get instances private ip'
    ins = ec_conn.get_all_instances(instances)
    env.hosts = []
    for i in ins:
        for j in i.instances:
            env.hosts.append(j.private_ip_address)

# to Restart apache instnces 
@fab.task
def restart_apache2():
    "Restart Apache2 server."
    fab.sudo("/etc/init.d/apache2 restart && ls")
    fab.sudo("/etc/init.d/apache2 status")

#To stop apache2 instances
@fab.task
def stop_apache2():
    "stop Apache2 server."
    fab.sudo("/etc/init.d/apache2 stop")

# to check the git log from app servers
@fab.task
def git_log():
    with cd("/home/ubuntu/src/apps/"):
        run('git log --pretty=format:"%h - %an, %ad, %ar : %s" -n 3')


# Fabric task for cloning GIT repository in app directory
@parallel
def clone_branch():
    with cd("/home/ubuntu/src/apps/"):
        run('git clone https://github.com/apps/app.git')


# Fabric task for deploying latest changes using GIT pull
@parallel
def update_branch():
    with cd("/home/ubuntu/src/apps"):
        run('git pull -f')

# Fabric git pull for code
@fab.task
@parallel
def pull():
    """Update the repository"""
    with cd(env['dir']):
        run('git pull origin master:master')

# fabric task to clear cache of django application
@fab.task
@parallel
def clear_cache():
    """Update the repository"""
    with cd(env['dir']):
        run('python manage.py clear_cache')


@fab.task
def diff():
    """Do a diff of local master with the remote master"""
    with cd(env['dir']):
        run('git diff master origin/master --stat')


@fab.task
def reset():
    """
    Reset all git repositories to specified hash.
    Usage:
        fab staging reset:hash=etcetc123
    """
    with cd(env['dir']):
        run('git reset --hard origin/master')

#Fab task to deploy codes on servers
@fab.task(alias='deploy')
def release_code():
    """Release the code and reboot apache"""
    pull()
    install_pip_requirements()
    restart_apache2()

#fab task to stop supervisor running process and killing all python process
@fab.task(alias="supervisor_stop")
@parallel
def supervisor_stop():
	"""supervisor stop and kill all running workers"""
        run( 'sudo supervisorctl stop all && sudo pkill -9 python')

#to print all running python tool version
@fab.task(alias="yolk")
@parallel
def yolk():
	"""print python tools version"""
        run( 'yolk -l')


@fab.task(alias="enable_headers")
@parallel
def enable_headers():
	"""supervisor stop and kill all running workers"""
        run( 'sudo a2enmod rewrite')
@fab.task(alias="supervisor_start")
@parallel
def supervisor_start():
	"""start supervisor process for instance"""
        run( 'sudo supervisorctl start all')

@fab.task(alias="deploy_worker")
@parallel
def deploy_worker():
	"""deploy and restart worker instances"""
	pull()
	install_pip_requirements()
        supervisor_stop()
	supervisor_start()

@fab.task(alias='apt-get')
def install_package():
    """
    Install package on host using apt-get
    """
    fab.sudo('apt-get update ')
    fab.sudo('apt-get install libxml2-dev libxslt1-dev libpq-dev python-dev libfreetype6-dev python-imaging python-setuptools gcc -y')


@fab.task(alias='pip')
def install_pip_requirements(requirements_file=None):
    """
    Installs pip requirements from the requirements_file
    If no file is given, default is used
    """
    if not requirements_file:
        with cd(env['dir']):
            fab.sudo('pip install -r requirements.txt')
    else:
        fab.sudo('pip install -r %s' % requirements_file)

@fab.task(alias='workers_restart')
@parallel
def workers_restart(name):
    'restart workers'
    run('fab.sudo supervisorctl status')
    run('fab.sudo supervisorctl restart {}'.format(name))
    run('fab.sudo supervisorctl status')


@fab.task(alias='workers_supervisorctl_status')
@parallel
def workers_supervisorctl_status():
    'get workers status'
    run('sudo supervisorctl status')

from fabric.contrib.project import rsync_project
@fab.task(alias='sync_files')
@parallel
def sync_files(loc):
    rsync_project(local_dir=loc, remote_dir='/home/ubuntu/src/apps', exclude='.git')
from fabric.api import env
from fabric.operations import run, put


@fab.task(alias='ntpdate')
@parallel
def ntpdate():
    # make sure the directory is there!
    sudo('ntpdate ntp.ubuntu.com')
 

##########################################################
#############Extended for autoscale if ec2 instances########

import boto.ec2.autoscale
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import launchconfig
from boto.ec2.autoscale import AutoScalingGroup
as_conn = boto.ec2.autoscale.connect_to_region("ap-southeast-1")
@fab.task(alias='launch_config')
def launch_config(lcname,image_id):
	'''Create a launch configuration for auto scalling group'''
	lc = LaunchConfiguration(name=lcname,image_id=image_id,instance_type='c3.large',key_name='allservers',security_groups=[('sg-0518e960')])
	as_conn.create_launch_configuration(lc)


@fab.task(alias='autoscale')
def autoscale(my_group, lb_name, LaunchConfig):
	'''create autoscalling group'''
	ag = AutoScalingGroup(group_name=my_group, load_balancers=[lb_name],
                          availability_zones=['ap-southeast-1a', 'ap-southeast-1b'],
                          launch_config=LaunchConfig, min_size=4, max_size=5,
                          connection=as_conn)
	as_conn.create_auto_scaling_group(ag)
	as_conn.get_all_activities(ag)


########################Define the Scaling policy##########################

from boto.ec2.autoscale import ScalingPolicy
import boto.ec2.cloudwatch
from boto.ec2.cloudwatch import MetricAlarm
cloudwatch = boto.ec2.cloudwatch.connect_to_region("ap-southeast-1")

@fab.task(alias='scaling_policy')
def scaling_policy(my_group):
	'define the scaing policy for the group'
	scale_up_policy = ScalingPolicy(name='scale_up', adjustment_type='ChangeInCapacity',
            as_name=my_group, scaling_adjustment=1, cooldown=180)
	scale_down_policy = ScalingPolicy(name='scale_down', adjustment_type='ChangeInCapacity',
            as_name=my_group, scaling_adjustment=-1, cooldown=180)

##########Submitting policy to AWS

	as_conn.create_scaling_policy(scale_up_policy)
	as_conn.create_scaling_policy(scale_down_policy)

## need to refresh scaling policy by requesting them back 

	scale_up_policy = as_conn.get_all_policies(as_group=my_group, policy_names=['scale_up'])[0]
	scale_down_policy = as_conn.get_all_policies(as_group=my_group, policy_names=['scale_down'])[0]

###CloudWatch alarms that will define when to run the Auto Scaling Policies

	alarm_dimensions = {"AutoScalingGroupName":my_group}
#def set_metricAlarm():
	'set alarm for scaing the instances in as_group'
	scale_up_alarm = MetricAlarm(
         	name='scale_up_on_cpu_"my_group"', namespace='AWS/EC2',
       		metric='CPUUtilization', statistic='Average',
            	comparison='>', threshold='70',
           	period='300', evaluation_periods=2,
            	alarm_actions=[scale_up_policy.policy_arn],
           	 dimensions=alarm_dimensions)
	
	cloudwatch.create_alarm(scale_up_alarm)

	scale_down_alarm = MetricAlarm(
            name='scale_down_on_cpu_"my_group"', namespace='AWS/EC2',
            metric='CPUUtilization', statistic='Average',
            comparison='<', threshold='40',
            period='300', evaluation_periods=2,
            alarm_actions=[scale_down_policy.policy_arn],
            dimensions=alarm_dimensions)
	
	cloudwatch.create_alarm(scale_down_alarm)


#### To retrive the instances from autoscaling group

@fab.task(alias='as_instances')
def as_instances(my_group):
	'describe instances running in as_group'
	group = as_conn.get_all_groups(names=['my_group'])[0]
	instance_ids = [i.instance_id for i in group.instances]
	instances = ec2.get_only_instances(instance_ids)


##delete your autoscale group

@fab.task(alias='ag_delete')
def ag_delete(my_group):
	'delete the autoscale group'
	ag.shutdown_instances()
	ag.delete()
	lc.delete()

#######################
from boto.ec2.elb import HealthCheck
from boto.ec2.elb import ELBConnection
from boto.ec2.elb.loadbalancer import LoadBalancer, LoadBalancerZones
@fab.task(alias='create_lb')
def create_lb(lb_name):
	'create a new load balancer'
	region = 'ap-southeast-1'
	#zones = 'ap-southeast-1a'
	zones = None
	listeners = [(80, 80, 'HTTP'),(443, 443, 'TCP')]
	subnets = 'subnet-0d0b3379'
	lb = lb_conn.create_load_balancer(lb_name, zones, listeners, subnets)
	hc = HealthCheck(
        	interval=20,
  		healthy_threshold=3,
       		unhealthy_threshold=5,
   		target='HTTP:80/health')
	lb.configure_health_check(hc)
	print lb.dns_name 
#######################attache lb to specific subnet################
@fab.task(alias = 'attach_lb_to_subnets')
def attach_lb_to_subnets(lb_name, subnets):
	'attach load balancer to a subnet'
	lb_conn.attach_lb_to_subnets(lb_name, subnets)	



#############################################################
#############################################################
#############Definition for RDS instance#####################
import boto.rds
conn = boto.rds.connect_to_region("ap-southeast-1")
## to create a new db instnces
#db = conn.create_dbinstance("db-master-1", 10, 'db.m1.small', 'root', 'hunter2') 
def create_db_instance(identifier, db_size, instance_class, engine, master_username, master_user_passwd):
    conn.create_dbinstance(identifier,db_size, instance_class, engine, master_username, master_user_passwd)
    instances = conn.get_all_dbinstances(identifier)
    db = instances[0]
    db.status
    db.endpoint

@fab.task
def get_all_snapshots():
    'get all rds snapshots detail'
    snp = conn.get_all_dbsnapshots()
    print snp

@fab.task
def get_all_dbinstances():
    'get all rds instance'	
    db = conn.get_all_dbinstances()
    print db

####restore db instance from db snapshots
import boto.rds.dbsnapshot
@fab.task
def restore_dbinstance_from_dbsnapshot(identifier, instance_id, instance_class,port = None,availability_zone = None):
    'restore db instance from rds snapshots'
    conn.restore_dbinstance_from_dbsnapshot('identifier','instance_id','instance_class',port = None,availability_zone = None)



#################################################################
####################get tag wise information of instance

@fab.task
def get_taggedhost_list(value):
 #   import pdb ; pdb.set_trace()
    '''get instances private ip'''
    ins = ec_conn.get_all_instances(filters={"tag:task":value})
	
    env.hosts = []
    for i in ins:
        for j in i.instances:
        	k=env.hosts.append(j.private_ip_address)
    return env.hosts

@fab.task
def task_cpu(value):
	'''get workers cpu utilization'''
	instances = []
	ins = ec_conn.get_all_instances(filters={"tag:task":value})
	for i in ins:
		for j in i.instances:
			l = cloudwatch.list_metrics(dimensions={'InstanceId':j.id}, metric_name='CPUUtilization')
			k = l[0]
			cpu=k.query(datetime.datetime.now()- datetime.timedelta(hours=0,minutes=5), datetime.datetime.now(), 'Maximum', 'Percent')
		print cpu
	return instances

######################
########### create a new ec2 instance worker 
	
@fab.task
def create_worker():
	'''create an on demand worker'''
	interface = boto.ec2.networkinterface.NetworkInterfaceSpecification(subnet_id='subnet-e895688d',groups=['sg-0518e960'],associate_public_ip_address=True)
	interfaces = boto.ec2.networkinterface.NetworkInterfaceCollection(interface)

	reservation = ec_conn.run_instances('ami-043d0f56',instance_type='c3.large',network_interfaces=interfaces, key_name='allservers')
	instance = reservation.instances[0]
	print instance 
	time.sleep(60)
	status = instance.update()
        print status
	if status == 'running':
    	    instance.add_tag("task","worker-new")
    	    instance.add_tag("project","express")
    	    instance.add_tag("Name","vpcw")
	else:
	    print('Instance status: ' + status)
   	    return None

@fab.task
def terminate_worker():
	'''terminate worker oif exceeds'''
	instances = []
        ins = ec_conn.get_all_instances(filters={"tag:task":"worker"})
        for i in ins:
	 if i == ins[4]:
                for j in i.instances:
			print "instance to be terminated is :" + str(j.id)
			ec_conn.terminate_instances(instance_ids=[j.id])
                        print "instance terminated: " +str(j.id)

@fab.task
def create_spot_worker():
	'''create a spot worker'''
        interface = boto.ec2.networkinterface.NetworkInterfaceSpecification(subnet_id='subnet-e895688d',groups=['sg-0518e960'],associate_public_ip_address=True)
        interfaces = boto.ec2.networkinterface.NetworkInterfaceCollection(interface)
        #req = ec_conn.request_spot_instances(.05,'ami-f8eacdaa',type='one-time',instance_type='m3.large',network_interfaces=interfaces, key_name='allservers',user_data = '/home/ubuntu/workers.sh')
        req = ec_conn.request_spot_instances(.5,'ami-ad6846ff',type='one-time',instance_type='c3.8xlarge',network_interfaces=interfaces, key_name='allservers')
        print "request id for the spot instance for worker is : "+ str(req[0])
        print "checking job instance id for this spot request"
        time.sleep(200)
	instances = []
	reservation = ec_conn.get_all_instances(filters={"image_id":'ami-ff4867ad'})
	instance = reservation.instances[0]
        print instance
        time.sleep(160)
        status = instance.update()
        print status
        if status == 'running':
            instances.add_tag("task","worker")
            instances.add_tag("Name","worker-kinko")
        else:
            print('Instance status: ' + status)
            return None

def terminate_instance(instance_id):
        '''terminate instance by id'''
        ec_conn.terminate_instances(instance_id)
#################################################################
###################################################################
@fab.task
def remove_unhealthy_instance_from_elb(elb):
	instances = []
	lb = lb_conn.get_all_load_balancers(load_balancer_names=[elb])[0]
  	instances.extend(lb.instances)
	#elb_instances(elb)
	# get the aws ec2 instance id for the current machine
	#instance_id = boto.utils.get_instance_metadata()['instance-id']
      
	for i in lb.instances:
		for j in i.id:
		#	elb.deregister_instances(j.id)
		        print 'Removing %s from ELB %s' % (i.id, 'elb')
 
			timeout = time.time() + 60*5 # 5 minutes
			while True:
				health = lb_conn.get_instance_health([i.id])[0]
				assert health.instance_id == i.id
				assert time.time() < timeout
		    		if health.state == 'OutOfService':
					break
			print 'Waiting for removal...'
			time.sleep(1)
 
		print 'Done'
 
#def add_this_instance_to_elb(elb_name):
#	elb = elb_name
 #
	# get the aws ec2 instance id for the current machine
#@	instance_id = boto.utils.get_instance_metadata()['instance-id']
 #
#	elb.register_instances(instance_id)
 #
#	start = time.time()
#	print 'Adding %s to ELB %s' % (instance_id, elb.name)
 #
#	timeout = time.time() + 60*5 # 5 minutes
#	while True:
#		health = elb.get_instance_health([instance_id])[0]
#		assert health.instance_id == instance_id
#		assert time.time() < timeout
#		if health.state == 'InService':
#		    break
#	time.sleep(1)
 #
#	print 'Instance %s now successfully InService in ELB %s (took %d seconds)' % (instance_id, elb.name, time.time() - start)
 
