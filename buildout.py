#!/usr/bin/env python3

import boto3
import subprocess
import time
from argparse import ArgumentParser

class Instance:
    def __init__(self, instance_id, user='ec2-user'):
        ec2 = boto3.resource('ec2')
        instance = ec2.Instance(instance_id)
        public_ip = instance.public_ip_address
        ip = public_ip if public_ip is not None else instance.private_ip_address
        self.address = '{}@{}'.format(user, ip)
        self.pem_file = '~/.ssh/{}.pem'.format(instance.key_name)

    def ssh(self, command):
        return subprocess.check_output([
            '/usr/bin/ssh',
            '-i', self.pem_file,
            '-o', 'StrictHostKeyChecking=no',
            self.address,
            command
        ])

    def scp(self, filename, dest=''):
        return subprocess.check_output([
            '/usr/bin/scp' ,
            '-i', self.pem_file,
            '-o', 'StrictHostKeyChecking=no',
            filename,
            '{}:{}'.format(self.address, dest)
        ])


def create_stack(stack_name, **kwargs):
    cloudformation = boto3.resource('cloudformation')

    with open('lanlytics-api.template', 'r') as f:
        template_body = f.read()

    parameters = [{'ParameterKey': key, 'Parameter': val, 'UsePrevious': False}
                    for key, val in kwargs.items()]

    stack = cloudformation.create_stack(
        StackName=stack_name,
        TemplateBody=template_body,
        Parameters=parameters,
        ResourceTypes=['AWS::*']
    )

    # Wait for stack to be created
    while stack.stack_status not in ['CREATE_COMPLETE', 'CREATE_FAILED']:
        time.sleep(1)

    if stack.stack_status == 'CREATE_FAILED':
        raise RuntimeError('Stack creation failed: {}'.format(stack.stack_status_reason))

    return stack.outputs


def deploy_registry(registry_instance, registry_bucket):
    print('Building docker registry')
    remote_dest = '~/docker-registry/'
    files = ['docker-compose.yml', 
             'config.yml', 
             'requirements.txt', 
             'create_config.py',
             'nginx.conf']
    print('Copying files')
    registry_instance.scp(' '.join(files), remote_dest)
    print('Installing Python packages')
    registry_instance.ssh('pip install -r ~/docker-registry/requirements.txt')
    print('Creating configuration')
    registry_instance.ssh('cd docker-registry && ./create_config.py {}'.format(registry_bucket))
    print('Launching application')
    registry_instance.ssh('cd docker-registry && docker-compose up -d --force-recreate')


def deploy_api_server(api_instance):
    print('Building API server')
    remote_dest = '~/lanlytics-api/'
    files = ['deploy-requirements.txt',
             'create_compose.py',
             'nginx.conf',
             'lanlytics-api.tar']
    print('Copying files')
    api_instance.ssh('mkdir lanlytics-api')
    api_instance.scp(' '.join(files), remote_dest)
    print('Loading Docker image')
    api_instance.ssh('docker load -i ~/lanlytics-api/lanlytics-api.tar')
    print('Installing Python packages')
    api_instance.ssh('pip install -r ~/lanlytics-api/deploy-requirements.txt')
    print('Creating configuration')
    api_instance.ssh('cd lanlytics-api && ./create_compose.py')
    print('Launching application')
    api_instance.ssh('cd lanlytics-api && docker-compose up -d --force-recreate')


def deploy_worker(worker_instance):
    print('Building API worker')
    api_instance.ssh('mkdir lanlytics-api-worker')
    remote_dest = '~/lanlytics-api-worker/'
    print('Copying files')
    worker_instance.scp('lanlytics-api-worker.tar', remote_dest)
    print('Loading Docker image')
    worker_instance.ssh('docker load -i ~/lanlytics-api-worker/lanlytics-api-worker.tar')
    print('Launching worker')
    worker_instance.ssh('sudo yum install jq -y')
    worker_instance.ssh('docker run -d \
            -e AWS_DEFAULT_REGION=$(curl --silent http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region) \
            -v /home/ec2-user:/home/ec2-user \
            -v /var/run/docker.sock:/var/run/docker.sock \
            --restart always \
            lanlytics-api-worker docker')


def create_worker_ami(instance_id):
    ec2 = boto3.resource('ec2')
    worker_instance = ec2.Instance(instance_id)
    image = worker_instance.create_image(name='lanlytics-api-worker')
    return image.image_id


def buildout_api(args):
    stack_parameters = vars(args)
    stack_name = stack_parameters.pop('name')
    outputs = create_stack(stack_name, **stack_parameters)
    api_server = Instance(outputs[0]['OutputValue'])
    registry = Instance(outputs[1]['OutputValue'])
    worker = Instance(outputs[2]['OutputValue'])
    redis_endpoint = outputs[3]['OutputValue']

    deploy_registry(registry)
    deploy_api_server(api_server)
    deploy_worker(worker)
    create_worker_ami(worker)

    print('All done; go home')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('name', help='Name for the CloudFormation stack')
    parser.add_argument('BaseImageId', help='Base AMI Id for instances')
    parser.add_argument('KeyName', help='Key pair name for launched instances')
    parser.add_argument('--vpc-ip-block', dest='IpBlock', default='10.0.0.0/16', help='Set of IP addresses for the VPC')
    parser.add_argument('--subnet-ip-block', dest='SubnetIpBlock', default='10.0.0.0/24', help='Set of IP addresses for the subnet')
    parser.add_argument('--ssh-ip', dest='SSHIP', default='0.0.0.0/0', help='IP to restrict SSH access')
    parser.add_argument('--jobs-table', dest='DynamoDBJobsTableName', default='jobs', help='DynamoDB table name for job storage')
    parser.add_argument('--worker-bucket', dest='S3WorkerBucketName', default='lanlytics-api-worker', help='S3 bucket for API workers')
    parser.add_argument('--image-bucket', dest='S3DockerImageBucketName', default='lanlytics-registry-images', help='S3 bucket for Docker Registry')
    args = parser.parse_args()
    buildout_api(args)
