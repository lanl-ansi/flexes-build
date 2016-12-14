#!/usr/bin/env python3

import boto3
import json
import sys
import time
import argparse
import traceback
from jsonschema import validate, ValidationError
from docker_launch import launch_container
import docker

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
    message = {'body': None, 'id': None, 'service': None}


    # Process message with optional Service attribute
    for msg in queue.receive_messages(MessageAttributeNames=['Service', 'ServiceType']):
        if msg.message_attributes is not None:
            service_type = msg.message_attributes.get('ServiceType').get('StringValue')
            service_name = msg.message_attributes.get('Service').get('StringValue')
            if service_type == service:
                message['service'] = service_name
                message['body'] = msg.body
                message['id'] = msg.message_id
                msg.delete()
                break
    return message


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


def get_docker_image(docker_client, image_name):
    for image in docker_client.images():
        for tag in image['RepoTags']:
            if image_name+':latest' in tag:
                return image
    return None


def process_message(docker_client, image, db, msg_id, msg, worker_id):
    print('Received message: {}'.format(str(msg_id)))

    try:
        msg_data = json.loads(msg)
        validate(msg_data, msg_schema)
    except ValueError as e:
        print('Message string was not valid JSON')
        return handle_exception(db, msg_id, e)
    except ValidationError as e:
        print('Message JSON failed validation')
        return handle_exception(db, msg_id, e)

    update_job(db, msg_id, STATUS_RUNNING)

    try:
        result = launch_container(docker_client, image, msg_data)
        return update_job(db, msg_id, STATUS_COMPLETE, result)
    except Exception as e:
        print('Docker launch failed')
        return handle_exception(db, msg_id, e)


def run_worker(args):
    sqs = boto3.resource('sqs')
    db = boto3.resource('dynamodb')

    docker_client = None

    if not args.local:
        docker_client = docker.Client(base_url='unix://var/run/docker.sock', version='auto')
    print('Polling for {} jobs every {} seconds'.format(args.worker_type, 
                                                        args.poll_frequency))

    while True:
        message = receive_message(sqs, args.worker_type)
        if message['body'] is not None:
            image = get_docker_image(docker_client, message['service'])
            if image is not None:
                print('Docker image for {} found\n'.format(message['service']))
                process_message(docker_client, image, db, 
                                message['id'], message['body'], 
                                message['service'])
            else:
                #TODO try to pull from docker hub
                # if that fails produce this error 
                print('Unable to locate docker image: {}'.format(message['service']))
        else:
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(args.poll_frequency)


def build_cli_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-pf', '--poll_frequency', default=60, type=int, 
                        help='time to wait between polling the work queue (seconds)')
    parser.add_argument('-l', '--local', action='store_true', 
                        help='run the command on the local system instead of a docker container')
    parser.add_argument('-t', '--worker_type', default='generic', 
                        help='type of worker required for the service')
    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    args = parser.parse_args()
    run_worker(args)
