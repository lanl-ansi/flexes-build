import os, pytest, sys

sys.path.append('.')
import mock
from docker_worker import DockerWorker
from config import load_config
from docker.errors import ContainerError, ImageNotFound
from test_common import test_commands

SUCCESS = 'It worked!'
config = load_config()

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
        assert(status == config['STATUS_COMPLETE'])
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
        self.worker.client.containers.run.return_value.logs.return_value = b''
        type(self.worker.client.containers.run.return_value).status = mock.PropertyMock(side_effect=['running', 'running', 'exited'])
        message = test_commands['pipe_command']
        status, feedback, stdout_data, stderr_data = self.worker.launch(message)
        assert(status == config['STATUS_COMPLETE'])
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
        assert(status == config['STATUS_FAIL'])
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

    def test_active_check_docker_message(self):
        self.worker.image_exists = mock.MagicMock(return_value=True)
        message = test_commands['test_command']
        message['job_id'] = '1234'
        status, result = self.worker.process_message(message)
        assert(status == config['STATUS_ACTIVE'])
        assert('Service is active' in result)

    def test_active_check_fail_docker_message(self):
        self.worker.image_exists = mock.MagicMock(return_value=False)
        message = test_commands['test_command']
        message['job_id'] = '1234'
        status, result = self.worker.process_message(message)
        assert(status == config['STATUS_FAIL'])
        assert('Image test not found' in result)

    def test_image_exists(self):
        assert(self.worker.image_exists('test'))

    def test_image_exists_remote(self):
        self.worker.client.images.get.side_effect = ImageNotFound('image not found')
        assert(self.worker.image_exists('test'))

    def test_image_exists_fail(self):
        self.worker.client.images.get.side_effect = ImageNotFound('image not found')
        self.worker.client.images.pull.side_effect = ImageNotFound('image not found')
        assert(self.worker.image_exists('test') is False)

    def test_registry_auth(self):
        self.worker.config['AUTHENTICATE'] = {'REGISTRY_USERNAME': 'user', 'REGISTRY_PASSWORD': 'password'}
        self.worker.registry_login()


