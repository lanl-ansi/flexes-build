import boto3
import json
import sys
import time
from docker_launch import launch_worker


def receive_message(service):
    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName='service-experiment')
    message = None
    msg_id = None

    # Process message with optional Service attribute
    for msg in queue.receive_messages(MessageAttributeNames=['Service']):
        if msg.message_attributes is not None:
            service_name = msg.message_attributes.get('Service').get('StringValue')
            if service_name == service:
                message = msg.body
                msg_id = msg.message_id
                msg.delete()
                break
    return message, msg_id


def update_job(job_id, status, result):
    db = boto3.resource('dynamodb')
    table = db.Table('service-experiment')
    table.update_item(Key={'job_id': job_id},
                      UpdateExpression='SET #stat = :val1, #r = :val2',
                      ExpressionAttributeNames={'#stat': 'status', '#r': 'result'},
                      ExpressionAttributeValues={':val1': status, ':val2': result})
                

def run_worker(worker_type, poll_frequency):
    while True:
        msg, msg_id = receive_message(worker_type)
        if msg is not None:
            print('received message')
            try:
                result = launch_worker(msg)
                update_job(msg_id, 'complete', result)
            except Exception as e:
                update_job(msg_id, 'failed', None)
        time.sleep(poll_frequency)


def do_work(params):
    params = json.loads(params)
    print(params)
    time.sleep(5)
    return 'work complete'

if __name__ == '__main__':
    worker_type = sys.argv[1]
    poll_frequency = int(sys.argv[2])
    run_worker(worker_type, poll_frequency)
