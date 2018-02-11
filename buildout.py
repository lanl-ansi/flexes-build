#!/usr/bin/env python

import boto3
import json
import subprocess
import time
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from __future__ import print_function

class Instance:
    def __init__(self, instance_id, user='ec2-user'):
        ec2 = boto3.resource('ec2')
        self.instance = ec2.Instance(instance_id)
        self.instance.wait_until_running()
        public_ip = self.instance.public_ip_address
        private_ip = self.instance.private_ip_address
        self.ip = public_ip if public_ip else private_ip_address
        self.user = user
        self.pem_file = '~/.ssh/{}.pem'.format(self.instance.key_name)

    def ssh(self, command):
        return subprocess.check_output([
            '/usr/bin/ssh',
            '-i', self.pem_file,
            '-o', 'StrictHostKeyChecking=no',
            '{}@{}'.format(self.user, self.ip),
            command
        ])

    def scp(self, filename, dest='', to='remote'):
        if to == 'remote':
            return subprocess.check_output([
                '/usr/bin/scp' ,
                '-i', self.pem_file,
                '-o', 'StrictHostKeyChecking=no',
                filename,
                '{}@{}:{}'.format(self.user, self.ip, dest)
            ])
        else:
            return subprocess.check_output([
                '/usr/bin/scp' ,
                '-i', self.pem_file,
                '-o', 'StrictHostKeyChecking=no',
                '{}@{}:{}'.format(self.user, self.ip, filename),
                dest
            ])

    def create_ami(self, name):
        ec2 = boto3.resource('ec2')
        image = self.instance.create_image(Name=name)
        return image.image_id

    def add_security_group(self, security_group_id):
        all_sg = [sg['GroupId'] for sg in self.instance.security_groups]
        all_sg.append(security_group_id)
        self.instance.modify_attribute(Groups=all_sg)


def create_stack(stack_name, template, **kwargs):
    cloudformation = boto3.resource('cloudformation')

    with open(template, 'r') as f:
        template_body = f.read()

    parameters = [{'ParameterKey': key, 'ParameterValue': val, 'UsePreviousValue': False}
                    for key, val in kwargs.items() if val is not None]

    stack = cloudformation.create_stack(
        StackName=stack_name,
        TemplateBody=template_body,
        Parameters=parameters,
        Capabilities=['CAPABILITY_NAMED_IAM']
    )

    # Wait for stack to be created
    print('Building stack {}'.format(stack_name), end='', flush=True)
    while stack.stack_status not in ['CREATE_COMPLETE', 'CREATE_FAILED']:
        time.sleep(1)
        stack.reload()
        print('.', end='')
        sys.stdout.flush()
    print()

    if stack.stack_status == 'CREATE_FAILED':
        raise RuntimeError('Stack creation failed: {}'.format(stack.stack_status_reason))

    return stack.outputs


def create_api_settings(jobs_table, redis_endpoint):
    with open('settings.py', 'w') as f:
        f.write("REDIS_HOST = '{}'\n".format(redis_endpoint))
        f.write("REDIS_PORT = 6379\n")
        f.write("TABLE_NAME = '{}'\n".format(jobs_table))
    subprocess.call('tar --append --file=lanlytics-api.tar settings.py && \
                     rm settings.py', shell=True)


def create_worker_settings(registry, jobs_table, redis_endpoint, api_endpoint):
    with open('settings.py', 'w') as f:
        f.write("STATUS_COMPLETE = 'complete'\n")
        f.write("STATUS_ACTIVE = 'active'\n")
        f.write("STATUS_RUNNING = 'running'\n")
        f.write("STATUS_FAIL = 'failed'\n")
        f.write("DOCKER_WORKER_TYPE = 'docker'\n")
        f.write("DOCKER_REGISTRY = '{}'\n".format(registry))
        f.write("JOBS_TABLE = '{}'\n".format(jobs_table))
        f.write("REDIS_HOST = '{}'\n".format(redis_endpoint))
        f.write("REDIS_PORT = 6379\n")
        f.write("API_ENDPOINT = 'https://{}'\n".format(api_endpoint))
    subprocess.call('tar --append --file=lanlytics-api-worker.tar settings.py && \
                     rm settings.py', shell=True)


def deploy_base_instance(base_instance):
    print('Build base AMI')
    remote_dest = '~/'
    files = ['docker.tar']
    print('Copying files')
    base_instance.scp(' '.join(files), '~/')
    base_instance.ssh('tar -xf {}'.format(files[0]))
    print('Moving binaries')
    base_instance.ssh('cd docker && \
                       chmod +x cgroupfs-mount && \
                       sudo ./cgroupfs-mount && \
                       tar xzvf docker.tgz && \
                       sudo cp docker/* /usr/bin/ && \
                       sudo cp docker.service /etc/init.d/docker')
    base_instance.ssh('sudo dockerd &')
    base_instance.ssh('sudo docker --version && \
                       sudo groupadd docker && \
                       sudo usermod -aG docker {}'.format(base_instance.user))
    base_instance.ssh('sudo service docker start && sudo chkconfig docker on')
    print(base_instance.ssh('docker --version'))
    base_instance.ssh('chmod +x docker/docker-compose && sudo mv docker/docker-compose /usr/bin/')
    print(base_instance.ssh('docker-compose --version'))
    base_instance.ssh('rm -r docker && rm docker.tar')


def deploy_registry(registry, registry_bucket):
    region = registry.instance.placement['AvailabilityZone'][:-1]
    print('Building docker registry')
    files = ['docker-registry.tar']
    print('Copying files')
    registry.scp(' '.join(files), '~/')
    registry.ssh('tar -xf {}'.format(files[0]))
    registry.ssh("cd docker-registry && \
                  sed -i 's/<aws-region>/{}/g' config.yml && \
                  sed -i 's/<s3-bucket>/{}/g' config.yml".format(region, registry_bucket))
    print('Launching application')
    registry.ssh('gunzip -c ~/docker-registry/docker-registry.tgz | docker load')
    registry.ssh('cd docker-registry && \
                  openssl req -x509 -subj /CN={} -newkey rsa:4096 -keyout server.key -out cert.crt -days 1000 -nodes && \
                  docker-compose -f docker-compose-ssl.yml up -d --force-recreate'.format(registry.instance.private_dns_name))
    print('Copying SSL certificate')
    registry.scp('~/docker-registry/cert.crt', '.', to='local')
    return 'cert.crt'


def deploy_api_server(api):
    print('Building API server')
    files = ['lanlytics-api.tar']
    print('Copying files')
    api.scp(' '.join(files), '~/')
    api.ssh('tar -xf {}'.format(files[0]))
    api.ssh('mv settings.py ~/lanlytics-api/')
    print('Loading Docker image')
    api.ssh('gunzip -c ~/lanlytics-api/lanlytics-api-server.tgz | docker load')
    print('Launching application')
    api.ssh('cd lanlytics-api && \
             openssl req -x509 -subj /CN={} -newkey rsa:4096 -keyout server.key -out cert.crt -days 1000 -nodes && \
             docker-compose -f docker-compose-ssl.yml up -d --force-recreate'.format(api.instance.public_dns_name))


def deploy_worker(worker, registry_name, registry_cert='cert.crt'):
    region = worker.instance.placement['AvailabilityZone'][:-1]
    print('Building API worker')
    subprocess.call('tar --append --file=lanlytics-api-worker.tar {}'.format(registry_cert), shell=True)
    files = ['lanlytics-api-worker.tar']
    print('Copying files')
    worker.scp(' '.join(files), '~/')
    worker.ssh('tar -xf {}'.format(files[0]))
    worker.ssh('sudo mkdir -p /etc/docker/certs.d/{0} && \
                sudo cp ~/{1} /etc/docker/certs.d/{0}/ca.crt && \
                sudo cp ~/{1} /etc/pki/ca-trust/source/anchors/{0}.crt && \
                sudo update-ca-trust'.format(registry_name, registry_cert))
    worker.ssh('mv settings.py ~/lanlytics-api-worker/')
    print('Loading Docker image')
    worker.ssh('gunzip -c ~/lanlytics-api-worker/lanlytics-api-worker.tgz | docker load')
    print('Launching worker')
    worker.ssh('docker run -d \
        -e AWS_DEFAULT_REGION={0} \
        -v /home/{1}:/home/{1}. \
        -v /home/{1}/lanlytics-api-worker/settings.py:/src/settings.py \
        -v /var/run/docker.sock:/var/run/docker.sock \
        --restart always \
        hub.lanlytics.com/lanlytics-api-worker:latest docker'.format(region, worker.user))


def deploy_echo_test(worker, registry_name):
    print('Uploading test image')
    tag = '{}/echo-test:latest'.format(registry_name)
    worker.scp('echo-test.tgz', '~/')
    worker.ssh('gunzip -c ~/echo-test.tgz | docker load && \
                docker tag echo-test:latest {0} && \
                docker push {0} && \
                docker rmi {0} echo-test:latest'.format(tag))


def get_output(outputs, name):
    for output in outputs:
        if output['OutputKey'] == name:
            return output['OutputValue']


def vpc_parameters(args):
    parameters = ['IpBlock', 'SubnetIpBlock', 'BaseImageId', 'KeyName', 'SshIp']
    return {key: val for key, val in vars(args).items() if key in parameters}


def stack_parameters(args, outputs):
    parameters = ['KeyName', 'DynamoDBJobsTableName', 'S3WorkerBucketName', 'S3DockerImageBucketName']
    params = {key: val for key, val in vars(args).items() if key in parameters}
    params['VpcId'] = get_output(outputs, 'VpcId')
    params['SubnetId'] = get_output(outputs, 'SubnetId')
    return params


def buildout_api(args):
    vpc_template = 'vpc.template'
    api_template = 'lanlytics-api.template'

    print('Unpacking files')
    subprocess.call('tar xvzf lanlytics-api-dist.tgz', shell=True)

    #Deploy VPC stack
    params = vpc_parameters(args)
    vpc_outputs = create_stack(args.vpc_stack_name, vpc_template, **params)
    base_instance = Instance(get_output(vpc_outputs, 'InstanceId'))
    time.sleep(60)
    deploy_base_instance(base_instance)
    base_image_id = base_instance.create_ami('docker-base')

    # Deploy API stack
    params = stack_parameters(args, vpc_outputs)
    params['BaseImageId'] = base_image_id
    outputs = create_stack(args.api_stack_name, api_template, **params)
    api_server = Instance(get_output(outputs, 'ApiServerId'))
    registry = Instance(get_output(outputs, 'RegistryId'))
    worker = Instance(get_output(outputs, 'WorkerId'))
    redis_endpoint = get_output(outputs, 'RedisEndpoint')

    ssh_access_id = get_output(vpc_outputs, 'SSHAccessId')
    for instance in [api_server, registry, worker]:
        instance.add_security_group(ssh_access_id)

    time.sleep(60)
    registry_cert = deploy_registry(registry, args.S3DockerImageBucketName)
    create_api_settings(args.DynamoDBJobsTableName, redis_endpoint)
    deploy_api_server(api_server)
    create_worker_settings(registry.instance.private_dns_name, 
                           args.DynamoDBJobsTableName, 
                           redis_endpoint, 
                           api_server.instance.public_dns_name)
    deploy_worker(worker, registry.instance.private_dns_name, registry_cert)
    deploy_echo_test(worker, registry.instance.private_dns_name)
    worker.create_ami('lanlytics-api-worker')
    base_instance.instance.terminate()

    test_message = json.dumps({'service': 'echo-test', 'test': True})
    test_cmd = '''curl -k -H "Content-Type: application/json" -X POST -d \'{}\' https://{}'''.format(test_message, api_server.instance.public_dns_name)
    print('Give it a try:')
    print(test_cmd)


if __name__ == '__main__':
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('BaseImageId', help='Base AMI Id for instances')
    parser.add_argument('KeyName', help='Key pair name for launched instances')
    parser.add_argument('--vpc-ip-block', dest='IpBlock', default='10.0.0.0/16', help='Set of IP addresses for the VPC')
    parser.add_argument('--subnet-ip-block', dest='SubnetIpBlock', default='10.0.0.0/24', help='Set of IP addresses for the subnet')
    parser.add_argument('--ssh-ip', dest='SshIp', default='0.0.0.0/0', help='IP to restrict SSH access')
    parser.add_argument('--jobs-table', dest='DynamoDBJobsTableName', default='jobs', help='DynamoDB table name for job storage')
    parser.add_argument('--worker-bucket', dest='S3WorkerBucketName', default='lanlytics-api-worker', help='S3 bucket for API workers')
    parser.add_argument('--image-bucket', dest='S3DockerImageBucketName', default='lanlytics-registry-images', help='S3 bucket for Docker Registry')
    parser.add_argument('--vpc-stack-name', dest='vpc_stack_name', default='api-vpc', help='Name for VPC CloudFormation stack')
    parser.add_argument('--api-stack-name', dest='api_stack_name', default='lanlytics-api', help='Name for the API CloudFormation stack')
    args = parser.parse_args()
    buildout_api(args)
