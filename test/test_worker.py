import os, pytest, sys

sys.path.append('.')
import botocore
import mock
import worker
import utils

docker_success = 'it worked!'

class TestWorker:
    def setup_method(self, _):
        self.message = {'id': '1234', 'service': 'worker'}
        self.mock_docker_client = mock.Mock()
        self.mock_db = mock.Mock()

    @mock.patch('worker.Command', 'execute', return_value=docker_success)
    def test_valid_message(self, mock_command):
        mock_command.return_value.execute.return_value = docker_success
        self.message['body'] = '{"command":[]}' 
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == worker.STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch('worker.Command', 'execute', return_value=docker_success)
    def test_valid_message_s3_stdin(self, mock_command):
        self.message['body'] = '{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}' 
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == worker.STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch('worker.Command', 'execute', return_value=docker_success)
    def test_valid_message_s3_cmd(self, mock_command):
        mock_command.return_value.execute.return_value = docker_success
        self.message['body'] = '{"command":[{"type":"output", "value":"s3://lanlytics/path/to/input/test.geojson"}]}' 
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == worker.STATUS_COMPLETE)
        assert(result == docker_success)

    def test_invalid_json_message(self):
        self.message['body'] = '{"command":[]}' 
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == worker.STATUS_FAILED)
        assert('Expecting property name' in result)

    def test_invalid_schema_message(self):
        self.message['body'] = '{"bloop":[]}'
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == worker.STATUS_FAILED)
        assert('Failed validating' in result)

    @mock.patch('boto3.client')
    @mock.patch('worker.Command', 'execute')
    def test_s3_file_not_found(self, mock_resource, mock_command):
        error_response = {'Error': {'Code': 404}}
        mock_command.side_effect = botocore.exceptions.ClientError(error_response, 'download')
        self.message['body'] = '{"command":[{"type":"input", "value":"s3://lanlytics/path/to/input/test.txt"}]}'
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == worker.STATUS_FAILED)
        assert('error occurred (404)' in result)

    ### Test Native CLI with
    # linux version
    # ./worker.py -pf 5 native native_tester '["java.exe", "-jar", "pw_test.jar"]'
    #
    # windows power shell version
    # ./worker.py -pf 5 native native_tester --% "[""java.exe"", ""-jar"", ""pw_test.jar""]"

