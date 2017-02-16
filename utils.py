import boto3
import docker
import json
import os
from jsonschema import validate, ValidationError
from settings import *

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'message_schema.json')) as file:
    message_schema = json.load(file)
    s3_uri_schema = message_schema['definitions']['s3_uri']

# AWS methods
def s3_get_uri(s3, uri):
    bucket_name, key = uri.split('/', 3)[2:]
    return (s3.Bucket(bucket_name), key)


def get_s3_file(s3, uri, local_file):
    bucket, key = s3_get_uri(s3, uri)
    for obj in bucket.objects.filter(Prefix=key):
        local_file = os.path.join(os.path.dirname(local_file), 
                                  os.path.basename(obj.key))
        if not obj.key.endswith('/'):
            bucket.download_file(obj.key, local_file)


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


def receive_message(sqs, service):
    queue = sqs.get_queue_by_name(QueueName='services')

    for msg in queue.receive_messages(MessageAttributeNames=['Service', 'ServiceType']):
        if msg.message_attributes is not None:
            service_type = msg.message_attributes.get('ServiceType').get('StringValue')
            service_name = msg.message_attributes.get('Service').get('StringValue')
            if service_type == service:
                message = {'service': service_name, 
                           'body': msg.body, 
                           'id': msg.message_id}
                msg.delete()
                return message
    else:
        return


def update_job(db, job_id, status, result=None):
    val = json.loads(db.get(job_id).decode())
    val.update({'status': status, 'result': result})
    db.set(job_id, json.dumps(val))
    if status == STATUS_COMPLETE:
        db.expire(job_id, 60)
        dyn = boto3.resource('dynamodb')
        table = dyn.Table('jobs')
        table.update_item(Key={'job_id': job_id},
                          UpdateExpression='SET #stat = :val1, #r = :val2',
                          ExpressionAttributeNames={'#stat': 'status', '#r': 'result'},
                          ExpressionAttributeValues={':val1': status, ':val2': result})
    elif status == STATUS_ACTIVE:
        db.expire(job_id, 30)
    return status, result


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


def image_exists(image_name):
    client = docker.DockerClient(base_url='unix://var/run/docker.sock', version='auto')
    image = 'hub.lanlytics.com/{}:latest'.format(image_name)
    try:
        image = client.images.get(image)
        return True
    except docker.errors.ImageNotFound:
        try:
            client.images.pull(image)
            return True
        except docker.errors.ImageNotFound:
            return False
