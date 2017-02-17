import boto3
import copy
import docker
import json
import os
import shutil
import subprocess
import sys
import time
import utils
from settings import *

HOME = os.path.abspath(os.sep)
if os.name == 'nt':
    if 'HOMEPATH' in os.environ:
        HOME = os.environ['HOMEDRIVE'] + os.environ['HOMEPATH']
else:
    if 'HOME' in os.environ:
        HOME = os.environ['HOME']

LOCAL_FILES_DIR = os.path.join('lanlytics_worker_local', str(os.getpid()))
LOCAL_FILES_PATH = os.path.join(HOME, LOCAL_FILES_DIR)

LOG_LINE_LIMIT = 10


class Command:
    def __init__(self, cmd_type, message, cmd_prefix):
        if cmd_type not in ['docker', 'native']:
            raise TypeError('Invalid worker type: {}'.format(cmd_type))

        self.command = json.loads(message['body'])
        self.prefix = cmd_prefix
        self.service = message['service']
        self.type = cmd_type

    def execute(self):
        if self.type == 'docker':
            return launch_container(self.service, self.command)
        elif self.type == 'native':
            return launch_native(self.prefix, self.command)


def lines_tail(string, tail_length):
    parts = string.split('\n')
    parts = parts[-tail_length:]
    return '\n'.join(parts)


def get_local_path(uri):
    if utils.is_s3_uri(uri):
        local_file_name = uri.replace('s3:/', LOCAL_FILES_PATH)
        return local_file_name
    return uri


def make_local_dirs(local_file):
    directory = os.path.dirname(local_file)
    if not os.path.exists(directory):
        os.makedirs(directory)

        
def get_docker_path(uri):
    path = get_local_path(uri)
    if path.startswith(LOCAL_FILES_PATH):
        return path.replace(LOCAL_FILES_PATH, os.sep+LOCAL_FILES_DIR)
    else:
        return path


def localize_resource(uri):
    if utils.is_s3_uri(uri):
        s3 = boto3.resource('s3')
        local_file_name = get_local_path(uri)
        make_local_dirs(local_file_name)

        print('Downloading to local filesystem:\n{}\n{}'.format(uri, local_file_name))
        utils.get_s3_file(s3, uri, local_file_name)
        return local_file_name
    else:
        return uri


def localize_output(uri):
    if utils.is_s3_uri(uri):
        local_path = get_local_path(uri)
        make_local_dirs(local_path)
        return local_path
    else:
        return uri


def persist_resource(uri):
    if utils.is_s3_uri(uri):
        s3 = boto3.resource('s3')
        local_file_name = get_local_path(uri)

        print('Uploading to s3:\n  {}\n  {}'.format(local_file_name, uri))
        utils.put_file_s3(s3, local_file_name, uri)


def localize_command(command):
    local_command = copy.deepcopy(command)
    if 'stdin' in local_command:
        local_command['stdin'] = localize_resource(local_command['stdin'])
    if 'stdout' in local_command:
        local_command['stdout'] = localize_output(local_command['stdout'])
    if 'stderr' in local_command:
        local_command['stderr'] = localize_output(local_command['stderr'])
    if 'input' in local_command:
        for uri in local_command['input']:
            localize_resource(uri)
    if 'output' in local_command:
        for uri in local_command['output']:
            localize_output(uri)
    for parameter in local_command['command']:
        if parameter['type'] == 'input':
            parameter['value'] = localize_resource(parameter['value'])
        if parameter['type'] == 'output':
            parameter['value'] = localize_output(parameter['value'])
        if parameter['type'] == 'parameter' and utils.is_s3_uri(parameter['value']):
            print('WARNING: s3 uri used in a parameter')
    return local_command


def dockerize_command(local_command):
    docker_command = copy.deepcopy(local_command)
    if 'stdin' in docker_command:
        docker_command['stdin'] = get_docker_path(docker_command['stdin'])
    if 'stdout' in docker_command:
        docker_command['stdout'] = get_docker_path(docker_command['stdout'])
    if 'stderr' in docker_command:
        docker_command['stderr'] = get_docker_path(docker_command['stderr'])
    for parameter in docker_command['command']:
        if parameter['type'] == 'input':
            parameter['value'] = get_docker_path(parameter['value'])
        if parameter['type'] == 'output':
            parameter['value'] = get_docker_path(parameter['value'])
    return docker_command


def persist_command(command):
    print(command)
    if 'stdout' in command:
        persist_resource(command['stdout'])
    if 'stderr' in command:
        persist_resource(command['stderr'])
    if 'output' in command:
        for uri in command['output']:
            persist_resource(uri)
    for parameter in command['command']:
        if parameter['type'] == 'output':
            persist_resource(parameter['value'])


# This is not currently used, but may still be useful

def build_bash_command(local_command):
    bash_command = []

    for parameter in local_command['command']:
        param = parameter['value']
        if 'name' in parameter:
            param = '{} {}'.format(parameter['name'], param)
        bash_command.append(param)
    if 'stdin' in local_command:
        stdin = '< {}'.format(local_command['stdin'])
        bash_command.append(stdin)
    if 'stdout' in local_command:
        stdout = '> {}'.format(local_command['stdout'])
        bash_command.append(stdout)
    if 'stderr' in local_command:
        stderr = '2> {}'.format(local_command['stderr'])
        bash_command.append(stderr)

    return bash_command


def build_command_parts(local_command):
    python_command = []
    stdin = None
    stdout = None
    stderr = None
    
    for parameter in local_command['command']:
        param = parameter['value']
        if 'name' in parameter:
            param = parameter['name'] + param
        python_command.append(param)
    if 'stdin' in local_command:
        stdin = local_command['stdin']
    if 'stdout' in local_command:
        stdout = local_command['stdout']
    if 'stderr' in local_command:
        stderr = local_command['stderr']

    return python_command, stdin, stdout, stderr


def build_localized_command(command, cmd_prefix=[]):
    abstract_cmd = build_bash_command(command)
    print('\nAbstract unix command:')
    print('{} {}\n'.format(cmd_prefix, abstract_cmd))

    local_command = localize_command(command)

    return local_command


def worker_cleanup(command, exit_code, worker_log):
    print('Exit code: {}'.format(exit_code))
    feedback = 'Job finished with exit code: {}'.format(exit_code)
    
    if exit_code != 0:
        print('\nWorker log:')
        print(worker_log)
        status = STATUS_FAIL
        feedback = feedback + '\n' + worker_log
    else:
        print('\nPersisting output:')
        status = STATUS_COMPLETE
        persist_command(command)

    print('\nCleaning local cache: {}'.format(LOCAL_FILES_PATH))
    shutil.rmtree(LOCAL_FILES_PATH)

    print('\nJob completed.')
    return status, feedback


def launch_native(cmd_prefix, command):
    print('\n\033[1mStarting Native Job\033[0m')

    local_command = build_localized_command(command, cmd_prefix)

    stdin = None
    stdout = subprocess.PIPE
    stderr = subprocess.PIPE

    native_cmd, stdin_file, stdout_file, stderr_file = build_command_parts(local_command)

    native_cmd = cmd_prefix + native_cmd

    if stdin_file != None:
        stdin = open(stdin_file, 'r')

    if stdout_file != None:
        stdout = open(stdout_file, 'w')

    if stderr_file != None:
        stderr = open(stderr_file, 'w')

    print('\nNative command:')
    print(native_cmd)
    print('stdin:  {}'.format(stdin))
    print('stdout: {}'.format(stdout))
    print('stderr: {}'.format(stderr))
    
    # Shell parameter used for Windows support
    process = subprocess.Popen(native_cmd, stdin=stdin, 
                               stdout=stdout, stderr=stderr, 
                               shell=(os.name == 'nt'))

    stdout_log, stderr_log = process.communicate()

    if stdout_log != None:
        stdout_log = lines_tail(stdout_log.decode('utf-8'), LOG_LINE_LIMIT)
    if stderr_log != None:
        stderr_log = lines_tail(stderr_log.decode('utf-8'), LOG_LINE_LIMIT)

    worker_log = 'stdout:\n{}\n\nstderr:\n{}'.format(stdout_log, stderr_log)

    if stdin_file != None:
        stdin.close()
    if stdout_file != None:
        stdout.close()
    if stderr_file != None:
        stderr.close()

    return worker_cleanup(command, process.returncode, worker_log)


def launch_container(image_name, command):
    print('\n\033[1mStarting Docker Job\033[0m')

    image = 'hub.lanlytics.com/{}:latest'.format(image_name)
    print('\nDocker Image: {}'.format(image))

    local_command = build_localized_command(command)
    local_cmd, stdin_file, stdout_file, stderr_file = build_command_parts(local_command)

    if stdin_file != None:
        return worker_cleanup(command, 999, 'stdin is not currently supported on generic workers')

    docker_command = dockerize_command(local_command)
    docker_cmd, docker_stdin_file, docker_stdout_file, docker_stderr_file = build_command_parts(docker_command)

    docker_cmd = ' '.join(docker_cmd)
    print('\nDocker command: {}'.format(docker_cmd))

    print('\nSetting up docker container')
    client = docker.DockerClient(base_url='unix://var/run/docker.sock', version='auto')
    
    docker_volume = os.path.join('/', LOCAL_FILES_DIR)
    volumes = {LOCAL_FILES_PATH: {'bind': docker_volume, 'mode': 'rw'}}
    print(volumes)

    try:
        container = client.containers.run(image, volumes=volumes, command=docker_cmd, detach=True)

        # this is bascially useless
        #print(container.status)

        #blocks until container's work is done
        exit_code = container.wait()

        logs = container.logs(stdout=True, stderr=True).decode('utf-8')

        if stdout_file != None:
            with open(stdout_file, 'w') as stdout:
                stdout.write(container.logs(stdout=True, stderr=False).decode('utf-8'))

        if stderr_file != None:
            with open(stderr_file, 'w') as stderr:
                stderr.write(container.logs(stdout=False, stderr=True).decode('utf-8'))

        container.remove()

    except docker.errors.ContainerError as e:
        print('Container error: {}'.format(e))
        logs = e.stderr.decode('utf-8')
        exit_code = e.exit_status
    except docker.errors.ImageNotFound as e:
        print('{} not found'.format(image))
        logs = 'Image not found'
        exit_code = -1

    return worker_cleanup(command, exit_code, logs)


if __name__ == '__main__':
    print(sys.argv[1])
    print(sys.argv[2])
    launch_container(sys.argv[1], sys.argv[2])
