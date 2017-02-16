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

class MockMessage:
    def __init__(self, msg_id, service):
        self.message_attributes = MockAttributes(service)
        if msg_id == 1234:
            self.body = json.dumps(commands['basic_command'])
            self.message_id = msg_id
        elif msg_id == 'test_id':
            self.body = json.dumps(commands['full_command'])
            self.message_id = msg_id

    def delete(self):
        return

class MockAttributes:
    def __init__(self, service):
        self.service = service

    def get(self, service):
        if service == 'StringValue':
            return self.service
        else:
            return self

class TestWorker:
    def setup_method(self, _):
        self.message = {'id': '1234', 'service': 'worker'}
        self.mock_docker_client = mock.Mock()
        self.mock_db = mock.Mock()
        self.mock_db.get.return_value = b'{}'

    def mock_execute(self):
        return (STATUS_COMPLETE, docker_success)

    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    @mock.patch('boto3.resource')
    def test_valid_message(self, mock_resource):
        self.message['body'] = '{"command":[]}' 
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch('boto3.resource')
    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    def test_valid_message_s3_stdin(self, mock_resource):
        self.message['body'] = json.dumps(commands['std_command'])
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    @mock.patch('boto3.resource')
    def test_valid_message_s3_cmd(self, mock_resource):
        self.message['body'] = json.dumps(commands['full_command'])
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    @mock.patch('boto3.resource')
    def test_invalid_json_message(self, mock_resource):
        self.message['body'] = '{command:[]}'
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_FAIL)
        assert('Expecting property name' in result)

    def test_invalid_schema_message(self):
        self.message['body'] = json.dumps(commands['bad_command'])
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_FAIL)
        assert('Failed validating' in result)

    @mock.patch('boto3.resource')
    def test_receive_message(self, mock_resource):
        messages = [MockMessage(1234, 'foo'), MockMessage('test_id', 'test')]
        mock_resource.get_queue_by_name.return_value.receive_messages.return_value = messages
        message = utils.receive_message(mock_resource, 'test')
        assert(message['id'] == 'test_id')

    @mock.patch('boto3.resource')
    def test_active_check_message(self, mock_resource):
        self.message['body'] = json.dumps(commands['test_command'])
        status, result = worker.process_message(self.mock_db, 'native', [], self.message)
        assert(status == STATUS_ACTIVE)
        assert('Service is active' in result)

    @mock.patch('boto3.resource')
    @mock.patch('utils.image_exists', return_value=True)
    def test_active_check_docker_message(self, mock_image_exists, mock_resource):
        self.message['body'] = json.dumps(commands['test_command'])
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_ACTIVE)
        assert('Service is active' in result)

    @mock.patch('boto3.resource')
    @mock.patch('utils.image_exists', return_value=False)
    def test_active_check_fail_docker_message(self, mock_image_exists, mock_resource):
        self.message['body'] = json.dumps(commands['test_command'])
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_FAIL)
        assert('Image for worker not found' in result)

    @mock.patch('boto3.resource')
    @mock.patch.object(local_launch.Command, 'execute')
    def test_s3_file_not_found(self, mock_cmd, mock_resource):
        mock_cmd.side_effect = ClientError({'Error': {'Code': 404}}, 'download')
        self.message['body'] = json.dumps(commands['basic_command'])
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == STATUS_FAIL)
        assert('error occurred (404)' in result)

    ### Test Native CLI with
    # linux version
    # ./worker.py -pf 5 native native_tester '["java.exe", "-jar", "pw_test.jar"]'
    #
    # windows power shell version
    # ./worker.py -pf 5 native native_tester --% "[""java.exe"", ""-jar"", ""pw_test.jar""]"

