#!/usr/bin/env python3

import argparse
import json
import os
import redis
import sys
import time
import traceback
import utils
from itertools import cycle
from jsonschema import validate, ValidationError
from launch import Command
from settings import *
from uuid import uuid4


def process_message(db, cmd_type, cmd_prefix, message):
    print('Received message: {}'.format(message['job_id']))

    try:
        validate(message, utils.message_schema)

        if 'tag' not in message:
            message['tag'] = 'latest'

        if 'test' in message and message['test']:
            utils.update_job(db, message['job_id'], STATUS_RUNNING, None)
            if cmd_type == 'docker':
                if utils.image_exists(message['service'], message['tag']):
                    print('Confirmed active status for {} worker of type {}'.format(cmd_type, message['service']))
                    return utils.update_job(db, message['job_id'], STATUS_ACTIVE, 'Service is active')
                else:
                    print('Image not found for {} worker of type {}'.format(cmd_type, message['service']))
                    return utils.update_job(db, message['job_id'], STATUS_FAIL, 
                                            'Image for {} not found'.format(message['service']))
            else:
                print('Confirmed active status for {} worker of type {}'.format(cmd_type, message['service']))
                return utils.update_job(db, message['job_id'], STATUS_ACTIVE, 'Service is active')
    except ValidationError as e:
        print('Message JSON failed validation')
        return handle_exception(db, message['job_id'], e)

    utils.update_job(db, message['job_id'], STATUS_RUNNING)

    command = Command(cmd_type, cmd_prefix, 
                      message['service'], message['command'], message['tag'])
    
    try:
        status, result, stdout_data, stderr_data = command.execute()
        print('Result: {}'.format(result))
    except Exception as e:
        return handle_exception(db, message['job_id'], e)

    return utils.update_job(db, message['job_id'], status, result, stdout_data, stderr_data)


def handle_exception(db, msg_id, e):
    traceback.print_exc()
    return utils.update_job(db, msg_id, STATUS_FAIL, str(e))


def update_worker_status(db, instance_id, queue, status):
    name = 'worker:{}'.format(instance_id)
    db.hset(name, 'status', status)
    
    busy = '{}:workers:busy'.format(queue)
    if status == 'busy':
        db.sadd(busy, instance_id)
    elif status == 'idle':
        db.srem(busy, instance_id)
    elif status == 'dead'
        db.srem(busy, instance_id)
        db.smove('{}:workers'.format(queue), 'workers:dead', instance_id)


def register_worker(db, queue, worker_type):
    instance_id, instance_type, private_ip = get_instance_info()

    worker_info = {'queue': queue, 
                   'worker_type': worker_type, 
                   'status': 'idle', 
                   'instace_type': instance_type, 
                   'private_ip': private_ip}

    db.hmset('worker:{}'.format(instance_id), worker_info)
    db.sadd('{}:workers'.format(queue), instance_id)
    return instance_id


def run_worker(args):
    print('Starting worker on process {}'.format(os.getpid()))

    db = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    instance_id = register_worker(db, args.queue, args.exec_type)

    try:
        args.cmd_prefix = json.loads(args.cmd_prefix)
    except ValueError as e:
        print('Command prefix was not valid JSON')
        return
    if not utils.is_str_list(args.cmd_prefix):
        print('Command prefix was not a list of strings')
        return
    print('Command prefix: {}'.format(args.cmd_prefix))

    spinner = cycle(['/', '-', '\\', '|'])
    while True:
        message = utils.receive_message(db, args.queue)
        if message is not None:
            update_worker_status(db, instance_id, args.queue, 'busy')
            process_message(db, args.exec_type, args.cmd_prefix, message)
            update_worker_status(db, instance_id, args.queue, 'idle')
        else:
            sys.stdout.write(next(spinner))
            sys.stdout.flush()
            time.sleep(args.poll_frequency)
            sys.stdout.write('\b')


def build_cli_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-pf', '--poll_frequency', default=60, type=int, 
                        help='time to wait between polling the work queue (seconds)')
    parser.add_argument('-q', '--queue', default='docker', 
                        help='queue for the worker to pull work from (default is docker)')

    subparsers = parser.add_subparsers(dest='exec_type', help='worker type')
    subparsers.required = True

    parser_docker = subparsers.add_parser('docker', help='runs commands in docker containers')
    parser_docker.set_defaults(cmd_prefix='[]')
    parser_docker.set_defaults(worker_type=DOCKER_WORKER_TYPE)

    parser_native = subparsers.add_parser('native', help='runs commands natively')
    parser_native.add_argument('worker_type',
                        help='type of worker required for the service')
    parser_native.add_argument('cmd_prefix',
                        help='the command prefix of a native worker as a list of \
                              strings in json format, takes the place of the \
                              "ENTRYPOINT" in a docker container')
    return parser


if __name__ == '__main__': # pragma: no cover
    parser = build_cli_parser()
    args = parser.parse_args()
    try:
        worker_id = register_worker(args.queue, args.exec_type)
        run_worker(args)
    except KeyboardInterrupt:
        print('\rStopping worker')
        sys.exit()
    except Exception as e:
        db = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0)
        instance_id = get_instance_info()[0]
        update_worker_status(db, instance_id, 'dead')
        sys.exit()

