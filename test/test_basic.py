import os, pytest, sys

sys.path.append('.')
import json
import mock
import launch as l
import utils
import worker
from argparse import ArgumentParser
from botocore.exceptions import ClientError
from collections import namedtuple
from docker.errors import ImageNotFound

class TestIO:
    def setup_method(self, _):
        self.uri = 's3://bucket/path/to/file.txt'
        self.local_file = '/bucket/path/to/file.txt'

    def test_get_local_path_s3(self):
        expected = l.LOCAL_FILES_PATH + self.local_file
        local_path = l.get_local_path(self.uri)
        assert(local_path == expected)

    def test_resolve_input_local(self):
        local_path = l.get_local_path(self.local_file)
        assert(local_path == self.local_file)

    def test_get_local_path_json(self):
        filename = '{"foo": "bar"}'
        json_input = l.get_local_path(filename)
        assert(json_input == filename)

    @mock.patch('boto3.resource')
    def test_s3_file_not_found(self, mock_resource):
        Obj = namedtuple('Obj', ['key'])
        key = 'path/to/file.txt'
        mock_resource.Bucket.return_value.objects.filter.return_value = [Obj(key=key)]
        side_effect = ClientError({'Error': {'Code': 404}}, 'download')
        mock_resource.Bucket.return_value.download_file.side_effect = side_effect
        with pytest.raises(ClientError):
            utils.get_s3_file(mock_resource, self.uri, self.local_file)

    @mock.patch('boto3.resource')
    def test_get_s3_file(self, mock_resource):
        Obj = namedtuple('Obj', ['key'])
        key = 'path/to/file.txt'
        mock_resource.Bucket.return_value.objects.filter.return_value = [Obj(key=key)]
        utils.get_s3_file(mock_resource, self.uri, self.local_file)
        mock_resource.Bucket.return_value.download_file.assert_called_with(key, self.local_file)

    @mock.patch('boto3.resource')
    @mock.patch('os.listdir')
    def test_put_file_s3(self, mock_listdir, mock_resource):
        Obj = namedtuple('Obj', ['key'])
        key = 'path/to/file.txt'
        mock_listdir.return_value = ['file.txt']
        mock_resource.Bucket.return_value.objects.filter.return_value = [Obj(key=key)]
        utils.put_file_s3(mock_resource, self.local_file, self.uri)
        mock_resource.Bucket.return_value.upload_file.assert_called_with(self.local_file, key)

    @mock.patch('boto3.resource')
    def test_get_s3_file_prefix(self, mock_resource):
        uri = os.path.splitext(self.uri)[0]
        local_file = os.path.splitext(self.local_file)[0]
        utils.get_s3_file(mock_resource, uri, local_file)
        mock_resource.Bucket.return_value.objects.filter.assert_called_with(Prefix='path/to/file')

    @mock.patch('boto3.resource')
    @mock.patch('os.listdir')
    def test_put_file_s3_prefix(self, mock_listdir, mock_resource):
        extensions = ['.txt', '.shp', '.dbf']
        mock_listdir.return_value = ['file{}'.format(ext) for ext in extensions]
        uri = os.path.splitext(self.uri)[0]
        local_file = os.path.splitext(self.local_file)[0]
        key = 'path/to/file'
        calls = [mock.call(local_file + ext, key + ext) for ext in extensions]
        utils.put_file_s3(mock_resource, local_file, uri)
        mock_resource.Bucket.return_value.upload_file.assert_has_calls(calls)

class TestUtils:
    @mock.patch('docker.DockerClient')
    def test_image_exists(self, mock_client):
        assert(utils.image_exists('test'))

    @mock.patch('docker.DockerClient')
    def test_image_exists_remote(self, mock_client):
        mock_client.return_value.images.get.side_effect = ImageNotFound('image not found')
        assert(utils.image_exists('test'))

    @mock.patch('docker.DockerClient')
    def test_image_exists_fail(self, mock_client):
        mock_client.return_value.images.get.side_effect = ImageNotFound('image not found')
        mock_client.return_value.images.pull.side_effect = ImageNotFound('image not found')
        assert(utils.image_exists('test') is False)

class TestCLI:
    def test_build_cli(self):
        parser = worker.build_cli_parser()
        args = parser.parse_args(['-pf', '5', 'docker'])
        assert(args.exec_type == 'docker')

    def test_missing_exec_type(self):
        parser = worker.build_cli_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(['-pf', '5'])

    def test_empty_args(self):
        parser = worker.build_cli_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])
