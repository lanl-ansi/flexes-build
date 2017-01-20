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

DOCKER_WORKER_TYPE = 'generic'

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

    utils.update_job(db, message['id'], 'running')

    command = Command(cmd_type, message, cmd_prefix)
    try:
        status, result = command.execute()
        print('Result: {}'.format(result))
    except Exception as e:
        return handle_exception(db, message['id'], e)

    return utils.update_job(db, message['id'], status, result)


def handle_exception(db, msg_id, e):
    traceback.print_exc()
    return utils.update_job(db, msg_id, 'failed', str(e))


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
    parser_docker.set_defaults(cmd_prefix='[]')
    parser_docker.set_defaults(worker_type=DOCKER_WORKER_TYPE)

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
