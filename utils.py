import boto3
import botocore
import json
import sys
from uuid import uuid4

def submit_job(db, command, attributes):
    job_id = str(uuid4())
    queue = attributes['ServiceType']
    job = {'job_id': job_id,
           'service': attributes['Service'],
           'command': command,
           'status': 'submitted'}
    job = json.dumps(job)
    db.lpush(queue, job)
    db.set(job_id, job)
    return job_id


def query_job(db, job_id):
    response = db.get(job_id)
    if response is not None:
        return json.loads(response.decode())
    else:
        dyn = boto3.resource('dynamodb')
        table = dyn.Table('jobs')
        response = table.get_item(Key={'job_id': job_id})
        return response['Item']


def all_jobs():
    dyn = boto3.resource('dynamodb')
    table = dyn.Table('jobs')
    response = table.scan(Select='ALL_ATTRIBUTES')
    return response['Items']
