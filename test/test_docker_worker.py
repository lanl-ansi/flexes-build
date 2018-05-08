import os, pytest, sys

sys.path.append('.')
import json
import mock
import utils
from docker_worker import DockerWorker
from argparse import ArgumentParser
from botocore.exceptions import ClientError
from collections import namedtuple
from docker.errors import ContainerError, ImageNotFound
from settings import *
from test_common import test_commands

SUCCESS = 'It worked!'

class TestDockerWorker:
    @mock.patch('docker.DockerClient', autospec=True)
    @mock.patch('api_worker.StrictRedis')
    @mock.patch('boto3.resource')
    def setup_method(self, _, mock_resource, mock_redis, mock_client):
        self.message = {'job_id': '1234', 'service': 'worker'}
        self.worker = DockerWorker(queue='test', poll_frequency=1)

    @mock.patch('shutil.rmtree')
    @mock.patch('os.makedirs', return_value=None)
    def test_launch_container(self, mock_makedirs, mock_rmtree):
        self.worker.localize_resource = mock.MagicMock(return_value='/path/to/resource.txt')
        self.worker.persist_command = mock.MagicMock()
        self.worker.client.containers.run.return_value.wait.return_value = {'Error': None, 'StatusCode': 0}
        type(self.worker.client.containers.run.return_value).status = mock.PropertyMock(side_effect=['running', 'running', 'exited'])
        message = test_commands['basic_command']
        status, feedback, stdout_data, stderr_data = self.worker.launch(message)
        assert(status == 'complete')
        assert(stdout_data == None)
        assert(stderr_data == None)
        assert(mock_rmtree.called)

    @mock.patch('shutil.rmtree')
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_launch_container_pipe(self, mock_open, mock_makedirs, mock_rmtree):
        self.worker.localize_resource = mock.MagicMock(return_value='/path/to/resource.txt')
        self.worker.persist_command = mock.MagicMock()
        self.worker.client.containers.run.return_value.wait.return_value = {'Error': None, 'StatusCode': 0}
        type(self.worker.client.containers.run.return_value).status = mock.PropertyMock(side_effect=['running', 'running', 'exited'])
        message = test_commands['pipe_command']
        status, feedback, stdout_data, stderr_data = self.worker.launch(message)
        assert(status == 'complete')
        assert(stdout_data == '')
        assert(stderr_data == None)

    @mock.patch('shutil.rmtree')
    @mock.patch('os.makedirs', return_value=None)
    def test_launch_container_fail(self, mock_makedirs, mock_rmtree):
        expected = 'Job finished with exit code -1\nContainer execution failed' 
        self.worker.localize_resource = mock.MagicMock(return_value='/path/to/resource.txt')
        self.worker.client.containers.run.side_effect = ContainerError('error', -1, 'test', 'test', b'Container execution failed')
        message = test_commands['basic_command']
        status, result, stdout_data, stderr_data = self.worker.launch(message)
        assert(status == 'failed')
        assert(result == expected) 

    @mock.patch('shutil.rmtree')
    @mock.patch('os.makedirs', return_value=None)
    def test_launch_container_notfound(self, mock_makedirs, mock_rmtree):
        expected = 'Job finished with exit code -1\nImage not found' 
        self.worker.localize_resource = mock.MagicMock(return_value='/path/to/resource.txt')
        self.worker.client.containers.run.side_effect = ImageNotFound('Image not found')
        message = test_commands['basic_command']
        status, result, stdout_data, stderr_data = self.worker.launch(message)
        assert(status == 'failed')
        assert(result == expected) 

    @mock.patch('utils.image_exists', return_value=True)
    def test_active_check_docker_message(self, mock_image_exists):
        message = test_commands['test_command']
        message['job_id'] = '1234'
        status, result = self.worker.process_message(message)
        assert(status == STATUS_ACTIVE)
        assert('Service is active' in result)

    @mock.patch('utils.image_exists', return_value=False)
    def test_active_check_fail_docker_message(self, mock_image_exists):
        message = test_commands['test_command']
        message['job_id'] = '1234'
        status, result = self.worker.process_message(message)
        assert(status == STATUS_FAIL)
        assert('Image test not found' in result)

