import boto3
import time

class Instance:
    def __init__(self, instance_id, user='ec2-user'):
        ec2 = boto3.resource('ec2')
        instance = ec2.Instance(instance_id)
        public_ip = instance.public_ip_address
        self.address = '{}@{}'.format(user, public_ip)
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


def create_stack(**kwargs):
    cloudformation = boto3.resource('cloudformation')

    with open('lanlytics-api.template', 'r') as f:
        template_body = f.read()

    stack = cloudformation.create_stack(
        StackName=stack_name,
        TemplateBody=template_body,
        Parameters=[
            {'ParameterKey': 'VpcId', 'ParameterValue': vpc_id, 'UsePreviousValue': False},    
            {'ParameterKey': 'SubnetGroupId', 'ParameterValue': subnet_id, 'UsePreviousValue': False},    
            {'ParameterKey': 'BaseImageId', 'ParameterValue': base_image_id, 'UsePreviousValue': False},    
            {'ParameterKey': 'KeyName', 'ParameterValue': key_name, 'UsePreviousValue': False},    
            {'ParameterKey': 'SSHIP', 'ParameterValue': ssh_ip, 'UsePreviousValue': False},    
            {'ParameterKey': 'DynamoDBJobsTableName', 'ParameterValue': jobs_table, 'UsePreviousValue': False},    
            {'ParameterKey': 'S3WorkerBucketName', 'ParameterValue': worker_bucket, 'UsePreviousValue': False},    
            {'ParameterKey': 'S3DockerImageBucketName', 'ParameterValue': registry_bucket, 'UsePreviousValue': False},    
        ],
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
            lanlytics-api-worker docker')


def create_worker_ami():


def buildout_api():
    outputs = create_stack()
    api_server = Instance(outputs[0]['OutputValue'])
    registry = Instance(outputs[1]['OutputValue'])
    worker = Instance(outputs[2]['OutputValue'])
    redis_endpoint = outputs[3]['OutputValue']

    deploy_registry(Instance(regsitry))
    deploy_api_server(Instance(api_server))
    deploy_worker(Instance(worker))

    print('All done; go home')
