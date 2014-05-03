
from datetime import datetime
import os
import sys
import time

import boto.ec2
from fabric.api import cd, env, prefix, put, run, settings, sudo, task


env.user = 'vagrant'
env.hosts = ['127.0.0.1:2222']
key_fname = os.path.join('~', '.vagrant.d', 'insecure_private_key')
env.key_filename = os.path.expanduser(key_fname)


@task
def install_mirage():
    """Initialise OPAM and install the mirage package."""
    run('opam init -a --dot-profile="~/.bash_profile"')
    with prefix('eval `opam config env`'):
        run('opam install -y mirage')


@task
def build_unix_unikernel(build_dir=None):
    """Produce a Unix unikernel.

    Args:
      build_dir: directory containing the config.ml configuration.
    """
    if build_dir is None:
        sys.exit('Build directory is required')
    with cd(build_dir):
        with prefix('eval `opam config env`'):
            run('env NET=socket FS=crunch mirage configure --unix')
            run('make')


@task
def build_xen_unikernel(build_dir=None):
    """Produce a Mirage unikernel capable of running on Amazon EC2.

    Args:
      build_dir: directory containing the config.ml configuration.
    """
    if build_dir is None:
        sys.exit('Build directory is required')
    with cd(build_dir):
        with prefix('eval `opam config env`'):
            run('env DHCP=true FS=crunch mirage configure --xen')
            run('make')


@task
def build_mirage_ami(access_key=None,
                     secret_key=None,
                     region='eu-west-1',
                     availability_zone='eu-west-1b',
                     xen_unikernel=None):
    """Produce a Mirage unikernel capable of running on Amazon EC2.

    Args:
      access_key: AWS access key
      secret_key: AWS secret access key
      region: Region where we launch the build host
      availability_zone: Availability Zone for the build host EBS block
      xen_unikernel: path of the Xen image (Mirage unikernel)
    """
    if secret_key is None:
        sys.exit('AWS access key is required')
    if access_key is None:
        sys.exit('AWS secret access key is required')
    if xen_unikernel is None:
        sys.exit('Path for the Mirage unikernel is required')

    conn = boto.ec2.connect_to_region(region,
                                      aws_access_key_id=access_key,
                                      aws_secret_access_key=secret_key)

    # Launch the instance responsible for composing the unikernal image
    reservation = conn.run_instances(
        'ami-2d18e35a',
        key_name='mirage-www',
        instance_type='t1.micro',
        security_groups=['mirage-unikernel-builder'])

    build_host = reservation.instances[0]
    print('Launched the build host ' + build_host.id)
    while build_host.state != 'running':
        build_host.update()
        time.sleep(1)
    print('The build host ' + build_host.id + ' is now running')
    print('The build host ip ' + build_host.ip_address)

    # Create the EBS volume which will become the unikernal AMI
    kernel_image = conn.create_volume(1, availability_zone)
    print('Created the EBS volume ' + kernel_image.id)
    # and attach it to our build host
    while kernel_image.status != 'available':
        kernel_image.update()
        time.sleep(1)
    kernel_image.attach(build_host.id, '/dev/sdh')
    print('Attaching the EBS volume to the build host')
    while kernel_image.attachment_state() != 'attached':
        kernel_image.update()
        time.sleep(1)
    print('Attached the EBS volume to the build host')

    time.sleep(120)

    mirage_key_fname = os.path.join('~', '.ssh', 'mirage-www.pem')
    with settings(user='ec2-user',
                  hosts=[build_host.ip_address + ':22'],
                  host_string=build_host.ip_address + ':22',
                  key_filename=os.path.expanduser(mirage_key_fname),
                  connection_attempts=5):
        sudo('mkfs.ext2 /dev/sdh')
        sudo('mount -t ext2 /dev/sdh /mnt')
        sudo('mkdir -p /mnt/boot/grub')
        run('echo default 0 > menu.lst')
        run('echo timeout 1 >> menu.lst')
        run('echo title Mirage >> menu.lst')
        run('echo "root (hd0)" >> menu.lst')
        run('echo "kernel /boot/mirage-os.gz" >> menu.lst')
        sudo('mv menu.lst /mnt/boot/grub/menu.lst')

        # Copy the unikernel to the build host
        put(xen_unikernel)
        print('Copied the unikernel to the build host')

        xen_fname = os.path.basename(xen_unikernel)
        sudo('sh -c "gzip -c /home/ec2-user/' + xen_fname +
             ' > /mnt/boot/mirage-os.gz"')
        sudo('umount -d /mnt')

    kernel_image_snapshot = conn.create_snapshot(kernel_image.id)
    print('Created the kernel image snapshot ' + kernel_image_snapshot.id)
    while kernel_image_snapshot.status != 'completed':
        kernel_image_snapshot.update()
        time.sleep(1)

    time_now = datetime.now()
    unikernel_name = 'mirage-' + time_now.strftime('%Y%m%d%H%M')
    # Kernel IDs can be found here
    # http://docs.aws.amazon.com/AWSEC2/latest/
    #   UserGuide/UserProvidedKernels.html
    image_id = conn.register_image(
        name=unikernel_name,
        architecture='x86_64',
        kernel_id='aki-52a34525',
        snapshot_id=kernel_image_snapshot.id,
        root_device_name='/dev/sdh')

    print('Registered unikernel AMI ' + image_id)


@task
def launch_mirage(access_key=None,
                  secret_key=None,
                  region='eu-west-1',
                  image_id=None):
    """Launch a Mirage unikernel.

    Args:
      access_key: AWS access key
      secret_key: AWS secret access key
      region: Region in which we will launch the instance
      image_id: AMI identifier
    """
    if secret_key is None:
        sys.exit('AWS access key is required')
    if access_key is None:
        sys.exit('AWS secret access key is required')
    if image_id is None:
        sys.exit('Unikernel AMI id is required')

    conn = boto.ec2.connect_to_region(region,
                                      aws_access_key_id=access_key,
                                      aws_secret_access_key=secret_key)

    # Launch the Mirage unikernel
    reservation = conn.run_instances(
        image_id,
        instance_type='t1.micro',
        security_groups=['mirage-www'])

    unikernel = reservation.instances[0]
    print('Launched unikernel with instance id: ' + unikernel.id)
