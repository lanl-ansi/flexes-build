import boto3
import json
import os
import sys
import time
import copy
import shutil
import subprocess
from jsonschema import validate, ValidationError

home = os.path.abspath(os.sep)
if os.name == 'nt':
    if 'HOMEPATH' in os.environ:
        home = os.environ['HOMEPATH']
else:
    if 'HOME' in os.environ:
        home = os.environ['HOME']

local_files_dir = os.path.join('lanlytics_worker_local', str(os.getpid()))
local_files_path = os.path.join(home, local_files_dir)

log_line_limit = 10

class Command:
    def __init__(self, cmd_type, cmd):
        self.type = cmd_type
        self.cmd = cmd

        if cmd_type = 'docker':
            self.assign_methods(dockerize_command, launch_container, worker_cleanup, None)
        elif cmd_type == 'native':
            self.assign_methods(localize_command, launch_native, worker_cleanup, None)
        else:
            raise TypeError('Invalid worker type: {}'.format(cmd_type))

    def assign_methods(build, execute, cleanup, output):
        self.build = build
        self.execute = execute
        self.cleanup = cleanup
        self.output = output


def is_s3_uri(uri):
    worker_dir_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(worker_dir_path, 'message_schema.json')) as file:
        msg_schema = json.load(file)
        s3_uri_schema = msg_schema['definitions']['s3_uri']

    try:
        validate(uri, s3_uri_schema)
        return True
    except ValidationError:
        return False


def s3_get_uri(s3_uri):
    return s3_uri.split('/',2)[-1].split('/',1)


def get_s3_file(s3_conn, s3_uri, local_file):
    bucket_id, key = s3_get_uri(s3_uri)
    s3_conn.download_file(bucket_id, key, local_file)


def put_file_s3(s3_conn, local_file, s3_uri):
    bucket_id, key = s3_get_uri(s3_uri)
    s3_conn.upload_file(local_file, bucket_id, key)


def get_local_path(uri):
    if is_s3_uri(uri):
        local_file_name = uri.replace('s3:/', local_files_path)
        return local_file_name
    return uri


def get_docker_path(uri):
    path = get_local_path(uri)
    if path.startswith(local_files_path):
        return path.replace(local_files_path, os.sep+local_files_dir)
    return path


def make_local_dirs(local_file):
    directory = os.path.dirname(local_file)
    if not os.path.exists(directory):
        os.makedirs(directory)


def lines_tail(string, tail_length):
    parts = string.split('\n')
    parts = parts[-tail_length:]
    return '\n'.join(parts)


def localize_resource(uri):
    if is_s3_uri(uri):
        s3 = boto3.client('s3')
        local_file_name = get_local_path(uri)
        make_local_dirs(local_file_name)

        print('downloading to local filesystem:\n  %s\n  %s' % (uri, local_file_name))
        get_s3_file(s3, uri, local_file_name)

        return local_file_name
    return uri


def localize_output(uri):
    if is_s3_uri(uri):
        local_path = get_local_path(uri)
        make_local_dirs(local_path)
        return local_path
    return uri


def persist_resource(uri):
    if is_s3_uri(uri):
        s3 = boto3.client('s3')
        local_file_name = get_local_path(uri)

        print('uploading to s3:\n  %s\n  %s' % (local_file_name, uri))
        put_file_s3(s3, local_file_name, uri)


def localize_command(command):
    local_command = copy.deepcopy(command)
    if 'stdin' in local_command:
        local_command['stdin'] = localize_resource(local_command['stdin'])
    if 'stdout' in local_command:
        local_command['stdout'] = localize_output(local_command['stdout'])
    if 'stderr' in local_command:
        local_command['stderr'] = localize_output(local_command['stderr'])
    for parameter in local_command['command']:
        if parameter['type'] == 'input':
            parameter['value'] = localize_resource(parameter['value'])
        if parameter['type'] == 'output':
            parameter['value'] = localize_output(parameter['value'])
        if parameter['type'] == 'parameter' and is_s3_uri(parameter['value']):
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


def persist_command(local_command):
    if 'stdout' in local_command:
        persist_resource(local_command['stdout'])
    if 'stderr' in local_command:
        persist_resource(local_command['stderr'])
    for parameter in local_command['command']:
        if parameter['type'] == 'output':
            persist_resource(parameter['value'])


def build_bash_command(local_command):
    bash_command = []

    for parameter in local_command['command']:
        param = parameter['value']
        if 'name' in parameter:
            param = parameter['name']+param
        bash_command.append(param)
    if 'stdin' in local_command:
        stdin = '< %s' % local_command['stdin']
        bash_command.append(stdin)
    if 'stdout' in local_command:
        stdout = '> %s' % local_command['stdout']
        bash_command.append(stdout)
    if 'stderr' in local_command:
        stderr = '2> %s' % local_command['stderr']
        bash_command.append(stderr)

    return bash_command


def build_python_command(local_command):
    python_command = []
    stdin = None
    stdout = None
    stderr = None
    
    for parameter in local_command['command']:
        param = parameter['value']
        if 'name' in parameter:
            param = parameter['name']+param
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
    print('\nabstract unix command:')
    print(' '.join(cmd_prefix+abstract_cmd)+'\n')

    local_command = localize_command(command)

    return local_command


def worker_cleanup(command, exit_code, worker_log):
    print('exit code - %d' % exit_code)
    feedback = 'job finished with exit code: %d' % exit_code
    
    if exit_code != 0:
        print('\nworker log:')
        print(worker_log)
        feedback = feedback+'\n'+worker_log
    else:
        print('\npersisting output:')
        persist_command(command)

    print('\ncleaning local cache: %s' % local_files_path)
    shutil.rmtree(local_files_path)

    print('\njob completed.')
    return feedback


def launch_native(cmd_prefix, command):
    print('\n\033[1mStarting Native Job\033[0m')

    local_command = build_localized_command(command, cmd_prefix)

    stdin = None
    stdout = subprocess.PIPE
    stderr = subprocess.PIPE

    native_cmd, stdin_file, stdout_file, stderr_file = build_python_command(local_command)

    native_cmd = cmd_prefix+native_cmd
    #native_cmd = ' '.join(native_cmd)

    if stdin_file != None:
        stdin = open(stdin_file, 'r')

    if stdout_file != None:
        stdout = open(stdout_file, 'w')

    if stderr_file != None:
        stderr = open(stderr_file, 'w')

    print('\nnative command:')
    print(native_cmd)
    print('stdin:  %s' % str(stdin))
    print('stdout: %s' % str(stdout))
    print('stderr: %s' % str(stderr))
    
    # shell parameter used for windows support
    process = subprocess.Popen(native_cmd, stdin=stdin, stdout=stdout, stderr=stderr, shell=(os.name == 'nt'))

    stdout_log, stderr_log = process.communicate()

    if stdout_log != None:
        stdout_log = lines_tail(stdout_log.decode('utf-8'), log_line_limit)
    if stderr_log != None:
        stderr_log = lines_tail(stderr_log.decode('utf-8'), log_line_limit)

    worker_log = 'stdout:\n%s\n\nstderr:\n%s' % (stdout_log, stderr_log)

    if stdin_file != None:
        stdin.close()
    if stdout_file != None:
        stdout.close()
    if stderr_file != None:
        stderr.close()

    return worker_cleanup(command, process.returncode, worker_log)


def launch_container(docker, image, command):
    print('\n\033[1mStarting Docker Job\033[0m')

    local_command = build_localized_command(command)

    docker_command = dockerize_command(local_command)
    #print(docker_command)

    docker_cmd = build_bash_command(docker_command)
    docker_cmd = ' '.join(docker_cmd)
    print('\ndocker command:')
    print(docker_cmd)

    print('\nsetting up docker container:')
    docker_volume = '/'+local_files_dir
    binds = ['%s:%s' % (local_files_path, docker_volume)]
    print('volumn binding: %s' % binds[0])

    container = docker.create_container(image=image['RepoTags'][0], command=docker_cmd,
                                        volumes=[docker_volume],
                                        host_config=docker.create_host_config(binds=binds))

    print('start container')
    docker.start(container)
    exit_code = docker.wait(container)
    container_log = str(docker.logs(container, tail=log_line_limit),'utf-8')

    print('removing container: %s' % str(container))
    docker.remove_container(container)

    return worker_cleanup(command, exit_code, container_log)



if __name__ == '__main__':
    print(sys.argv[1])
    print(sys.argv[2])
    launch_container(sys.argv[1], sys.argv[2])
