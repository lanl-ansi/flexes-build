# EC2 Deployment Test

These are some notes on how the "geotiff2json-worker" AMI was built.

My experince has been if you want to setup an instance to run something on startup it is best to install everything as root (and not ec2-user), becouse the launch script is run as root.

## Setup Steps

- spin up clean ec2 instance and ssh to it
- `sudo su root` to switch to root 
- `yum update` get latest packages

### python3 install
- `yum install -y python35`
- `curl https://bootstrap.pypa.io/get-pip.py | python3` pip3 install

### docker install
- `yum install -y docker`
- `service docker start`
- `docker info` check that docker is working
- load any images that all workers should have, without reaching out to docker-hub

### worker install
- checkout or copy the repo to `/lanlytics-api-worker` (checking out the worker will require installing git `yum install -y git`)
- from the worker directory, 
  - `pip3 install -r requirements.txt`
  - test the worker will start with `python3 worker.py <some docker image name> 5

- stop the EC2 instance and save a new AMI

# Launcing the Worker AMI(s)

## Role

- make sure the role is setup as "Service", otherwise the worker.py will die

## Basic User Data Sctipt (run when the instance boots)

Putting this script as plane text "user data" should start the worker in the background on startup.

```
#!/bin/bash

export AWS_DEFAULT_REGION="us-gov-west-1"

cd lanlytics-api-worker

python3 worker.py geotiff2json 5 &

```

To debug the worker stat, shh into an instance and check for the process with `ps aux | grep python`

The startup log can be viewed at `/var/log/cloud-init-output.log`
