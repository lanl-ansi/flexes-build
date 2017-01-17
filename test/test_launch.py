import os, pytest, sys

sys.path.append('.')

import docker
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

    @mock.patch('local_launch.launch_container')
    @mock.patch('docker.DockerClient', autospec=True)
    def test_execute_docker(self, mock_client, mock_launch_container):
        message = {'service': 'test', 'id': '1234',
                    'body': '{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}'}
        cmd = l.Command('docker', message, [])
        cmd.execute()
        assert(mock_client.called)
        assert(mock_launch_container.called)

    @mock.patch('local_launch.launch_native')
    def test_execute_native(self, mock_launch_native):
        message = {'service': 'test', 'id': '1234',
                    'body': '{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}'}
        cmd = l.Command('native', message, [])
        cmd.execute()
        assert(mock_launch_native.called)


class TestLaunch:
    @mock.patch('boto3.resource')
    @mock.patch('shutil.rmtree')
    @mock.patch('docker.DockerClient', autospec=True)
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('local_launch.localize_resource', 
                return_value='/path/to/resource.txt')
    def test_launch_container(self, mock_localize_resource, 
                              mock_makedirs, mock_client,
                              mock_rmtree, mock_resource):
        mock_client.return_value.containers.return_value.run.return_value = str.encode('logs')
        command = json.loads('{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}')
        result = l.launch_container(mock_client, 'test', command)
        assert(mock_rmtree.called)

    @mock.patch('boto3.resource')
    @mock.patch('shutil.rmtree')
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('local_launch.localize_resource', 
                return_value='test/data/test.txt')
    @mock.patch('subprocess.Popen', autospec=True)
    def test_launch_native(self, mock_subprocess, mock_localize_resource, 
                           mock_makedirs, mock_rmtree, mock_resource):
        mock_subprocess.return_value.communicate.return_value = (b'test', b'test')
        mock_subprocess.return_value.returncode = 0
        command = json.loads('{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}')
        result = l.launch_native(['python', 'test.py'], command)
        assert(mock_rmtree.called)
