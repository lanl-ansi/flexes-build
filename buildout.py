import boto3
import time

class Instance:
    def __init__(self, ip, pem_file, user='ec2-user'):
        self.address = '{}@{}'.format(user, ip)
        self.pem_file = pem_file

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


def deploy_registry(registry_instance):
    # Copy build file to instance
    # Run build file
    # Launch docker-compose application


def deploy_api_server(api_instance):
    api_server = Instance(api_server_id)
    # 


def deploy_worker(worker_instance)


def create_worker_ami():


def buildout_api():
    outputs = create_stack()
    api_server = Instance(outputs[0]['OutputValue'])
    registry = Instance(outputs[1]['OutputValue'])
    worker = Instance(outputs[2]['OutputValue'])
    redis_endpoint = outputs[3]['OutputValue']

    deploy_registry(regsitry)
    deploy_api_server(api_server)
    deploy_worker(worker)

    print('All done; go home')
