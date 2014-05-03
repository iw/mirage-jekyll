
Mirage with Jekyll on Amazon EC2
================================

## Introduction

[Mirage](http://www.openmirage.org) is emerging as a wondrous approach for producing specialised applications for the cloud.

The following provide fine introduction:

* [Unikernels: Library Operating Systems for the Cloud](http://anil.recoil.org/papers/2013-asplos-mirage.pdf)
* [Unikernels: Rise of the Virtual Library Operating System](http://queue.acm.org/detail.cfm?id=2566628)

## Mirage for serving sites

There are a number of fine articles describing the production of Mirage unikernels for serving static sites:

* [Building mirage-www](http://www.openmirage.org/wiki/mirage-www)
* [From Jekyll site to Unikernel in fifty lines of code](http://amirchaudhry.com/from-jekyll-to-unikernel-in-fifty-lines/)
* [It's a Mirage! (or, How to Shave a Yak.)](http://www.somerandomidiot.com/blog/2014/03/14/its-a-mirage/)

Rather than simply cloning one of the above approaches, I wanted to go with [Test Kitchen](http://kitchen.ci) (with [Vagrant](http://www.vagrantup.com)) for unikernel production with [Packer](http://www.packer.io) for composing [AMIs suitable for launching on EC2](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/UserProvidedKernels.html).

(For the moment, Packer is not used within the workflow. This will be revisited shortly. [Fabric](http://www.fabfile.org) and [boto](http://boto.readthedocs.org/en/latest/) will be used for the AMI production.)

## Choice for static site production

We will be using the wonderful [poole](http://getpoole.com) for our exemplar site, choosing the [Lanyon theme](http://lanyon.getpoole.com).

## Installing the dependencies

The following was performed on Mac OS X 10.9.2.

### Install rbenv

```bash
$ git clone https://github.com/sstephenson/rbenv.git ~/.rbenv
$ echo 'export PATH="$HOME/.rbenv/bin:$PATH"' >> ~/.bash_profile
$ echo 'eval "$(rbenv init -)"' >> ~/.bash_profile
```

### Install the latest OpenSSL release

```bash
$ curl -O http://www.openssl.org/source/openssl-1.0.1g.tar.gz
$ tar xvf openssl-1.0.1g.tar.gz
$ cd openssl-1.0.1g
$ ./Configure darwin64-x86_64-cc --prefix=$HOME/local/openssl-1.0.1g
$ make
$ make install
```

### Install Ruby

```bash
$ curl -O http://cache.ruby-lang.org/pub/ruby/2.1/ruby-2.1.1.tar.gz
$ tar xvf ruby-2.1.1.tar.gz
$ cd ruby-2.1.1
$ ./configure --with-openssl-dir=$HOME/local/openssl-1.0.1g --with-openssl-include-dir=$HOME/local/openssl-1.0.1g/include/openssl --with-openssl-lib-dir=$HOME/local/openssl-1.0.1g/lib --prefix=$HOME/.rbenv/versions/2.1.1
$ make
$ make install
```

### Switch to using our installed Ruby

```bash
$ rbenv rehash
$ ruby -v
ruby 2.0.0p247 (2013-06-27 revision 41674) [universal.x86_64-darwin13]
$ rbenv versions
* system (set by /<home_dir>/.rbenv/version)
  2.1.1
$ ruby -v
ruby 2.1.1p76 (2014-02-24 revision 45161) [x86_64-darwin13.0]
$ rbenv global 2.1.1
$ rbenv rehash
```

### Install Test Kitchen and Berkshelf

Reading the [Getting Started Guide](http://kitchen.ci/docs/getting-started/) for installing Test Kitchen and Berkshelf. These feature in this project's `Gemfile`.

```bash
$ which gem
/<home_dir>/.rbenv/shims/gem
$ gem install bundler
$ rbenv rehash
```

Notice the ``rbenv rehash`` above: this follows the direction "Run this command after you install a new version of Ruby, or install a gem that provides commands" from `https://github.com/sstephenson/rbenv#rbenv-rehash`.

### Install Vagrant

We install [Vagrant 1.5.2](https://dl.bintray.com/mitchellh/vagrant/vagrant_1.5.2.dmg).

### Install VirtualBox

We install [VirtualBox 4.3.10](http://download.virtualbox.org/virtualbox/4.3.10/VirtualBox-4.3.10-93012-OSX.dmg).


## Download the Mirage static site and unikernel builder projects

```bash
$ git clone https://github.com/iw/mirage-lanyon.git
$ git clone https://github.com/iw/mirage-jekyll.git
```

And install Test Kitchen and Berkshelf:

```bash
$ cd mirage-jekyll
$ bundle install
$ bundle show test-kitchen
/<home_dir>/.rbenv/versions/2.1.1/lib/ruby/gems/2.1.0/gems/test-kitchen-1.2.1
$ kitchen version
Test Kitchen version 1.2.1
$ bundle show berkshelf
/<home_dir>/.rbenv/versions/2.1.1/lib/ruby/gems/2.1.0/gems/berkshelf-2.0.14
$ rbenv rehash
$ cd ..
```

Having installed [Jekyll](http://jekyllrb.com) through `Bundler` we can build our site:

```bash
$ cd mirage-lanyon
$ jekyll build
$ cd ..
```

## Installing Python dependencies

We chose to use [pyenv](https://github.com/yyuu/pyenv) for managing our python environments.

```bash
$ cd mirage-jekyll
$ pyenv system
$ python --version
Python 2.7.5
$ mkvirtualenv mirage-jekyll
$ export CFLAGS=-Qunused-arguments
$ export CPPFLAGS=-Qunused-arguments
$ pip install -r requirements.txt
$ cd ..
```

## Provisioning the VM for building the unikernel

Notice: `.kitchen.yml` shares the static site folder (`mirage-lanyon`) with the Vagrant VM. This will need to be changed when choosing your own static site folder.

```bash
$ cd mirage-jekyll
$ kitchen create
$ kitchen converge
$ fab install_mirage
```

## Building the Mirage unikernel

You can test the Mirage UNIX build with:

```bash
$ fab build_unix_unikernel:build_dir=/home/vagrant/mirage-lanyon/_mirage
```

To build the Mirage Xen unikernel:

```bash
$ fab build_xen_unikernel:build_dir=/home/vagrant/mirage-lanyon/_mirage
```

## Building the Mirage unikernel

The following assumes we have defined:

* an AWS key pair `mirage-www`
* an AWS security group `mirage-unikernel-builder` (allowing SSH access)
* an AWS security group `mirage-www` (allowing HTTP access on port 80)
* envars `AWS_ACCESS_KEY` and `AWS_SECRET_KEY` containing the respective AWS access keys

Building the unikernel:

```bash
$ fab -i ~/.ssh/mirage-www.pem build_mirage_ami:access_key="$AWS_ACCESS_KEY",secret_key="$AWS_SECRET_KEY",xen_unikernel=`pwd`/../mirage-lanyon/_mirage/mir-www.xen
```

Note the "Registered unikernel AMI" that is displayed from performing the above.

Launching the unikernel:

Using the unikernel AMI from the previous step, we can now launch an instance serving our static site:

```bash
$ fab -i ~/.ssh/mirage-www.pem launch_mirage:access_key="$AWS_ACCESS_KEY",secret_key="$AWS_SECRET_KEY",image_id=<unikernel_ami_id>
```

If you have the AMI Tools installed you can monitor the progress of the launching of the unikernel with:

```bash
$ ec2-get-console-output --region eu-west-1 <unikernel_instance_id>
```
