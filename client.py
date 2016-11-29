from __future__ import print_function
import boto3
import botocore
import json
import sys

def send_message(message, service):
    try:
        sqs = boto3.resource('sqs')
        queue = sqs.get_queue_by_name(QueueName='service-experiment')
        resp = queue.send_message(MessageBody=json.dumps(message),
                                  MessageAttributes={'Service': {'StringValue': service, 
                                                                 'DataType': 'String'}})
        return resp.get('MessageId')
    except botocore.exceptions.NoRegionError:
        print('No region specified, has an .aws/config file been created?', file=sys.stderr)
        return


def add_job(job_id, service):
    try:
        db = boto3.resource('dynamodb')
        table = db.Table('service-experiment')
        table.put_item(Item={
            'job_id': job_id,
            'service': service,
            'result': None,
            'status': 'submitted'
        })
    except botocore.exceptions.NoRegionError:
        print('No region specified, has an .aws/config file been created?', file=sys.stderr)
        return


def submit_job(message, service):
    job_id = send_message(message, service)
    add_job(job_id, service)
    return job_id


def query_job(job_id):
    try:
        db = boto3.resource('dynamodb')
        table = db.Table('service-experiment')
        response = table.get_item(Key={'job_id': job_id})
        return response['Item']
    except botocore.exceptions.NoRegionError:
        print('No region specified, has an .aws/config file been created?', file=sys.stderr)
        return
