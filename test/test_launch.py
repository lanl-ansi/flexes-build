import os, pytest, sys

sys.path.append('.')

import json
import mock

import local_launch as l

class TestLocalize:
    def setup_method(self, _):
        self.uri = 's3://lanlytics/path/to/input/test.geojson'

    def test_get_local_path(self):
        uri = l.get_local_path(self.uri)
        assert(isinstance(uri, str))

    @mock.patch('os.makedirs', return_value=None)
    def test_make_local_dirs(self, mock_makedirs):
        l.make_local_dirs('/path/to/resource.txt')
        assert(mock_makedirs.called)


class TestCommands:
    @mock.patch('local_launch.localize_resource', return_value='/path/to/resource.txt')
    @mock.patch('os.makedirs', return_value=None)
    def test_localize_command(self, mock_localize_resource, mock_makedirs):
        command = json.loads('{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}')
        local_command = l.localize_command(command)
        assert(isinstance(local_command, dict))


class TestLaunch:
    @mock.patch('docker.Client', autospec=True)
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('local_launch.localize_resource', return_value='/path/to/resource.txt')
    def test_launch_container(self, mock_client, mock_makedirs, mock_localize_resource):
        command = json.loads('{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}')
        result = l.launch_container('test', command)
        print(result)
        assert(True==False)

