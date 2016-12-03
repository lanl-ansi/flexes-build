import os, pytest, sys

sys.path.append('.')
import mock
import worker

docker_success = 'it worked!'

class TestWorker:
    def setup_method(self, _):
        self.msg_id = '1234'
        self.worker_id = 'worker'
        self.mock_docker = mock.Mock()
        self.mock_docker.images = lambda: [{'RepoTags':[self.worker_id+':latest']}]
        self.mock_db = mock.Mock()

    @mock.patch('worker.launch_container', return_value = docker_success)
    def test_valid_message(self, mock_resource):
        status, result = worker.process_message(self.mock_docker, self.mock_db, self.msg_id, '{"command":[]}', self.worker_id)
        assert(status == worker.STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch('worker.launch_container', return_value = docker_success)
    def test_valid_message_s3(self, mock_resource):
        status, result = worker.process_message(self.mock_docker, self.mock_db, self.msg_id, '{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}', self.worker_id)
        assert(status == worker.STATUS_COMPLETE)
        assert(result == docker_success)

    @mock.patch('worker.launch_container', return_value = docker_success)
    def test_valid_message_s3_cmd(self, mock_resource):
        status, result = worker.process_message(self.mock_docker, self.mock_db, self.msg_id, '{"command":[{"type":"parameter", "value":"s3://lanlytics/path/to/input/test.geojson"}]}', self.worker_id)
        assert(status == worker.STATUS_COMPLETE)
        assert(result == docker_success)

    def test_invalid_json_message(self):
        status, result = worker.process_message(self.mock_docker, self.mock_db, self.msg_id, '{command:[]}', self.worker_id)
        assert(status == worker.STATUS_FAILED)
        assert('Expecting property name' in result)

    def test_invalid_schema_message_1(self):
        status, result = worker.process_message(self.mock_docker, self.mock_db, self.msg_id, '{"bloop":[]}', self.worker_id)
        assert(status == worker.STATUS_FAILED)
        assert('Failed validating' in result)
