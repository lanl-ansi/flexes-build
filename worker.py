#!/usr/bin/env python3

import argparse
import boto3
import json
import sys
import os
import time
import traceback
import utils
from jsonschema import validate, ValidationError
#from local_launch import launch_container
#from local_launch import launch_native
from local_launch import Command

STATUS_COMPLETE = 'complete'
STATUS_FAILED = 'failed'
STATUS_RUNNING = 'running'

def process_message(db, cmd_type, cmd_prefix, message):
    print('Received message: {}'.format(message['id']))

    try:
        validate(json.loads(message['body']), utils.message_schema)
    except ValueError as e:
        print('Message string was not valid JSON')
        return handle_exception(db, message['id'], e)
    except ValidationError as e:
        print('Message JSON failed validation')
        return handle_exception(db, message['id'], e)

    utils.update_job(db, message['id'], STATUS_RUNNING)

    command = Command(cmd_type, message, cmd_prefix)
    try:
        status, result = command.execute()
        print('result: {}'.format(result))
    except Exception as e:
        return handle_exception(db, message['id'], e)

#    if docker_client != None: # this is a generic worker
#    #if docker_client != None and False: # hack for testing 
#        image = get_docker_image(docker_client, service_id)
#        if image is None:
#            #TODO try to pull from docker hub
#            # if that fails produce this error 
#            feedback = 'Unable to locate docker image: {}'.format(service_id)
#            print(feedback)
#            return handle_exception(db, msg_id, feedback)
#
#        print('Docker image for {} found\n'.format(service_id))
#        try:
#            result = launch_container(docker_client, image, msg_data)
#        except Exception as e:
#            print('docker launch failed')
#            return handle_exception(db, msg_id, e)
#
#    else: # non-generic native worker
#        try:
#            result = launch_native(cmd_prefix, msg_data)
#        except Exception as e:
#            print('native launch failed')
#            return handle_exception(db, msg_id, e)

    return utils.update_job(db, message['id'], STATUS_COMPLETE, result)


def handle_exception(db, msg_id, e):
    traceback.print_exc()
    return utils.update_job(db, msg_id, STATUS_FAILED, str(e))


def run_worker(args):
    print('Starting worker on process {}'.format(os.getpid()))

    sqs = boto3.resource('sqs')
    db = boto3.resource('dynamodb')

    try:
        args.cmd_prefix = json.loads(args.cmd_prefix)
    except ValueError as e:
        print('Command prefix was not valid JSON')
        return
    if not utils.is_str_list(args.cmd_prefix):
        print('Command prefix was not a list of strings')
        return
    print('Command prefix: {}'.format(args.cmd_prefix))
#    docker_client = None
#    if args.launch == 'docker':
#        docker_client = docker.Client(base_url='unix://var/run/docker.sock', version='auto')
#        print('docker client: {}'.format(docker_client))
#
#    if args.launch == 'native':
#        if args.worker_type == DOCKER_WORKER_TYPE:
#            print('native worker cannot have the worker type "{}"'.format(DOCKER_WORKER_TYPE))
#            return
#
#        try:
#            args.cmd_prefix = json.loads(args.cmd_prefix)
#        except ValueError as e:
#            print('command prefix string was not valid JSON')
#            return
#        if not is_str_list(args.cmd_prefix):
#            print('command prefix was not a list of strings')
#            return
#        print('native command prefix: {}'.format(args.cmd_prefix))
#
#    print('Polling for {} jobs every {} seconds'.format(args.worker_type, 
#                                                        args.poll_frequency))

    while True:
        message = utils.receive_message(sqs, args.worker_type)
        if message['body'] is not None:
            process_message(db, args.launch, args.cmd_prefix, message)
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
