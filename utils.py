import boto3
import docker
import json
import os
import random
import time
from botocore.exceptions import ClientError
from config import load_config
from jsonschema import validate, ValidationError
from pathlib import Path

config = load_config()

with Path(__file__).with_name('message_schema.json').open('r') as f:
    message_schema = json.load(f)
    s3_uri_schema = message_schema['definitions']['s3_uri']


def s3_get_uri(s3, uri):
    bucket_name, key = uri.split('/', 3)[2:]
    return (s3.Bucket(bucket_name), key)


def get_s3_file(s3, uri, local_file):
    bucket, key = s3_get_uri(s3, uri)
    files = [obj.key for obj in bucket.objects.filter(Prefix=key)
                if not obj.key.endswith('/')]

    if len(files) == 0:
        raise ValueError('File {} not found'.format(uri))

    for obj in files:
        local_file = str(Path(local_file).with_name(Path(obj).name))
        bucket.download_file(obj, local_file)


def put_file_s3(s3, local_file, uri):
    bucket, key = s3_get_uri(s3, uri)
    local_dir = os.path.dirname(local_file)
    prefix = os.path.basename(local_file)
    for f in os.listdir(local_dir):
        filename, ext = os.path.splitext(f)
        if f == prefix:
            bucket.upload_file(local_file, key)
            break
        elif filename == prefix:
            bucket.upload_file(local_file + ext, key + ext)


def get_instance_info():
    try:
        metadata_url = 'http://169.254.169.254/latest/dynamic/instance-identity/document'
        response = requests.get(metadata_url, timeout=1)
        resp_json = response.json()
        instance_id = resp_json['instanceId']
        instance_type = resp_json['instanceType']
        private_ip = resp_json['privateIp']
    except requests.exceptions.ConnectionError:
        instance_id = str(uuid4())
        instance_type = 'local_machine'
        private_ip = None
    return instance_id, instance_type, private_ip


# Database
def receive_message(db, queue):
    message = db.rpop(queue)
    if message is not None:
        message = json.loads(message)
        update_job(db, message['job_id'], config['STATUS_RUNNING'])
    return message


def update_job(db, job_id, status, result=None, stdout_data=None, stderr_data=None):
    job = 'job:{}'.format(job_id)
    queue = db.hget(job, 'queue')
    db.hmset(job, 
            {'status': status, 
             'result': result, 
             'stdout': stdout_data, 
             'stderr': stderr_data})
    if status == config['STATUS_RUNNING']:
        db.sadd('{}:jobs:running'.format(queue), job_id)
    elif status in [config['STATUS_COMPLETE'], config['STATUS_FAIL']]:
        db.expire(job, 60)
        db.srem('{}:jobs'.format(queue), job_id)
        db.srem('{}:jobs:running'.format(queue), job_id)
        dyn = boto3.resource('dynamodb', endpoint_url=config['DYNAMODB_ENDPOINT'])
        table = dyn.Table(config['JOBS_TABLE'])
        table.update_item(Key={'job_id': job_id},
                          UpdateExpression='SET #stat = :val1, #r = :val2',
                          ExpressionAttributeNames={'#stat': 'status', '#r': 'result'},
                          ExpressionAttributeValues={':val1': status, ':val2': result})
    elif status == config['STATUS_ACTIVE']:
        db.expire(job, 30)
        db.srem('{}:jobs'.format(queue), job_id)
        db.srem('{}:jobs:running'.format(queue), job_id)
    return status, result


def update_job_messages(db, job_id, messages):
    job = 'job:{}'.format(job_id)
    db.hmset(job, {'messages': messages})


# Validation
def is_str_list(x):
    return (isinstance(x, list) and all(isinstance(s, str) for s in x))


def is_valid_message(message):
    return isvalid(message, message_schema)


def is_s3_uri(uri):
    return isvalid(uri, s3_uri_schema)


def isvalid(obj, schema):
    try:
        validate(obj, schema)
        return True
    except ValidationError:
        return False


def image_exists(image_name, tag='latest'):
    client = docker.DockerClient(base_url='unix://var/run/docker.sock', version='auto')
    image = '{}/{}:{}'.format(config['DOCKER_REGISTRY'], image_name, tag)
    try:
        image = client.images.get(image)
        return True
    except docker.errors.ImageNotFound:
        try:
            print('Image {} not found locally'.format(image))
            client.images.pull(image)
            return True
        except docker.errors.ImageNotFound:
            return False
