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

def process_message(db, docker_client, cmd_prefix, msg_id, msg_body, service_id):
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
    #if docker_client != None and False: # hack for testing 
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
            result = launch_native(cmd_prefix, msg_data)
        except Exception as e:
            print('native launch failed')
            return handle_exception(db, msg_id, e)

    return update_job(db, msg_id, STATUS_COMPLETE, result)


def run_worker(args):
    print('Starting worker on process {}'.format(os.getpid()))

    sqs = boto3.resource('sqs')
    db = boto3.resource('dynamodb')

    docker_client = None
    if args.launch == 'docker':
        docker_client = docker.Client(base_url='unix://var/run/docker.sock', version='auto')
        print('docker client: {}'.format(docker_client))

    if args.launch == 'native':
        if args.worker_type == DOCKER_WORKER_TYPE:
            print('native worker cannot have the worker type "{}"'.format(DOCKER_WORKER_TYPE))
            return

        try:
            args.cmd_prefix = json.loads(args.cmd_prefix)
        except ValueError as e:
            print('command prefix string was not valid JSON')
            return
        if not is_str_list(args.cmd_prefix):
            print('command prefix was not a list of strings')
            return
        print('native command prefix: {}'.format(args.cmd_prefix))

    print('Polling for {} jobs every {} seconds'.format(args.worker_type, 
                                                        args.poll_frequency))

    while True:
        message = receive_message(sqs, args.worker_type)
        if message['body'] is not None:
            command = Command(args.launch, message, args.cmd_prefix)
            command.execute()
            process_message(db, docker_client, args.cmd_prefix, message['id'], message['body'], message['service'])
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
    #parser_docker.add_argument('worker_type', action='store_const', const=DOCKER_WORKER_TYPE)
    parser_docker.set_defaults(worker_type=DOCKER_WORKER_TYPE)
    #parser_docker.add_argument('-t', '--worker_type', default=DOCKER_WORKER_TYPE,
    #                    help='override docker\'s default worker type')

    parser_native = subparsers.add_parser('native', help='runs commands natively')
    parser_native.set_defaults(launch='native')
    parser_native.add_argument('worker_type',
                        help='type of worker required for the service')
    parser_native.add_argument('cmd_prefix',
                        help='the command prefix of a native worker as a list of \
                              strings in json format, takes the place of the \
                              "ENTRYPOINT" in a docker container')
    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    args = parser.parse_args()
    run_worker(args)
