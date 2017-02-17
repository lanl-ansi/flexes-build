import boto3
import botocore
import json
import sys
from uuid import uuid4

def send_message(sqs, message, attributes):
    try:
        queue = sqs.get_queue_by_name(QueueName='services')
        message_attributes = {attr: {'StringValue': val, 'DataType': 'String'}
                              for attr, val in attributes.items()}
        resp = queue.send_message(MessageBody=json.dumps(message),
                                  MessageAttributes=message_attributes)
        return resp.get('MessageId')


def submit_job(db, message, attributes):
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


def query_job(db, dyn, job_id):
    response = db.get(job_id)
    if response is not None:
        return json.loads(response.decode())
    else:
        table = dyn.Table('jobs')
        response = table.get_item(Key={'job_id': job_id})
        return response['Item']


def all_jobs(dyn):
    table = dyn.Table('jobs')
    response = table.scan(Select='ALL_ATTRIBUTES')
    return response['Items']
