import boto3
import json
import sys
import time
from job_db import update_job

def receive_message(service):
    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName='service-experiment')
    message = None

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
                

def run_worker(worker_type, poll_frequency):
    while True:
        msg, msg_id = receive_message(worker_type)
        if msg:
            try:
                result = do_work(msg)
                update_job(msg_id, 'complete', result)
            except Exception as e:
                update_job(msg_id, 'failed', None)
        time.sleep(poll_frequency)


def do_work(params):
    params = json.loads(params)
    time.sleep(10)
    return 'work complete'

if __name__ == '__main__':
    worker_type, poll_frequency = tuple(sys.argv)
    run_worker(worker_type, poll_frequency)
    
