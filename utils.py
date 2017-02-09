from __future__ import print_function
import boto3
import botocore
import json
import sys

def send_message(sqs, message, attributes):
    try:
        queue = sqs.get_queue_by_name(QueueName='services')
        message_attributes = {attr: {'StringValue': val, 'DataType': 'String'}
                              for attr, val in attributes.items()}
        resp = queue.send_message(MessageBody=json.dumps(message),
                                  MessageAttributes=message_attributes)
        return resp.get('MessageId')
    except botocore.exceptions.NoRegionError:
        print('No region specified, has an .aws/config file been created?', file=sys.stderr)
        return


def add_job(db, dyn, job_id, command, service):
    job = {'job_id': job_id,
           'service': service,
           'command': json.dumps(command),
           'result': None,
           'status': 'submitted'}
    db.set(job_id, json.dumps(job))
    table = dyn.Table('jobs')
    table.put_item(Item=job)


def submit_job(db, dyn, sqs, message, attributes):
    job_id = send_message(sqs, message, attributes)
    add_job(db, dyn, job_id, message, attributes['Service'])
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
