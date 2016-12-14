import boto3
import json
import os
import sys
import time
import copy
import shutil

from subprocess import Popen, PIPE

if 'HOME' in os.environ:
    home = os.environ['HOME']
else:
    home = os.sep

local_files_dir = 'lanlytics_worker_local'+os.sep+str(os.getpid())
local_files_path = home+os.sep+local_files_dir


def is_s3_uri(string):
    #TODO make this a robust?
    return string.startswith('s3://')


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


def build_command(local_command):
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


def build_localized_command(command):
    abstract_cmd = build_command(command)
    print('\nabstract command:')
    print(' '.join(abstract_cmd)+'\n')

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

    return feedback


def launch_native(command):
    print('\n\033[1mStarting Native Job\033[0m')

    local_command = build_localized_command(command)

    native_cmd = build_command(local_command)
    #native_cmd = ' '.join(native_cmd)

    print('\nnative command:')
    print(native_cmd)

    # shell parameter used for windows support
    process = Popen(native_cmd, stdout=PIPE, stderr=PIPE, shell = (os.name == 'nt'))
    stdout, stderr = process.communicate()
    worker_log = 'stdout:\n\n%s\nstderr:\n\n%s' % (stdout, stderr)

    return worker_cleanup(command, process.returncode, worker_log)


def launch_container(docker, image, command):
    print('\n\033[1mStarting Docker Job\033[0m')

    local_command = build_localized_command(command)

    docker_command = dockerize_command(local_command)
    #print(docker_command)

    docker_cmd = build_command(docker_command)
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
    container_log = str(docker.logs(container, tail=10),'utf-8')

    print('removing container: %s' % str(container))
    docker.remove_container(container)

    return worker_cleanup(command, exit_code, container_log)



if __name__ == '__main__':
    print(sys.argv[1])
    print(sys.argv[2])
    launch_container(sys.argv[1], sys.argv[2])
