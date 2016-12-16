#!/usr/bin/env python3

import boto3
import json
import sys
import os
import time
import argparse
import traceback
from jsonschema import validate, ValidationError
from local_launch import launch_container
from local_launch import launch_native
import docker

worker_dir_path = os.path.dirname(os.path.abspath(__file__))
with open(worker_dir_path+os.sep+'message_schema.json') as file:
    msg_schema = json.load(file)

DEFAULT_WORKER_TYPE = 'generic'

STATUS_FAILED = 'failed'
STATUS_RUNNING = 'running'
STATUS_COMPLETE = 'complete'


def is_str_list(x):
    if type(x) is list:
        for s in x:
            if not type(s) is str:
                return False
    else:
        return False
    return True

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


def process_message(db, docker_client, msg_id, msg_body, service_id):
    print('Received message: {}'.format(str(msg_id)))

    try:
        msg_data = json.loads(msg_body)
        validate(msg_data, msg_schema)
    except ValueError as e:
        print('Message string was not valid JSON')
        return handle_exception(db, msg_id, e)
    except ValidationError as e:
        print('Message JSON failed validation')
        return handle_exception(db, msg_id, e)

    update_job(db, msg_id, STATUS_RUNNING)

    if docker_client != None: # this is a generic worker
    #if docker_client != None and service_id != 'powerworld_test': # hack for testing 
        image = get_docker_image(docker_client, service_id)
        if image is None:
            #TODO try to pull from docker hub
            # if that fails produce this error 
            feedback = 'Unable to locate docker image: {}'.format(service_id)
            print(feedback)
            return handle_exception(db, msg_id, feedback)

        print('Docker image for {} found\n'.format(service_id))
        try:
            result = launch_container(docker_client, image, msg_data)
        except Exception as e:
            print('docker launch failed')
            return handle_exception(db, msg_id, e)

    else: # non-generic native worker
        try:
            result = launch_native(msg_data)
        except Exception as e:
            print('native launch failed')
            return handle_exception(db, msg_id, e)

    return update_job(db, msg_id, STATUS_COMPLETE, result)

def run_worker(args):
    sqs = boto3.resource('sqs')
    db = boto3.resource('dynamodb')

    print(args)

    docker_client = None
    if args.launch == 'docker':
        docker_client = docker.Client(base_url='unix://var/run/docker.sock', version='auto')

    if args.launch == 'native':
        try:
            args.cmd_prefix = json.loads(args.cmd_prefix)
        except ValueError as e:
            print('command prefix string was not valid JSON')
            return
        if not is_str_list(args.cmd_prefix):
            print('command prefix was not a list of strings')
            return

    print(args)

    print('Starting worker on process %d' % os.getpid())
    print('Polling for {} jobs every {} seconds'.format(args.worker_type, 
                                                        args.poll_frequency))

    while True:
        message = receive_message(sqs, args.worker_type)
        if message['body'] is not None:
            process_message(db, docker_client, message['id'], message['body'], message['service'])
        else:
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(args.poll_frequency)


def build_cli_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-pf', '--poll_frequency', default=60, type=int, 
                        help='time to wait between polling the work queue (seconds)')

    subparsers = parser.add_subparsers()

    parser_docker = subparsers.add_parser('docker', help='runs commands in docker containers')
    parser_docker.set_defaults(launch='docker')
    #parser_docker.add_argument('worker_type', action='store_const', const=DEFAULT_WORKER_TYPE)
    parser_docker.set_defaults(worker_type=DEFAULT_WORKER_TYPE)
    #parser_docker.add_argument('-t', '--worker_type', default=DEFAULT_WORKER_TYPE,
    #                    help='override docker\'s default worker type')

    parser_native = subparsers.add_parser('native', help='runs commands nativly')
    parser_native.set_defaults(launch='native')
    parser_native.add_argument('worker_type',
                        help='type of worker required for the service')
    parser_native.add_argument('cmd_prefix',
                        help='the command prefix of a native worker as a list of strings in json format')
    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    args = parser.parse_args()
    run_worker(args)
