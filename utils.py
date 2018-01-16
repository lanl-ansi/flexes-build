import boto3
import botocore
import json
import sys
from settings import *
from uuid import uuid4

def submit_job(db, message):
    job_id = str(uuid4())
    message['job_id'] = job_id
    message['status'] = 'submitted'
    queue = message['queue'] if 'queue' in message.keys() else 'docker'

    job = 'job:{}'.format(job_id)
    # Create job db entry
    db.hmset(job, message)
    # Push to queue
    db.lpush(queue, json.dumps(message))
    db.sadd('{}:jobs'.format(queue), job_id)
    return job_id


def query_job_status(db, job_id):
    job = 'job:{}'.format(job_id)
    status = db.hget(job, 'job_id')
    if status is not None:
        return {'job_id': job_id, 'status': status.decode()}
    else:
        return get_job_result(db, job_id)


def get_job_result(db, job_id):
    job = 'job:{}'.format(job_id)
    result = db.hgetall(job)
    if result is not None:
        return result
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
