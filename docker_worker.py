import copy
import docker
import os
import sys
import time
import utils
from api_worker import APIWorker
from argparse import ArgumentParser
from pathlib import Path

class DockerWorker(APIWorker):
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.client = docker.DockerClient(base_url='unix://var/run/docker.sock', version='auto')
        self.local_files_dir = Path(self.local_files_path).anchor + str(Path(self.local_files_path).relative_to(Path.home()))

    def test_service(self, message):
        message['tag'] = message.get('tag', 'latest')
        if self.image_exists(message['service'], message['tag']):
            print('Confirmed active status for {}'.format(message['service']))
            return self.update_job(message['job_id'], self.config['STATUS_ACTIVE'], 'Service is active')
        else:
            print('Image {} not found'.format(message['service']))
            return self.update_job(message['job_id'], self.config['STATUS_FAIL'], 
                                   'Image {} not found'.format(message['service']))

    def image_exists(self, image_name, tag='latest'):
        image = '{}/{}:{}'.format(self.config['DOCKER_REGISTRY'], image_name, tag)
        try:
            image = self.client.images.get(image)
            return True
        except docker.errors.ImageNotFound:
            try:
                print('Image {} not found locally'.format(image))
                self.client.images.pull(image)
                return True
            except docker.errors.ImageNotFound:
                return False

    def get_docker_path(self, uri):
        path = self.get_local_path(uri)
        if path.startswith(self.local_files_path):
            return Path(path).anchor + str(Path(path).relative_to(Path.home()))
        else:
            return path

    def dockerize_command(self, local_command):
        docker_command = copy.deepcopy(local_command)
        if 'stdin' in docker_command and docker_command['stdin']['type'] == 'uri':
            docker_command['stdin']['value'] = self.get_docker_path(docker_command['stdin']['value'])
        if 'stdout' in docker_command and docker_command['stdout']['type'] == 'uri':
            docker_command['stdout']['value'] = self.get_docker_path(docker_command['stdout']['value'])
        if 'stderr' in docker_command and docker_command['stderr']['type'] == 'uri':
            docker_command['stderr']['value'] = self.get_docker_path(docker_command['stderr']['value'])
        for arg in docker_command['arguments']:
            if arg['type'] == 'input':
                arg['value'] = self.get_docker_path(arg['value'])
            if arg['type'] == 'output':
                arg['value'] = self.get_docker_path(arg['value'])
        return docker_command

    def launch(self, message):
        print('\n\033[1mStarting Docker Job\033[0m')

        tag = message.get('tag', 'latest')
        image = '{}/{}:{}'.format(self.config['DOCKER_REGISTRY'], message['service'], tag)
        print('\nDocker Image: {}'.format(image))

        local_command = self.build_localized_command(message['command'])
        local_cmd, stdin_file, stdin_pipe, stdout_file, stdout_pipe, stderr_file, stderr_pipe = self.build_command_parts(local_command)

        docker_command = self.dockerize_command(local_command)
        docker_cmd, *docker_other = self.build_command_parts(docker_command)

        stdin_data = None
        if stdin_file is not None:
            if stdin_pipe:
                stdin_data = stdin_file
            else:
                with open(stdin_file, 'r') as stdin:
                    stdin_data = stdin.read()

        docker_cmd = ' '.join(docker_cmd)
        print('\nDocker command: {}'.format(docker_cmd))

        print('\nSetting up docker container')
        
        environment = {'API_ENDPOINT': self.config['API_ENDPOINT'], 
                       'WORKER_BUCKET': self.config['WORKER_BUCKET']}

        docker_volume = self.local_files_dir
        volumes = {self.local_files_path: {'bind': docker_volume, 'mode': 'rw'}}
        print(volumes)

        container = None
        try:
            self.client.images.pull(image)
            container = self.client.containers.run(image, 
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

            messages = []
            while container.status != 'exited':
                tail = [line.strip().decode() for line in container.logs(stream=True, stdout=False, stderr=True, tail=5)]
                if tail != messages and len(tail) > 0:
                    messages = tail
                    self.update_job_messages(self.db, message['job_id'], messages)
                # Report container stats???
                stats = container.stats(decode=True)
                time.sleep(0.1)
                container.reload()
            exit_code = container.wait()['StatusCode']

            logs = container.logs(stdout=True, stderr=True).decode()
            stdout_lines = [line.strip().decode() for line in container.logs(stream=True, stdout=True, stderr=False)]
            stderr_lines = [line.strip().decode() for line in container.logs(stream=True, stdout=False, stderr=True)]
            if stdout_file != None:
                with open(stdout_file, 'w') as stdout:
                    stdout.writelines(stdout_lines)
            if stderr_file != None:
                with open(stderr_file, 'w') as stderr:
                    stderr.writelines(stderr_lines)
            stdout_data = '\n'.join(stdout_lines) if stdout_pipe else None
            stderr_data = '\n'.join(stderr_lines) if stderr_pipe else None 
        except docker.errors.ContainerError as e:
            print('Container error: {}'.format(e))
            logs = e.stderr.decode()
            exit_code = e.exit_status
            stdout_data = stderr_data = None
        except docker.errors.ImageNotFound as e:
            print('{} not found'.format(image))
            logs = 'Image not found'
            exit_code = -1
            stdout_data = stderr_data = None
        finally:
            if container:
                container.remove()
        return self.worker_cleanup(message['command'], exit_code, logs, stdout_data, stderr_data)

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-q', '--queue', default='docker', 
                        help='queue for the worker to pull work from')
    parser.add_argument('-pf', '--poll_frequency', default=1, type=int, 
                        help='time to wait between polling the work queue (seconds)')
    args = parser.parse_args()
    worker = DockerWorker(queue=args.queue, poll_frequency=args.poll_frequency)
    worker.run()
