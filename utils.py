import boto3
import docker
import json
import os
from jsonschema import validate, ValidationError

HOME = os.path.abspath(os.sep)
if os.name == 'nt':
    if 'HOMEPATH' in os.environ:
        HOME = os.environ['HOMEPATH']
else:
    if 'HOME' in os.environ:
        HOME = os.environ['HOME']

LOCAL_FILES_DIR = os.path.join('lanlytics_worker_local', str(os.getpid()))
LOCAL_FILES_PATH = os.path.join(HOME, LOCAL_FILES_DIR)

worker_dir_path = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(worker_dir_path, 'message_schema.json')) as file:
    msg_schema = json.load(file)
    s3_uri_schema = msg_schema['definitions']['s3_uri']

DOCKER_WORKER_TYPE = 'generic'

STATUS_FAILED = 'failed'
STATUS_RUNNING = 'running'
STATUS_COMPLETE = 'complete'

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


def isvalid(obj, schema):
    try:
        validate(obj, schema)
        return True
    except ValidationError:
        return False

# IO
def get_local_path(uri):
    if is_s3_uri(uri):
        local_file_name = uri.replace('s3:/', LOCAL_FILES_PATH)
        return local_file_name
    return uri


def get_docker_path(uri):
    path = get_local_path(uri)
    if path.startswith(LOCAL_FILES_PATH):
        return path.replace(LOCAL_FILES_PATH, os.sep+LOCAL_FILES_DIR)
    return path


def make_local_dirs(local_file):
    directory = os.path.dirname(local_file)
    if not os.path.exists(directory):
        os.makedirs(directory)

# Misc
def handle_exception(db, msg_id, e):
    traceback.print_exc()
    return update_job(db, msg_id, STATUS_FAILED, str(e))


def get_docker_image(docker_client, image_name):
    for image in docker_client.images():
        for tag in image['RepoTags']:
            if image_name+':latest' in tag:
                return image
    return None
