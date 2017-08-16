import boto3
import botocore
import json
import sys
from settings import *
from uuid import uuid4

boto3.Session(region_name=AWS_REGION)

def submit_job(db, message):
    job_id = str(uuid4())
    message['job_id'] = job_id
    message['status'] = 'submitted'
    queue = message['queue'] if 'queue' in message.keys() else 'docker'
    queue_message = json.dumps(message)
    # Remove command key from message for status queries
    if 'command' in message:
        message.pop('command')
    db.set(job_id, json.dumps(message))
    # Push to queue
    db.lpush(queue, queue_message)
    return job_id


def query_job(db, job_id):
    response = db.get(job_id)
    if response is not None:
        return json.loads(response.decode())
    else:
        dyn = boto3.resource('dynamodb')
        table = dyn.Table(TABLE_NAME)
        response = table.get_item(Key={'job_id': job_id})
        return response['Item']


def all_jobs():
    dyn = boto3.resource('dynamodb')
    table = dyn.Table(TABLE_NAME)
    response = table.scan(Select='ALL_ATTRIBUTES')
    return response['Items']
