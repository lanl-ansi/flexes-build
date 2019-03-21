#!/usr/bin/env python3

import argparse
import boto3
import copy
import json
import os
import shutil
import signal
import sys
import time
import traceback
from . import utils
from .. import config
from itertools import cycle
from jsonschema import validate, ValidationError
from pathlib import Path
from redis import StrictRedis
from uuid import uuid4


class APIWorker(object):
    """Base class for API worker. Implements basic functionality for communicating 
        with the API. 

    Attributes:
        config (dict): Worker configuration
        local_files_path (str): Worker's root directory
        queue (str): Queue worker listens to, default `docker`
        poll_frequency (int): Worker queue poll frequency in seconds, default `1`
        db (redis.StrictRedis): Redis connection, connection parameters are specified 
            in the worker configuration file.
        s3 (boto3.resource): S3 connection
        dyn (boto3.resource): DynamoDB connection

    Args:
        queue (str): Queue worker listens to, default `docker`
        poll_frequency (int): Worker queue poll frequency in seconds, default `1`
    """
    def __init__(self, *args, **kwargs):
        self.config = config.load_config()
        self.message_schema = config.load_message_schema()
        self.local_files_path = str(Path.home().joinpath('lanlytics_worker_local', str(uuid4().hex)))
        self.queue = kwargs.get('queue', 'docker')
        self.poll_frequency = kwargs.get('poll_frequency', 1)
        self.db = StrictRedis(self.config['REDIS_HOST'], self.config['REDIS_PORT'], decode_responses=True)
        self.s3 = boto3.resource('s3', endpoint_url=self.config['S3_ENDPOINT'])
        self.dyn = boto3.resource('dynamodb', endpoint_url=self.config['DYNAMODB_ENDPOINT'])

    def test_service(self, message):
        print('Confirmed active status for {}'.format(message['service']))
        return self.update_job(message['job_id'], self.config['STATUS_ACTIVE'], 'Service is active')

    def process_message(self, message):
        """Execute a job based on a message received from the queue

        Args:
            message (dict): Message received from queue

        Returns:
            tuple: (job_status, job_result) 
        """
        print('Received message: {}'.format(message['job_id']))
        try:
            validate(message, self.message_schema)
            if 'test' in message and message['test']:
                self.update_job(message['job_id'], self.config['STATUS_RUNNING'], None)
                return self.test_service(message)
        except ValidationError as e:
            print('Message JSON failed validation')
            return self.handle_exception(message['job_id'], e)

        self.update_job(message['job_id'], self.config['STATUS_RUNNING'])
        try:
            status, result, stdout_data, stderr_data = self.launch(message)
            print('Result: {}'.format(result))
        except Exception as e:
            return self.handle_exception(message['job_id'], e)
        return self.update_job(message['job_id'], status, result, stdout_data, stderr_data)

    def receive_message(self):
        """Receive message from queue

        Returns:
            dict: Job message
        """
        message = self.db.rpop(self.queue)
        if message is not None:
            message = json.loads(message)
            self.update_job(message['job_id'], self.config['STATUS_RUNNING'])
        return message

    def update_job(self, job_id, status, result=None, stdout_data=None, stderr_data=None):
        """Update job status in database

        Args:
            job_id (str): Unique ID for job
            status (str): New job status
            result (str, optional): Result of job execution, default `None`
            stdout_data (str, optional): Return from STDOUT, default `None`
            stderr_data (str, optional): Return from STDERR, default `None`

        Returns:
            tuple: (job_status, job_result) 
        """
        job = self.config['JOB_PREFIX'] + job_id
        queue = self.db.hget(job, 'queue')
        self.db.hmset(job, 
                      {'status': status, 
                       'result': result, 
                       'stdout': stdout_data, 
                       'stderr': stderr_data})
        if status == self.config['STATUS_RUNNING']:
            self.db.sadd('{}:jobs:running'.format(queue), job_id)
        elif status in [self.config['STATUS_COMPLETE'], self.config['STATUS_FAIL']]:
            self.db.expire(job, 60)
            self.db.srem('{}:jobs'.format(queue), job_id)
            self.db.srem('{}:jobs:running'.format(queue), job_id)
            table = self.dyn.Table(self.config['JOBS_TABLE'])
            table.update_item(Key={'job_id': job_id},
                              UpdateExpression='SET #stat = :val1, #r = :val2',
                              ExpressionAttributeNames={'#stat': 'status', '#r': 'result'},
                              ExpressionAttributeValues={':val1': status, ':val2': result})
        elif status == self.config['STATUS_ACTIVE']:
            self.db.expire(job, 30)
            self.db.srem('{}:jobs'.format(queue), job_id)
            self.db.srem('{}:jobs:running'.format(queue), job_id)
        return status, result

    def update_job_messages(self, job_id, messages):
        """Update intermediate job execution messages in database

        Args:
            job_id (str): Unique ID for job
            messages (list): List of messages from running job
        """
        job = self.config['JOB_PREFIX'] + job_id
        self.db.hmset(job, {'messages': messages})

    def get_local_path(self, uri):
        """Get local path from S3 URI

        Args:
            uri (str): S3 URI to resolve

        Returns:
            str: Local file path
        """
        if utils.is_s3_uri(uri):
            local_filename = Path(self.local_files_path).joinpath(Path(uri).relative_to('s3://'))
            return str(local_filename)
        return uri

    def make_local_dirs(self, local_file):
        """Create intermediate directories for file path

        Args:
            local_file (str): Local file path
        """
        directory = Path(local_file).parent
        if not directory.exists():
            os.makedirs(directory)

    def localize_resource(self, uri):
        """Take an S3 URI and download it to the worker's local file system

        Args:
            uri (str): S3 URI

        Returns:
            str: Local path to downloaded file
        """
        if utils.is_s3_uri(uri):
            local_file_name = self.get_local_path(uri)
            self.make_local_dirs(local_file_name)
            print('Downloading to local filesystem:\n{}\n{}'.format(uri, local_file_name))
            utils.get_s3_file(self.s3, uri, local_file_name)
            return local_file_name
        else:
            return uri

    def localize_output(self, uri):
        """Get local path for output file

        Args:
            uri (str): S3 URI for output

        Returns:
            str: Local path for output file
        """
        if utils.is_s3_uri(uri):
            local_path = self.get_local_path(uri)
            self.make_local_dirs(local_path)
            return local_path
        else:
            return uri

    def persist_resource(self, uri):
        """Upload local file to S3

        Args:
            uri (str): S3 URI for file destination        
        """
        if utils.is_s3_uri(uri):
            local_file_name = self.get_local_path(uri)
            print('Uploading to s3:\n  {}\n  {}'.format(local_file_name, uri))
            utils.put_file_s3(self.s3, local_file_name, uri)

    def localize_command(self, command):
        """Localize input and output arguments in command

        Args:
            command (dict): Command for worker to execute

        Returns:
            dict: Command rewritten with local input and output arguments
        """
        local_command = copy.deepcopy(command)
        if 'stdin' in local_command and local_command['stdin']['type'] == 'uri':
            local_command['stdin']['value'] = self.localize_resource(local_command['stdin']['value'])
        if 'stdout' in local_command and local_command['stdout']['type'] == 'uri': 
            local_command['stdout']['value'] = self.localize_output(local_command['stdout']['value'])
        if 'stderr' in local_command and local_command['stdout']['type'] == 'uri':
            local_command['stderr']['value'] = self.localize_output(local_command['stderr']['value'])
        if 'input' in local_command:
            for uri in local_command['input']:
                self.localize_resource(uri)
        if 'output' in local_command:
            for uri in local_command['output']:
                self.localize_output(uri)
        for arg in local_command['arguments']:
            if arg['type'] == 'input':
                arg['value'] = self.localize_resource(arg['value'])
            if arg['type'] == 'output':
                arg['value'] = self.localize_output(arg['value'])
            if arg['type'] == 'parameter' and utils.is_s3_uri(arg['value']):
                print('WARNING: s3 uri used in a parameter')
        return local_command

    def persist_command(self, command):
        """Upload outputs specified in command

        Args:
            command (dict): Command for worker to execute
        """
        print(command)
        if 'stdout' in command and command['stdout']['type'] == 'uri':
            self.persist_resource(command['stdout']['value'])
        if 'stderr' in command and command['stderr']['type'] == 'uri':
            self.persist_resource(command['stderr']['value'])
        if 'output' in command:
            for uri in command['output']:
                self.persist_resource(uri)
        for arg in command['arguments']:
            if arg['type'] == 'output':
                self.persist_resource(arg['value'])

    # This is not currently used, but may still be useful
    @staticmethod
    def build_bash_command(local_command):
        bash_command = []
        for arg in local_command['arguments']:
            param = arg['value']
            if 'name' in arg:
                param = '{} {}'.format(arg['name'], param)
            bash_command.append(param)
        if 'stdin' in local_command:
            stdin = '< {}'.format(local_command['stdin']['value'])
            bash_command.append(stdin)
        if 'stdout' in local_command:
            stdout = '> {}'.format(local_command['stdout']['value'])
            bash_command.append(stdout)
        if 'stderr' in local_command:
            stderr = '2> {}'.format(local_command['stderr']['value'])
            bash_command.append(stderr)
        return bash_command

    def build_command_parts(self, local_command):
        """Convert command dictionary to a list of command arguments

        Args:
            local_command (dict): Command for worker to execute with input and output 
                arguments localized

        Returns:
            tuple:
                list: A list of command arguments
                str: Value to pass to STDIN
                bool: Whether to pipe value through STDIN
                str: URI for storing output from STDOUT
                bool: Whether to pipe STDOUT to user
                str: URI for storing output from STDERR
                bool: Whether to pipe STDERR to user
        """
        stdin = stdout = stderr = None
        stdin_pipe = stdout_pipe = stderr_pipe = False 
        command = []
        for arg in local_command['arguments']:
            if 'name' in arg:
                delimiter = arg.get('delimiter', ' ')
                command.append(arg['name'] + delimiter + arg['value'])
            else:
                command.append(arg['value'])

        if 'stdin' in local_command:
            stdin = local_command['stdin']['value']
            stdin_pipe = local_command['stdin']['type'] == 'pipe'
        if 'stdout' in local_command:
            if local_command['stdout']['type'] == 'uri':
                stdout = local_command['stdout']['value']
            else:
                assert(local_command['stdout']['type'] == 'pipe')
                stdout_pipe = True
        if 'stderr' in local_command:
            if local_command['stderr']['type'] == 'uri':
                stdout = local_command['stderr']['value']
            else:
                assert(local_command['stderr']['type'] == 'pipe')
                stderr_pipe = True
        return command, stdin, stdin_pipe, stdout, stdout_pipe, stderr, stderr_pipe


    def build_localized_command(self, command, cmd_prefix=[]):
        """Build command with localized input and output arguments
        
        Args:
            command (dict): Command for worker to execute

        Returns:
            dict: Command with input and output arguments localized
        """
        abstract_cmd = self.build_bash_command(command)
        print('\nAbstract unix command:')
        print('{} {}\n'.format(cmd_prefix, abstract_cmd))
        local_command = self.localize_command(command)
        return local_command

    def worker_cleanup(self, command, exit_code, worker_log, stdout_data, stderr_data):
        """Clean up files and upload output after worker execution
        
        Args:
            command (dict): Command worker used to execute job
            exit_code (int): Code returned when executed completed
            worker_log (str): Output from worker during execution
            stdout_data (str): Return from STDOUT during execution
            stderr_data (str): Return from STDERR during execution

        Returns:
            tuple:
                str: Status of job execution
                str: Description of job execution
                str: Return from STDOUT during execution
                str: Return from STDERR during execution
        """
        print('Exit code: {}'.format(exit_code))
        feedback = 'Job finished with exit code {}'.format(exit_code)
        
        if exit_code != 0:
            print('\nWorker log:')
            print(worker_log)
            status = self.config['STATUS_FAIL']
            feedback = feedback + '\n' + worker_log
        else:
            print('\nPersisting output:')
            status = self.config['STATUS_COMPLETE']
            self.persist_command(command)
        print('\nCleaning local cache: {}'.format(self.local_files_path))
        try:
            shutil.rmtree(self.local_files_path)
        except FileNotFoundError as e:
            pass # this is needed in case the job terminates before it starts
        print('\nJob completed.')
        return status, feedback, stdout_data, stderr_data

    def handle_exception(self, msg_id, e):
        """Handle exception during job execution
        
        Args:
            msg_id (str): Unique ID for job execution
            e (Exception): Exception encountered during execution

        Returns:
            tuple: (job_status, job_result) 
        """
        traceback.print_exc()
        return self.update_job(msg_id, self.config['STATUS_FAIL'], str(e))

    def gracefully_exit(self, signo, stack_frame):
        """Handle SIGTERM message

        Args:
            signo (int): Signal code
            stack_frame (str): Current stack frame
        """
        ## TODO: handle case where worker has an active job
        print('SIGTERM received: {} {}'.format(signo, stack_frame))
        update_worker_status('dead')
        sys.exit(0)

    def launch(self, message):
        """Method for executing job on worker

        Args:
            message (dict): Message for worker to use for execution

        Raises:
            NotImplementedError: If method is not overridden by child class
        """
        raise NotImplementedError('launch method is not implemented')

    def update_worker_status(self, status):
        name = self.config['WORKER_PREFIX'] + self.instance_id
        self.db.hset(name, 'status', status)
        
        busy = '{}:workers:busy'.format(self.queue)
        if status == 'busy':
            self.db.sadd(busy, self.instance_id)
        elif status == 'idle':
            self.db.srem(busy, self.instance_id)
        elif status == 'dead':
            self.db.srem(busy, self.instance_id)
            self.db.smove('{}:workers'.format(self.queue), 'workers:dead', self.instance_id)
            self.db.expire(self.config['WORKER_PREFIX'] + self.instance_id, 600)

    def register_worker(self):
        """Create entry for worker in database
        
        Returns:
            str: Unique ID for worker
        """
        instance_id, instance_type, private_ip = utils.get_instance_info()
        self.instance_id = instance_id

        worker_info = {'queue': self.queue, 
                       'worker_type': self.__class__.__name__, 
                       'status': 'idle', 
                       'instance_type': instance_type, 
                       'private_ip': private_ip}
        worker_id = self.config['WORKER_PREFIX'] + self.instance_id
        if self.db.exists(worker_id):
            keys = self.db.keys(pattern='{}*'.format(worker_id))
            worker_id = '{}_{}'.format(worker_id, len(keys))

        self.db.hmset(worker_id, worker_info)
        self.db.sadd('{}:workers'.format(self.queue), self.instance_id)
        return instance_id

    def run(self):
        """Start worker"""
        signal.signal(signal.SIGTERM, self.gracefully_exit)
        print('Starting worker on process {}'.format(os.getpid()))
        self.register_worker()

        spinner = cycle(['/', '-', '\\', '|'])
        try:
            while True:
                message = self.receive_message()
                if message is not None:
                    self.update_worker_status('busy')
                    self.process_message(message)
                    self.update_worker_status('idle')
                else:
                    sys.stdout.write(next(spinner))
                    sys.stdout.flush()
                    time.sleep(self.poll_frequency)
                    sys.stdout.write('\b')
        except KeyboardInterrupt:
            print('\rStopping worker')
            self.update_worker_status('dead')
        except Exception as e:
            print(e)
            self.update_worker_status('dead')
                
