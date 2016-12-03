#!/usr/bin/env python3

import boto3
import json
import sys
import time
import argparse
import traceback
from jsonschema import validate, ValidationError
from docker_launch import launch_container
from docker import Client

with open('message_schema.json') as file:
    msg_schema = json.load(file)

STATUS_FAILED = 'failed'
STATUS_RUNNING = 'running'
STATUS_COMPLETE = 'complete'

def isvalid(obj, schema):
    try:
        validate(obj, schema)
        return True
    except ValidationError:
        return False


def receive_message(sqs, service):
    queue = sqs.get_queue_by_name(QueueName='services')
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


def update_job(db, job_id, status, result=None):
    table = db.Table('jobs')
    table.update_item(Key={'job_id': job_id},
                      UpdateExpression='SET #stat = :val1, #r = :val2',
                      ExpressionAttributeNames={'#stat': 'status', '#r': 'result'},
                      ExpressionAttributeValues={':val1': status, ':val2': result})
    return status, result


def handle_exception(db, msg_id, e):
    traceback.print_exc()
    return update_job(db, msg_id, STATUS_FAILED, str(e))


def get_docker_image(docker, image_name):
    for image in docker.images():
        for tag in image['RepoTags']:
            if image_name+':latest' in tag:
                return image
    return None


def process_message(docker, image, db, msg_id, msg, worker_id):
    print('received message: %s' % str(msg_id))

    try:
        msg_data = json.loads(msg)
        validate(msg_data, msg_schema)
    except ValueError as e:
        print('message string was not valid JSON')
        return handle_exception(db, msg_id, e)
    except ValidationError as e:
        print('message JSON failed validation')
        return handle_exception(db, msg_id, e)

    update_job(db, msg_id, STATUS_RUNNING)

    try:
        result = launch_container(docker, image, msg_data)
        return update_job(db, msg_id, STATUS_COMPLETE, result)
    except Exception as e:
        print('docker launch failed')
        return handle_exception(db, msg_id, e)


def run_worker(args):
    sqs = boto3.resource('sqs')
    db = boto3.resource('dynamodb')

    docker = None
    image = None

    if not args.local:
        docker = Client(base_url='unix://var/run/docker.sock', version='auto')
        image = get_docker_image(docker, args.worker_type)
        if image == None:
            #TODO try to pull from docker hub
            # if that fails produce this error 
            print('unable to locate docker image: %s' % args.worker_type)
            return

    print('docker image for %s found\n' % args.worker_type)

    print('Polling for {} jobs every {} seconds'.format(args.worker_type, args.poll_frequency))
    while True:
        msg, msg_id = receive_message(sqs, args.worker_type)
        if msg is not None:
            process_message(docker, image, db, msg_id, msg, args.worker_type)
        else:
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(args.poll_frequency)


def build_cli_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('worker_type', help='worker id string')
    parser.add_argument('poll_frequency', help='time to wait between polling the work queue (seconds)', type=int)
    parser.add_argument('-l', '--local', help='run the command on the local system instead of a docker container', action='store_true')
    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    args = parser.parse_args()
    run_worker(args)
