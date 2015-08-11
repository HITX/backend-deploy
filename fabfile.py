import errno
import os, json
from tempfile import mkdtemp
from contextlib import contextmanager

from fabric.operations import open_shell, put
from fabric.api import env, local, sudo, run, cd, prefix, task, settings, execute
from fabric.colors import green as _green, yellow as _yellow
from fabric.context_managers import hide, show, lcd
import boto
import boto.ec2
import boto.rds
import time

# from fabric.network import key_filenames, ssh
# ssh.util.log_to_file("paramiko.log", 10)

# ------ SETTINGS --------

# Read in configurable settings.
deploy_settings = {
    'aws_access_key_id': None,
    'aws_secret_access_key': None,
    'aws_default_region': None,
    'aws_ssh_key_name': None,
    'aws_ssh_port': None,
    'aws_ec2_instance_type': None,
    'aws_ec2_ami_id': None,
    'aws_ec2_security_group_name': None,
    'aws_rds_allocated_storage': None,
    'aws_rds_instance_class': None,
    'aws_rds_master_username': None,
    'aws_rds_master_password': None,
    'aws_rds_database_name': None,
    'aws_rds_security_group_name': None,
}
for name, value in deploy_settings.items():
    env_value = os.getenv(name.upper())
    env[name] = env_value
    if not env_value:
        raise Exception("Please make sure to enter your AWS keys/info in your deploy/environment file before running fab scripts. {} is currently set to {}".format(name, value))

# Define non-configurable settings
env.root_directory = os.path.dirname(os.path.realpath(__file__))
env.deploy_directory = os.path.join(env.root_directory, 'deploy')
env.app_settings_directory = os.path.join(env.deploy_directory, 'settings')
env.app_settings_base = os.path.join(env.app_settings_directory, 'base.json')
env.app_settings_deploy_key = os.path.join(env.app_settings_directory, 'deploy_key')
env.fab_hosts_directory = os.path.join(env.deploy_directory, 'fab_hosts')
env.ssh_directory = os.path.join(env.deploy_directory, 'ssh')
env.aws_ssh_key_extension = '.pem'
env.aws_ssh_key_path = os.path.join(
    env.ssh_directory,
    ''.join([env.aws_ssh_key_name, env.aws_ssh_key_extension]))

# ------ FABRIC TASKS -------

@task
def setup_aws_account():

    prep_paths(env.ssh_directory, env.deploy_directory)

    ec2 = connect_to_ec2()
    # rds = connect_to_rds()

    # Check to see if specified keypair already exists.
    # If we get an InvalidKeyPair.NotFound error back from EC2,
    # it means that it doesn't exist and we need to create it.
    try:
        key_name = env.aws_ssh_key_name
        key = ec2.get_all_key_pairs(keynames=[key_name])[0]
        print "key name {} already exists".format(key_name)
    except ec2.ResponseError, e:
        if e.code == 'InvalidKeyPair.NotFound':
            print 'Creating keypair: %s' % env.aws_ssh_key_name
            # Create an SSH key to use when logging into instances.
            key = ec2.create_key_pair(env.aws_ssh_key_name)

            # AWS will store the public key but the private key is
            # generated and returned and needs to be stored locally.
            # The save method will also chmod the file to protect
            # your private key.
            key.save(directory_path=env.ssh_directory)
        else:
            raise

    # Check to see if specified security group already exists.
    # If we get an InvalidGroup.NotFound error back from EC2,
    # it means that it doesn't exist and we need to create it.
    try:
        ec2_group = ec2.get_all_security_groups(groupnames=[env.aws_ec2_security_group_name])[0]  # noqa
    except ec2.ResponseError, e:
        if e.code == 'InvalidGroup.NotFound':
            print 'Creating EC2 Security Group: %s' % env.aws_ec2_security_group_name
            # Create a security group to control access to instance via SSH.
            ec2_group = ec2.create_security_group(env.aws_ec2_security_group_name,
                                              'A group that allows SSH and HTTP access')
        else:
            raise

    try:
        rds_group = ec2.get_all_security_groups(groupnames=[env.aws_rds_security_group_name])[0]
    except ec2.ResponseError, e:
        if e.code == 'InvalidGroup.NotFound':
            print 'Creating RDS Security Group: %s' % env.aws_rds_security_group_name
            rds_group = ec2.create_security_group(env.aws_rds_security_group_name,
                                                'A group that allows SSH and Postgres access')
        else:
            raise

    # try:
    #     rds_param_group = get_all_dbparameter_groups(groupname=[env.aws_rds_parameter_group_name])[0]
    # except rds.ResponseError, e:
    #     if e.code == '':
    #         print 'Creating RDS Parameter Group: %s' % env.aws_rds_parameter_group_name
    #         pg = rds.create_parameter_group(name='dbparamgrp',
    #                                     description='My DB parameter group.')
    #     else:
    #         raise

    # Add a rule to the security group to authorize SSH traffic
    # on the specified port.
    for port in ["80", env.aws_ssh_port]:
        try:
            ec2_group.authorize('tcp', port, port, "0.0.0.0/0")
        except ec2.ResponseError, e:
            if e.code == 'InvalidPermission.Duplicate':
                print 'Security Group: %s already authorized' % env.aws_ec2_security_group_name  # noqa
            else:
                raise

    for port in ["5432", env.aws_ssh_port]:
        try:
            rds_group.authorize('tcp', port, port, src_group=ec2_group)
        except ec2.ResponseError, e:
            if e.code == 'InvalidPermission.Duplicate':
                print 'Security Group: %s alsready authorized' %env.aws_rds_security_group_name
            else:
                raise

    # postgres authorization
    # try:
    #     group.authorize('tcp', 5432, 5432, src_group=group)
    # except ec2.ResponseError, e:
    #     if e.code == 'InvalidPermission.Duplicate':
    #         print 'Security Group: %s already authorized' % env.aws_security_group_name  # noqa
    #     else:
    #         raise

@task
def create_instance(name, tag=None):
    """
    Launch an instance and wait for it to start running.
    Returns a tuple consisting of the Instance object and the CmdShell
    object, if request, or None.
    tag        A name that will be used to tag the instance so we can
               easily find it later.
    """

    prep_paths(env.ssh_directory, env.deploy_directory)

    print(_green("Started creating {}...".format(name)))
    print(_yellow("...Creating EC2 instance..."))

    conn = connect_to_ec2()

    try:
        key = conn.get_all_key_pairs(keynames=[env.aws_ssh_key_name])[0]
        group = conn.get_all_security_groups(groupnames=[env.aws_ec2_security_group_name])[0]  # noqa
    except conn.ResponseError, e:
        setup_aws_account()

    reservation = conn.run_instances(
        env.aws_ec2_ami_id,
        key_name=env.aws_ssh_key_name,
        security_groups=[env.aws_ec2_security_group_name],
        instance_type=env.aws_ec2_instance_type)

    instance = reservation.instances[0]
    conn.create_tags([instance.id], {"Name":name})
    if tag:
        instance.add_tag(tag)
    while instance.state != u'running':
        print(_yellow("Instance state: %s" % instance.state))
        time.sleep(10)
        instance.update()

    print(_green("Instance state: %s" % instance.state))
    print(_green("Public dns: %s" % instance.public_dns_name))

    host_data = {
        'host_string': instance.public_dns_name,
        'port': '22',
        'user': 'ubuntu',
        'key_filename': env.aws_ssh_key_path,
    }
    with open(os.path.join(env.ssh_directory, ''.join([name, '.json'])), 'w') as f:  # noqa
        json.dump(host_data, f)

    # f = open("deploy/fab_hosts/{}.txt".format(name), "w")
    f = open(os.path.join(env.fab_hosts_directory, ''.join([name, '.txt'])), 'w')
    f.write(instance.public_dns_name)
    f.close()
    return instance.public_dns_name

@task
def terminate_instance(name):
    """
    Terminates all servers with the given name
    """

    print(_green("Started terminating {}...".format(name)))

    conn = connect_to_ec2()
    filters = {"tag:Name": name}
    for reservation in conn.get_all_instances(filters=filters):
        for instance in reservation.instances:
            if "terminated" in str(instance._state):
                print "instance {} is already terminated".format(instance.id)
                continue
            else:
                print instance._state
            print (instance.id, instance.tags['Name'])
            if raw_input("terminate? (y/n) ").lower() == "y":
                print(_yellow("Terminating {}".format(instance.id)))
                conn.terminate_instances(instance_ids=[instance.id])
                os.remove(os.path.join(env.ssh_directory, ''.join([name, '.json'])))  # noqa
                os.remove(os.path.join(env.fab_hosts_directory, ''.join([name, '.txt'])))
                print(_yellow("Terminated"))

@task
def create_database(name):
    prep_paths(env.ssh_directory, env.deploy_directory)

    print(_green("Started creating database {}...".format(name)))
    print(_yellow("...Creating RDS instance..."))

    ec2 = connect_to_ec2()
    rds = connect_to_rds()

    try:
        # key = conn.get_all_key_pairs(keynames=[env.aws_ssh_key_name])[0]
        group = ec2.get_all_security_groups(groupnames=[env.aws_rds_security_group_name])[0]  # noqa
    except ec2.ResponseError, e:
        setup_aws_account()

    # TODO: Get rds instance in proper security group
    try:
        rds.create_dbinstance(
            name,
            allocated_storage=env.aws_rds_allocated_storage,
            instance_class=env.aws_rds_instance_class,
            engine='postgres',
            port=5432,
            master_username=env.aws_rds_master_username,
            master_password=env.aws_rds_master_password,
            db_name=env.aws_rds_database_name)
            # vpc_security_groups=[group.vpc_id])
    except rds.ResponseError, e:
        print "Error creating database '{}'".format(env.aws_rds_database_name)
        print "{}: {}".format(e.code, e.message)
        return

    db_settings = {
        'DB_NAME': env.aws_rds_database_name,
        'DB_USERNAME': env.aws_rds_master_username,
        'DB_PASSWORD': env.aws_rds_master_password,
    }

    with open(os.path.join(env.app_settings_directory, ''.join([name, '.json'])), 'w') as f:
        json.dump(db_settings, f)


@task
def ssh(name):
    """SSH into an instance."""
    with open(os.path.join(env.ssh_directory, ''.join([name, '.json'])), 'r') as f:  # noqa
        host_data = json.load(f)
    with settings(**host_data):
        open_shell()

@task
def bootstrap(name, no_install=False, dbname=None):
    """
    Bootstrap the specified server. Install chef then run chef solo.
    :param name: The name of the node to be bootstrapped
    :param no_install: Optionally skip the Chef installation
    since it takes time and is unneccesary after the first run
    :return:
    """

    print(_green("--BOOTSTRAPPING {}--".format(name)))
    f = open("deploy/fab_hosts/{}.txt".format(name))
    env.host_string = "ubuntu@{}".format(f.readline().strip())
    if dbname != None:
        build_databag(dbname)
    if not no_install:
        install_chef()
    run_chef(name)

# @task
# def deploy(name):
#     """
#     Bootstrap the specified server. Install chef then run chef solo.
#     :param name: The name of the node to be bootstrapped
#     :param no_install: Optionally skip the Chef installation
#     since it takes time and is unneccesary after the first run
#     :return:
#     """
#
#     print(_green("--DEPLOYING {}--".format(name)))
#     f = open("deploy/fab_hosts/{}.txt".format(name))
#     env.host_string = "ubuntu@{}".format(f.readline().strip())
#     deploy_app(name)
#
# @task
# def restart():
#     """
#     Reload nginx/gunicorn
#     """
#     with settings(warn_only=True):
#         with open(env.app_settings_file) as f:
#             app_settings = json.load(f)
#         sudo("supervisorctl restart {app_name}".format(app_name=app_settings["APP_NAME"]))
#         sudo('/etc/init.d/nginx reload')

#------- HELPER FUNCTIONS ------

def prep_paths(ssh_directory, deploy_directory):
    try:
        os.makedirs(ssh_directory)
    except OSError as exception:
        if exception.errno == errno.EEXIST and os.path.isdir(ssh_directory):
            pass
        else:
            raise
    os.chmod(deploy_directory, 0700)
    os.chmod(ssh_directory, 0700)

@contextmanager
def _virtualenv():
    with prefix(env.activate):
        yield

def connect_to_ec2():
    """
    return a connection given credentials imported from config
    """
    ec2_connection = boto.ec2.connect_to_region(
        env.aws_default_region,
        aws_access_key_id=env.aws_access_key_id,
        aws_secret_access_key=env.aws_secret_access_key)
    if not ec2_connection:
        raise Exception("We're having a problem connecting to your AWS account. Are you sure you entered your credentials correctly?")
    return ec2_connection

def connect_to_rds():
    rds_connection = boto.rds.connect_to_region(
        env.aws_default_region,
        aws_access_key_id=env.aws_access_key_id,
        aws_secret_access_key=env.aws_secret_access_key)
    if not rds_connection:
        raise Exception("We're having a problem connecting to your AWS account. Are you sure you entered your credentials correctly?")
    return rds_connection

def build_databag(dbname):
    print(_yellow("--BUILDING DATA BAG--"))
    rds = connect_to_rds()

    # Get database host information
    try:
        inst = rds.get_all_dbinstances(instance_id=dbname)[0]
    except rds.ResponseError, e:
        print "{}: {}".format(e.code, e.message)
        return

    old_status = inst.status
    while inst.status != 'available':
        if inst.status == 'failed':
            print(_red("Instance failed"))
            return False

        if inst.status != old_status:
            print(_yellow("Waiting for database {}. Status: {}".format(dbname, inst.status)))
            old_status = inst.status
        time.sleep(10)
        inst.update()

    db_host = inst.endpoint[0]
    db_port = inst.endpoint[1]

    # Add ec2 and db host to tmp settings
    tmp_settings = {
        'EC2_HOST': env.host_string,
        'DB_HOST': db_host,
        'DB_PORT': db_port
    }

    # Add base settings to tmp settings
    with open(env.app_settings_base, 'r') as f:
        tmp_settings.update(json.load(f))

    # Add db settings to tmp settings
    with open(os.path.join(env.app_settings_directory, ''.join([dbname, '.json'])), 'r') as f:
        tmp_settings.update(json.load(f))

    # Add deploy key to tmp settings
    with open(env.app_settings_deploy_key, 'r') as f:
        tmp_settings.update({
            'GITHUB_DEPLOY_KEY': f.read().replace('\n', '\\n')
        })

    # Write out tmp settings
    tmp_settings_path = 'chef_repo/tmp_settings.json'
    with open(tmp_settings_path, 'w') as f:
        json.dump(tmp_settings, f)


    data_bag_key_exists = os.path.isfile('chef_repo/data_bag_key')
    with settings(warn_only=True):
        with lcd('chef_repo'):
            if not data_bag_key_exists:
                # Create data bag key if not exists
                local('openssl rand -base64 512 > data_bag_key')
            # Create data bag
            local('knife solo data bag create config config_1 --json-file tmp_settings.json')

    # Delete tmp settings file
    os.remove(tmp_settings_path)

    return True

def install_chef():
    """
    Install chef-solo on the server.
    """
    print(_yellow("--INSTALLING CHEF--"))
    local("knife solo prepare -i {key_file} {host}".format(
        key_file=env.aws_ssh_key_path,
        host=env.host_string))

def run_chef(name):
    """
    Read configuration from the appropriate node file and bootstrap
    the node
    :param name:
    :return:
    """
    print(_yellow("--RUNNING CHEF--"))
    node = "./nodes/{name}_node.json".format(name=name)
    with lcd('chef_repo'):
        # local("pwd")
        local("knife solo cook -i {key_file} {host} {node}".format(
            key_file=env.aws_ssh_key_path,
            host=env.host_string,
            node=node))
#
# def deploy_app(name):
#
#     print(_yellow("--DEPLOYING APP--"))
#     node = "./nodes/deploy_node.json".format(name=name)
#
#     with lcd('chef_files'):
#         try:
#             # skip updating the Berkshelf cookbooks to save time
#             os.rename("chef_files/Berksfile", "chef_files/hold_Berksfile")
#             local("knife solo cook -i {key_file} {host} {node}".format(
#                 key_file=env.aws_ssh_key_path,
#                 host=env.host_string,
#                 node=node))
#             restart()
#         except Exception as e:
#             print e
#         finally:
#             os.rename("chef_files/hold_Berksfile", "chef_files/Berksfile")
