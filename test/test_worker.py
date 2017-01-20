import os, pytest, sys

sys.path.append('.')
import botocore
import json
import mock

import local_launch
import utils
import worker

docker_success = 'it worked!'

class TestWorker:
    def setup_method(self, _):
        self.message = {'id': '1234', 'service': 'worker'}
        self.mock_docker_client = mock.Mock()
        self.mock_db = mock.Mock()

    def mock_execute(self):
        return ('complete', docker_success)

    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    def test_valid_message(self):
        self.message['body'] = '{"command":[]}' 
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == 'complete')
        assert(result == docker_success)

    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    def test_valid_message_s3_stdin(self):
        self.message['body'] = '{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}'
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == 'complete')
        assert(result == docker_success)

    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    def test_valid_message_s3_cmd(self):
        self.message['body'] = '{"command":[{"type":"output", "value":"s3://lanlytics/path/to/input/test.geojson"}]}'
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == 'complete')
        assert(result == docker_success)

    @mock.patch.object(local_launch.Command, 'execute', mock_execute)
    def test_invalid_json_message(self):
        self.message['body'] = '{command:[]}'
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == 'failed')
        assert('Expecting property name' in result)

    def test_invalid_schema_message(self):
        self.message['body'] = '{"bloop":[]}'
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == 'failed')
        assert('Failed validating' in result)

    @mock.patch('boto3.client')
    @mock.patch.object(local_launch.Command, 'execute', side_effect=botocore.exceptions.ClientError({'Error': {'Code': 404}}, 'download'))
    def test_s3_file_not_found(self, mock_resource, mock_cmd):
        self.message['body'] = '{"command":[{"type":"input", "value":"s3://lanlytics/path/to/input/test.txt"}]}'
        status, result = worker.process_message(self.mock_db, 'docker', [], self.message)
        assert(status == 'failed')
        assert('error occurred (404)' in result)

    ### Test Native CLI with
    # linux version
    # ./worker.py -pf 5 native native_tester '["java.exe", "-jar", "pw_test.jar"]'
    #
    # windows power shell version
    # ./worker.py -pf 5 native native_tester --% "[""java.exe"", ""-jar"", ""pw_test.jar""]"

