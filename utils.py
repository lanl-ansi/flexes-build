import boto3
import docker
import json
import os
from jsonschema import validate, ValidationError

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'message_schema.json')) as file:
    msg_schema = json.load(file)
    s3_uri_schema = msg_schema['definitions']['s3_uri']

DOCKER_WORKER_TYPE = 'generic'

# AWS methods
def s3_get_uri(uri):
    return uri.split('/',2)[-1].split('/',1)


def get_s3_file(s3, uri, local_file):
    bucket_id, key = s3_get_uri(uri)
    s3.download_file(bucket_id, key, local_file)


def put_file_s3(s3, local_file, uri):
    bucket_id, key = s3_get_uri(uri)
    s3.upload_file(local_file, bucket_id, key)


def receive_message(sqs, service):
    queue = sqs.get_queue_by_name(QueueName='services')
    message = {'body': None, 'id': None, 'service': None}

    # Process message with optional Service attribute
    for msg in queue.receive_messages(MessageAttributeNames=['Service', 'ServiceType']):
        if msg.message_attributes is not None:
            service_type = msg.message_attributes.get('ServiceType').get('StringValue')
            service_name = msg.message_attributes.get('Service').get('StringValue')
            if service_type == service:
                message['service'] = service_name
                message['body'] = msg.body
                message['id'] = msg.message_id
                msg.delete()
                break
    return message


def update_job(db, job_id, status, result=None):
    table = db.Table('jobs')
    table.update_item(Key={'job_id': job_id},
                      UpdateExpression='SET #stat = :val1, #r = :val2',
                      ExpressionAttributeNames={'#stat': 'status', '#r': 'result'},
                      ExpressionAttributeValues={':val1': status, ':val2': result})
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

# IO
def make_local_dirs(local_file):
    directory = os.path.dirname(local_file)
    if not os.path.exists(directory):
        os.makedirs(directory)
