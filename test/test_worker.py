import os, pytest, sys

sys.path.append('.')
import json
import mock
import local_launch
import utils
import worker
from botocore.exceptions import ClientError
from docker.errors import ImageNotFound
from settings import *

docker_success = 'it worked!'

test_commands = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_commands.json')
with open(test_commands) as f:
    commands = json.load(f)

class TestWorker:
    def setup_method(self, _):
        self.message = {'job_id': '1234', 'service': 'worker'}
        self.mock_docker_client = mock.Mock()
        self.mock_db = mock.Mock()
        self.mock_db.get.return_value = b'{}'

    def mock_execute(self):
        return (STATUS_COMPLETE, docker_success)

    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    @mock.patch('boto3.resource')
    def test_valid_message(self, mock_resource):
        self.message['command'] = {'command':[]}
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch('boto3.resource')
    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    def test_valid_message_s3_stdin(self, mock_resource):
        self.message['command'] = commands['std_command']
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    @mock.patch('boto3.resource')
    def test_valid_message_s3_cmd(self, mock_resource):
        self.message['command'] = commands['full_command']
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_COMPLETE)
        assert(result == docker_success)

    def test_invalid_schema_message(self):
        self.message['command'] = commands['bad_command']
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_FAIL)
        assert('Failed validating' in result)

    def test_receive_message(self):
        self.mock_db.rpoplpush.return_value = b'{"job_id": "test_id"}' 
        message = utils.receive_message(self.mock_db, 'test')
        assert(message['job_id'] == 'test_id')

    @mock.patch('boto3.resource')
    def test_active_check_message(self, mock_resource):
        self.message['command'] = commands['test_command']
        status, result = worker.process_message(self.mock_db, 'native', [], self.message)
        assert(status == STATUS_ACTIVE)
        assert('Service is active' in result)

    @mock.patch('boto3.resource')
    @mock.patch('utils.image_exists', return_value=True)
    def test_active_check_docker_message(self, mock_image_exists, mock_resource):
        self.message['command'] = commands['test_command']
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_ACTIVE)
        assert('Service is active' in result)

    @mock.patch('boto3.resource')
    @mock.patch('utils.image_exists', return_value=False)
    def test_active_check_fail_docker_message(self, mock_image_exists, mock_resource):
        self.message['command'] = commands['test_command']
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_FAIL)
        assert('Image for worker not found' in result)

    @mock.patch('boto3.resource')
    @mock.patch.object(local_launch.Command, 'execute')
    def test_s3_file_not_found(self, mock_cmd, mock_resource):
        mock_cmd.side_effect = ClientError({'Error': {'Code': 404}}, 'download')
        self.message['command'] = commands['basic_command']
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_FAIL)
        assert('error occurred (404)' in result)

    ### Test Native CLI with
    # linux version
    # ./worker.py -pf 5 native native_tester '["java.exe", "-jar", "pw_test.jar"]'
    #
    # windows power shell version
    # ./worker.py -pf 5 native native_tester --% "[""java.exe"", ""-jar"", ""pw_test.jar""]"

