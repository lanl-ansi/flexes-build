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
import io
from settings import *
from uuid import uuid4

HOME = os.path.abspath(os.sep)
if os.name == 'nt':
    if 'HOMEPATH' in os.environ:
        HOME = os.environ['HOMEDRIVE'] + os.environ['HOMEPATH']
else:
    if 'HOME' in os.environ:
        HOME = os.environ['HOME']

LOCAL_FILES_DIR = os.path.join('lanlytics_worker_local', str(uuid4().hex))
LOCAL_FILES_PATH = os.path.join(HOME, LOCAL_FILES_DIR)

LOG_LINE_LIMIT = 10


class Command:
    def __init__(self, cmd_type, cmd_prefix, service, command, tag='latest'):
        if cmd_type not in ['docker', 'native']:
            raise TypeError('Invalid worker type: {}'.format(cmd_type))

        self.command = command
        self.prefix = cmd_prefix
        self.service = service
        self.tag = tag
        self.type = cmd_type

    def execute(self):
        if self.type == 'docker':
            return launch_container(self.service, self.command, self.tag)
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
    if 'stdin' in local_command and local_command['stdin']['type'] == 'uri':
        local_command['stdin']['value'] = localize_resource(local_command['stdin']['value'])
    if 'stdout' in local_command and local_command['stdout']['type'] == 'uri': 
        local_command['stdout']['value'] = localize_output(local_command['stdout']['value'])
    if 'stderr' in local_command and local_command['stdout']['type'] == 'uri':
        local_command['stderr']['value'] = localize_output(local_command['stderr']['value'])
    if 'input' in local_command:
        for uri in local_command['input']:
            localize_resource(uri)
    if 'output' in local_command:
        for uri in local_command['output']:
            localize_output(uri)
    for arg in local_command['arguments']:
        if arg['type'] == 'input':
            arg['value'] = localize_resource(arg['value'])
        if arg['type'] == 'output':
            arg['value'] = localize_output(arg['value'])
        if arg['type'] == 'parameter' and utils.is_s3_uri(arg['value']):
            print('WARNING: s3 uri used in a parameter')
    return local_command


def dockerize_command(local_command):
    docker_command = copy.deepcopy(local_command)
    if 'stdin' in docker_command and docker_command['stdin']['type'] == 'uri':
        docker_command['stdin']['value'] = get_docker_path(docker_command['stdin']['value'])
    if 'stdout' in docker_command and docker_command['stdout']['type'] == 'uri':
        docker_command['stdout']['value'] = get_docker_path(docker_command['stdout']['value'])
    if 'stderr' in docker_command and docker_command['stderr']['type'] == 'uri':
        docker_command['stderr']['value'] = get_docker_path(docker_command['stderr']['value'])
    for arg in docker_command['arguments']:
        if arg['type'] == 'input':
            arg['value'] = get_docker_path(arg['value'])
        if arg['type'] == 'output':
            arg['value'] = get_docker_path(arg['value'])
    return docker_command


def persist_command(command):
    print(command)
    if 'stdout' in command and command['stdout']['type'] == 'uri':
        persist_resource(command['stdout']['value'])
    if 'stderr' in command and command['stderr']['type'] == 'uri':
        persist_resource(command['stderr']['value'])
    if 'output' in command:
        for uri in command['output']:
            persist_resource(uri)
    for arg in command['arguments']:
        if arg['type'] == 'output':
            persist_resource(arg['value'])


# This is not currently used, but may still be useful

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


def build_command_parts(local_command):
    python_command = []
    stdin = None
    stdin_pipe = False
    stdout = None
    stdout_pipe = False
    stderr = None
    stderr_pipe = False
    
    for arg in local_command['arguments']:
        param = arg['value']
        if 'name' in arg:
            param = arg['name'] + param
        python_command.append(param)

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

    return python_command, stdin, stdin_pipe, stdout, stdout_pipe, stderr, stderr_pipe


def build_localized_command(command, cmd_prefix=[]):
    abstract_cmd = build_bash_command(command)
    print('\nAbstract unix command:')
    print('{} {}\n'.format(cmd_prefix, abstract_cmd))

    local_command = localize_command(command)

    return local_command


def worker_cleanup(command, exit_code, worker_log, stdout_data, stderr_data):
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
    try:
        shutil.rmtree(LOCAL_FILES_PATH)
    except FileNotFoundError as e:
        pass # this is needed in case the job terminates before it starts

    print('\nJob completed.')
    return status, feedback, stdout_data, stderr_data


def launch_native(cmd_prefix, command):
    print('\n\033[1mStarting Native Job\033[0m')

    local_command = build_localized_command(command, cmd_prefix)

    stdin = None
    stdout = subprocess.PIPE
    stderr = subprocess.PIPE

    native_cmd, stdin_file, stdin_pipe, stdout_file, stdout_pipe, stderr_file, stderr_pipe = build_command_parts(local_command)

    native_cmd = cmd_prefix + native_cmd

    if stdin_file != None:
        if stdin_pipe:
            stdin = io.StringIO(stdin_file)
        else:
            stdin = open(stdin_file, 'r')

    if stdout_file != None:
        stdout = open(stdout_file, 'w')
    if stdout_pipe:
        assert(stdout_file == None)
        stdout_file = ''
        stdout = io.StringIO(stdout_file)

    if stderr_file != None:
        stderr = open(stderr_file, 'w')
    if stderr_pipe:
        assert(stderr_file == None)
        stderr_file = ''
        stderr = io.StringIO(stderr_file)


    print('\nNative command:')
    print(native_cmd)
    print('stdin:  {}'.format(stdin))
    print('stdout: {}'.format(stdout))
    print('stderr: {}'.format(stderr))
    
    # Shell command used for Windows support
    process = subprocess.Popen(native_cmd, stdin=stdin, 
                               stdout=stdout, stderr=stderr, 
                               shell=(os.name == 'nt'))

    stdout_log, stderr_log = process.communicate()

    if stdout_log != None:
        stdout_log = lines_tail(stdout_log.decode('utf-8'), LOG_LINE_LIMIT)
    if stderr_log != None:
        stderr_log = lines_tail(stderr_log.decode('utf-8'), LOG_LINE_LIMIT)

    worker_log = 'stdout:\n{}\n\nstderr:\n{}'.format(stdout_log, stderr_log)

    stdout_data = None
    stderr_data = None
    if stdout_pipe:
        stdout_data = stdout_file
    if stderr_pipe:
        stderr_data = stderr_file


    if stdin_file != None:
        stdin.close()
    if stdout_file != None:
        stdout.close()
    if stderr_file != None:
        stderr.close()

    return worker_cleanup(command, process.returncode, worker_log, stdout_data, stderr_data)


def launch_container(image_name, command, tag='latest'):
    print('\n\033[1mStarting Docker Job\033[0m')

    image = '{}/{}:{}'.format(DOCKER_REGISTRY, image_name, tag)
    print('\nDocker Image: {}'.format(image))

    local_command = build_localized_command(command)
    local_cmd, stdin_file, stdin_pipe, stdout_file, stdout_pipe, stderr_file, stderr_pipe = build_command_parts(local_command)

    docker_command = dockerize_command(local_command)
    docker_cmd, *docker_other = build_command_parts(docker_command)

    stdin_data = None
    if stdin_file != None:
        if stdin_pipe:
            stdin_data = stdin_file
        else:
            with open(stdin_file, 'r') as stdin:
                stdin_data = stdin.read()

    docker_cmd = ' '.join(docker_cmd)
    print('\nDocker command: {}'.format(docker_cmd))

    print('\nSetting up docker container')
    client = docker.DockerClient(base_url='unix://var/run/docker.sock', version='auto')
    
    environment = {'API_ENDPOINT': API_ENDPOINT}

    docker_volume = os.path.join('/', LOCAL_FILES_DIR)
    volumes = {LOCAL_FILES_PATH: {'bind': docker_volume, 'mode': 'rw'}}
    print(volumes)

    stdout_data = None
    stderr_data = None
    try:
        client.images.pull(image)
        container = client.containers.run(image, 
                                          command=docker_cmd, 
                                          detach=True, 
                                          environment=environment,
                                          volumes=volumes, 
                                          stdin_open = (stdin_data != None))

        if stdin_data != None:
            socket = container.attach_socket(params={'stdin': 1, 'stream': 1})
            os.write(socket.fileno(), stdin_data.encode())
            socket.close()
            print('input socket closed')

        exit_code = container.wait()
        logs = container.logs(stdout=True, stderr=True).decode('utf-8')

        if stdout_file != None:
            with open(stdout_file, 'w') as stdout:
                stdout.write(container.logs(stdout=True, stderr=False).decode('utf-8'))
        else:
            if stdout_pipe:
                stdout_data = container.logs(stdout=True, stderr=False).decode('utf-8')

        if stderr_file != None:
            with open(stderr_file, 'w') as stderr:
                stderr.write(container.logs(stdout=False, stderr=True).decode('utf-8'))
        else:
            if stderr_pipe:
                stderr_data = container.logs(stdout=False, stderr=True).decode('utf-8')

        container.remove()

    except docker.errors.ContainerError as e:
        print('Container error: {}'.format(e))
        logs = e.stderr.decode('utf-8')
        exit_code = e.exit_status
    except docker.errors.ImageNotFound as e:
        print('{} not found'.format(image))
        logs = 'Image not found'
        exit_code = -1

    return worker_cleanup(command, exit_code, logs, stdout_data, stderr_data)


if __name__ == '__main__': # pragma: no cover
    print(sys.argv[1])
    print(sys.argv[2])
    launch_container(sys.argv[1], sys.argv[2])
