import os, pytest, sys

sys.path.append('.')
import botocore
import mock
import worker

docker_success = 'it worked!'

class TestWorker:
    def setup_method(self, _):
        self.msg_id = '1234'
        self.worker_id = 'worker'
        self.mock_docker_client = mock.Mock()
        #self.mock_image = mock.Mock()
        #self.mock_docker.images = lambda: [{'RepoTags':[self.worker_id+':latest']}]
        self.mock_db = mock.Mock()

    @mock.patch('worker.launch_container', return_value = docker_success)
    @mock.patch('worker.get_docker_image', return_value = mock.Mock())
    def test_valid_message(self, mock_container, mock_image):
        status, result = worker.process_message(self.mock_db, self.mock_docker_client, [], self.msg_id, '{"command":[]}', self.worker_id)
        assert(status == worker.STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch('worker.launch_container', return_value = docker_success)
    @mock.patch('worker.get_docker_image', return_value = mock.Mock())
    def test_valid_message_s3_stdin(self, mock_container, mock_image):
        status, result = worker.process_message(self.mock_db, self.mock_docker_client, [], self.msg_id, '{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}', self.worker_id)
        assert(status == worker.STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch('worker.launch_container', return_value = docker_success)
    @mock.patch('worker.get_docker_image', return_value = mock.Mock())
    def test_valid_message_s3_cmd(self, mock_container, mock_image):
        status, result = worker.process_message(self.mock_db, self.mock_docker_client, [], self.msg_id, '{"command":[{"type":"output", "value":"s3://lanlytics/path/to/input/test.geojson"}]}', self.worker_id)
        assert(status == worker.STATUS_COMPLETE)
        assert(result == docker_success)

    def test_invalid_json_message(self):
        status, result = worker.process_message(self.mock_db, self.mock_docker_client, [], self.msg_id, '{command:[]}', self.worker_id)
        assert(status == worker.STATUS_FAILED)
        assert('Expecting property name' in result)

    def test_invalid_schema_message(self):
        status, result = worker.process_message(self.mock_db, self.mock_docker_client, [], self.msg_id, '{"bloop":[]}', self.worker_id)
        assert(status == worker.STATUS_FAILED)
        assert('Failed validating' in result)

    @mock.patch('boto3.client')
    @mock.patch('local_launch.get_s3_file')
    @mock.patch('worker.launch_container', return_value = docker_success)
    @mock.patch('worker.get_docker_image', return_value = mock.Mock())
    def test_s3_file_not_found(self, mock_resource, mock_get_s3, mock_container, mock_image):
        error_response = {'Error': {'Code': 404}}
        mock_get_s3.side_effect = botocore.exceptions.ClientError(error_response, 'download')
        status, result = worker.process_message(self.mock_db, self.mock_docker_client, [], self.msg_id, '{"command":[{"type":"input", "value":"s3://lanlytics/path/to/input/test.txt"}]}', self.worker_id)
        assert(status == worker.STATUS_FAILED)
        assert('error occurred (404)' in result)

    ### Test Native CLI with
    # linux version
    # ./worker.py -pf 5 native native_tester '["java.exe", "-jar", "pw_test.jar"]'
    #
    # windows power shell version
    # ./worker.py -pf 5 native native_tester --% "[""java.exe"", ""-jar"", ""pw_test.jar""]"

