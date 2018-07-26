import boto3
import docker
import json
import os
import requests
import time
from botocore.exceptions import ClientError
from config import load_config
from jsonschema import validate, ValidationError
from pathlib import Path
from uuid import uuid4

config = load_config()

# Load API message schema for message validation
with Path(__file__).with_name('message_schema.json').open('r') as f:
    message_schema = json.load(f)
    s3_uri_schema = message_schema['definitions']['s3_uri']


def s3_get_uri(s3, uri):
    """Split S3 URI into a bucket object and key

    Args:
        s3 (boto3.resource): S3 connection
        uri (str): S3 URI

    Returns:
        tuple:
            boto3.resource.Bucket: S3 bucket object
            str: S3 object key
    """
    bucket_name, key = uri.split('/', 3)[2:]
    return (s3.Bucket(bucket_name), key)


def get_s3_file(s3, uri, local_file):
    """Download file(s) from S3
    
    Args:
        s3 (boto3.resource): S3 connection
        uri (str): S3 URI
        local_file (str): Local file destination for download

    Raises:
        ValueError: If S3 object does not exist
    """
    bucket, key = s3_get_uri(s3, uri)
    files = [obj.key for obj in bucket.objects.filter(Prefix=key)
                if not obj.key.endswith('/')]

    if len(files) == 0:
        raise ValueError('File {} not found'.format(uri))

    for obj in files:
        local_file = str(Path(local_file).with_name(Path(obj).name))
        bucket.download_file(obj, local_file)


def put_file_s3(s3, local_file, uri):
    """Upload file to S3

    Args:
        s3 (boto3.resource): S3 connection
        local_file (str): Path to local file
        uri (str): S3 URI for upload destination
    """
    bucket, key = s3_get_uri(s3, uri)
    local_dir = os.path.dirname(local_file)
    prefix = os.path.basename(local_file)
    for f in os.listdir(local_dir):
        if f == prefix:
            bucket.upload_file(local_file, key)
            break
        elif f.startswith(prefix):
            upload_file = os.path.join(local_dir, f)
            upload_key = os.path.join(os.path.dirname(key), f)
            bucket.upload_file(upload_file, upload_key)


def get_instance_info():
    """Get information about worker host machine
    
    Returns:
        tuple:
            str: Worker unique ID
            str: Type of instance worker is running on
            str: Private IP of the instance worker is running on
    """
    try:
        metadata_url = 'http://169.254.169.254/latest/dynamic/instance-identity/document'
        response = requests.get(metadata_url, timeout=5)
        resp_json = response.json()
        instance_id = resp_json['instanceId']
        instance_type = resp_json['instanceType']
        private_ip = resp_json['privateIp']
    except requests.exceptions.ConnectionError:
        instance_id = str(uuid4())
        instance_type = 'local_machine'
        private_ip = None
    return instance_id, instance_type, private_ip


# Validation
def is_str_list(x):
    """Determine if object is a list of strings"""
    return (isinstance(x, list) and all(isinstance(s, str) for s in x))


def is_valid_message(message):
    """Determine if message conforms to the specified message schema

    Args:
        message (dict): Message to evaluate
    
    Returns:
        bool
    """
    return isvalid(message, message_schema)


def is_s3_uri(uri):
    """Determine if a string is a valid S3 URI"""
    return isvalid(uri, s3_uri_schema)


def isvalid(obj, schema):
    """Determine if object conforms to a specified schema
    
    Args:
        obj (dict): Object to evaluate against schema
        schema (dict): Schema to compare with `obj`

    Returns:
        bool
    """
    try:
        validate(obj, schema)
        return True
    except ValidationError:
        return False
