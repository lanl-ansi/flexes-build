import boto3
import json

def send_message(message, service):
    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName='service-experiment')
    resp = queue.send_message(MessageBody=json.dumps(message),
                              MessageAttributes={'Service': {'StringValue': service, 
                                                             'DataType': 'String'}})
    return resp.get('MessageId')


def add_job(job_id, service):
    db = boto3.resource('dynamodb')
    table = db.Table('service-experiment')
    table.put_item(Item={
        'job_id': job_id,
        'service': service,
        'result': None,
        'status': 'submitted'
    })


def submit_job(message, service):
    job_id = send_message(message, service)
    add_job(job_id, service)
    return job_id


def query_job(job_id):
    db = boto3.resource('dynamodb')
    table = db.Table('service-experiment')
    response = table.get_item(Key={'job_id': job_id})
    return response['Item']
