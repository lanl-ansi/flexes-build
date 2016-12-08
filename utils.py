from __future__ import print_function
import boto3
import botocore
import json
import sys

def send_message(message, attributes):
    try:
        sqs = boto3.resource('sqs')
        queue = sqs.get_queue_by_name(QueueName='services')
        message_attributes = {attr: {'StringValue': val, 'DataType': 'String'}
                              for attr, val in attributes.items()}
        resp = queue.send_message(MessageBody=json.dumps(message),
                                  MessageAttributes=message_attributes)
        return resp.get('MessageId')
    except botocore.exceptions.NoRegionError:
        print('No region specified, has an .aws/config file been created?', file=sys.stderr)
        return


def add_job(job_id, service):
    try:
        db = boto3.resource('dynamodb')
        table = db.Table('jobs')
        table.put_item(Item={
            'job_id': job_id,
            'service': service,
            'result': None,
            'status': 'submitted'
        })
    except botocore.exceptions.NoRegionError:
        print('No region specified, has an .aws/config file been created?', file=sys.stderr)
        return


def submit_job(message, attributes):
    job_id = send_message(message, attributes)
    add_job(job_id, service)
    return job_id


def query_job(job_id):
    try:
        db = boto3.resource('dynamodb')
        table = db.Table('jobs')
        response = table.get_item(Key={'job_id': job_id})
        return response['Item']
    except botocore.exceptions.NoRegionError:
        print('No region specified, has an .aws/config file been created?', file=sys.stderr)
        return


def all_jobs():
    try:
        db = boto3.resource('dynamodb')
        table = db.Table('jobs')
        response = table.scan(Select='ALL_ATTRIBUTES')
        return response['Items']
    except botocore.exceptions.NoRegionError:
        print('No region specified, has an .aws/config file been created?', file=sys.stderr)
        return
