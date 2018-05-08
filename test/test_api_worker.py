import os, pytest, sys

sys.path.append('.')
import json
import mock
import utils
from api_worker import APIWorker
from argparse import ArgumentParser
from botocore.exceptions import ClientError
from collections import namedtuple
from docker.errors import ImageNotFound
from settings import *
from test_common import test_commands

SUCCESS = 'It worked!'

class TestMessage:
    @mock.patch('api_worker.StrictRedis')
    @mock.patch('boto3.resource')
    def setup_method(self, _, mock_redis, mock_resource):
        self.message = {'job_id': '1234', 'service': 'worker'}
        self.worker = APIWorker(queue='test', poll_frequency=1)
        self.worker.launch = mock.MagicMock(return_value=(STATUS_COMPLETE, SUCCESS, None, None))

    def test_valid_message(self):
        self.message['command'] = {'arguments': []}
        status, result = self.worker.process_message(self.message)
        assert(status == STATUS_COMPLETE)
        assert(result == SUCCESS)

    def test_valid_message_s3_stdin(self):
        self.message['command'] = test_commands['std_command']['command']
        status, result = self.worker.process_message(self.message)
        assert(status == STATUS_COMPLETE)
        assert(result == SUCCESS)

    def test_valid_message_s3_cmd(self):
        self.message['command'] = test_commands['full_command']['command']
        status, result = self.worker.process_message(self.message)
        assert(status == STATUS_COMPLETE)
        assert(result == SUCCESS)

    def test_invalid_schema_message(self):
        self.message['command'] = test_commands['bad_command']
        status, result = self.worker.process_message(self.message)
        assert(status == STATUS_FAIL)
        assert('Failed validating' in result)

    def test_active_check_message(self):
        self.message['test'] = True
        status, result = self.worker.process_message(self.message)
        assert(status == STATUS_ACTIVE)
        assert('Service is active' in result)

    def test_s3_file_not_found(self):
        self.worker.launch.side_effect = ClientError({'Error': {'Code': 404}}, 'download')
        self.message['command'] = test_commands['basic_command']['command']
        status, result = self.worker.process_message(self.message)
        assert(status == STATUS_FAIL)
        assert('error occurred (404)' in result)

class TestLocalize:
    @mock.patch('api_worker.StrictRedis')
    @mock.patch('boto3.resource')
    def setup_method(self, _, mock_redis, mock_resource):
        self.message = {'job_id': '1234', 'service': 'worker'}
        self.worker = APIWorker(queue='test', poll_frequency=1)
        self.worker.launch = mock.MagicMock(return_value=(STATUS_COMPLETE, SUCCESS, None, None))
        self.uri = 's3://lanlytics/path/to/input/test.txt'

    def test_get_local_path(self):
        uri = self.worker.get_local_path(self.uri)
        assert(isinstance(uri, str))

    @mock.patch('os.makedirs', return_value=None)
    def test_make_local_dirs(self, mock_makedirs):
        self.worker.make_local_dirs('/path/to/resource.txt')
        mock_makedirs.assert_called()

class TestCommands:
    @mock.patch('api_worker.StrictRedis')
    @mock.patch('boto3.resource')
    def setup_method(self, _, mock_redis, mock_resource):
        self.message = {'job_id': '1234', 'service': 'worker'}
        self.worker = APIWorker(queue='test', poll_frequency=1)
        self.worker.launch = mock.MagicMock(return_value=(STATUS_COMPLETE, SUCCESS, None, None))

    @mock.patch('utils.get_s3_file')
    @mock.patch('os.makedirs', return_value=None)
    def test_build_localized_command(self, mock_makedirs, mock_get_s3):
        command = test_commands['input_command']['command']
        local_command = self.worker.build_localized_command(command)
        assert(mock_get_s3.call_count == 2)

    @mock.patch('utils.put_file_s3')
    @mock.patch('shutil.rmtree')
    def test_worker_cleanup(self, mock_rmtree, mock_put_s3):
        command = test_commands['output_command']['command']
        status, feedback, stdout_data, stderr_data = self.worker.worker_cleanup(command, 0, 'worker log', None, None)
        assert(mock_put_s3.call_count == 2)

    def test_build_bash_command(self):
        command = test_commands['basic_command']['command']
        expected = ['s3://bucket/path/to/input.txt', 
                    '--arg1 arg_val', 
                    '--output s3://bucket/path/to/output.txt']
        bash_command = self.worker.build_bash_command(command)
        assert(bash_command == expected)
        
    @mock.patch('os.makedirs', return_value=None)
    def test_localize_command(self, mock_makedirs):
        self.worker.localize_resource = mock.MagicMock(return_value='/path/to/resource.txt')
        command = test_commands['std_command']['command'] 
        local_command = self.worker.localize_command(command)
        assert(isinstance(local_command, dict))

class TestIO:
    @mock.patch('api_worker.StrictRedis')
    @mock.patch('boto3.resource')
    def setup_method(self, _, mock_redis, mock_resource):
        self.uri = 's3://bucket/path/to/file.txt'
        self.local_file = '/bucket/path/to/file.txt'
        self.message = {'job_id': '1234', 'service': 'worker'}
        self.worker = APIWorker(queue='test', poll_frequency=1)
        self.worker.launch = mock.MagicMock(return_value=(STATUS_COMPLETE, SUCCESS, None, None))

    def test_get_local_path_s3(self):
        expected = self.worker.local_files_path + self.local_file
        local_path = self.worker.get_local_path(self.uri)
        assert(local_path == expected)

    def test_resolve_input_local(self):
        local_path = self.worker.get_local_path(self.local_file)
        assert(local_path == self.local_file)

    def test_get_local_path_json(self):
        filename = '{"foo": "bar"}'
        json_input = self.worker.get_local_path(filename)
        assert(json_input == filename)

    def test_s3_file_not_found(self):
        self.worker.s3.Bucket.return_value.objects.filter.return_value = []
        with pytest.raises(ValueError):
            utils.get_s3_file(self.worker.s3, self.uri, self.local_file)

    def test_get_s3_file(self):
        Obj = namedtuple('Obj', ['key'])
        key = 'path/to/file.txt'
        self.worker.s3.Bucket.return_value.objects.filter.return_value = [Obj(key=key)]
        utils.get_s3_file(self.worker.s3, self.uri, self.local_file)
        self.worker.s3.Bucket.return_value.download_file.assert_called_with(key, self.local_file)

    @mock.patch('os.listdir')
    def test_put_file_s3(self, mock_listdir):
        Obj = namedtuple('Obj', ['key'])
        key = 'path/to/file.txt'
        mock_listdir.return_value = ['file.txt']
        self.worker.s3.Bucket.return_value.objects.filter.return_value = [Obj(key=key)]
        utils.put_file_s3(self.worker.s3, self.local_file, self.uri)
        self.worker.s3.Bucket.return_value.upload_file.assert_called_with(self.local_file, key)

    def test_get_s3_file_prefix(self):
        Obj = namedtuple('Obj', ['key'])
        uri = os.path.splitext(self.uri)[0]
        key = 'path/to/file.txt'
        self.worker.s3.Bucket.return_value.objects.filter.return_value = [Obj(key=key)]
        local_file = os.path.splitext(self.local_file)[0]
        utils.get_s3_file(self.worker.s3, uri, local_file)
        self.worker.s3.Bucket.return_value.objects.filter.assert_called_with(Prefix='path/to/file')

    @mock.patch('os.listdir')
    def test_put_file_s3_prefix(self, mock_listdir):
        extensions = ['.txt', '.shp', '.dbf']
        mock_listdir.return_value = ['file{}'.format(ext) for ext in extensions]
        uri = os.path.splitext(self.uri)[0]
        local_file = os.path.splitext(self.local_file)[0]
        key = 'path/to/file'
        calls = [mock.call(local_file + ext, key + ext) for ext in extensions]
        utils.put_file_s3(self.worker.s3, local_file, uri)
        self.worker.s3.Bucket.return_value.upload_file.assert_has_calls(calls)

class TestModifyJob:
    @mock.patch('api_worker.StrictRedis')
    @mock.patch('boto3.resource')
    def setup_method(self, _, mock_redis, mock_resource):
        self.uri = 's3://bucket/path/to/file.txt'
        self.local_file = '/bucket/path/to/file.txt'
        self.message = {'job_id': '1234', 'service': 'worker'}
        self.worker = APIWorker(queue='test', poll_frequency=1)
        self.worker.launch = mock.MagicMock(return_value=(STATUS_COMPLETE, SUCCESS, None, None))

    def test_update_job(self):
        self.worker.db.get.return_value = b'{"foo":"bar"}'
        status, result = self.worker.update_job('test1234', 'testing')
        assert(status == 'testing')

