import os, pytest, sys

sys.path.append('.')

import docker
import json
import mock

import local_launch as l

test_commands = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_commands.json')
with open(test_commands) as f:
    commands = json.load(f)

class TestLocalize:
    def setup_method(self, _):
        self.uri = 's3://lanlytics/path/to/input/test.geojson'

    def test_get_local_path(self):
        uri = l.get_local_path(self.uri)
        assert(isinstance(uri, str))

    @mock.patch('os.makedirs', return_value=None)
    def test_make_local_dirs(self, mock_makedirs):
        l.make_local_dirs('/path/to/resource.txt')
        mock_makedirs.assert_called()


class TestCommands:
    @mock.patch('boto3.resource')
    @mock.patch('utils.get_s3_file')
    @mock.patch('os.makedirs', return_value=None)
    def test_build_localized_command(self, mock_makedirs, mock_get_s3, mock_resource):
        command = commands['input_command']
        local_command = l.build_localized_command(command)
        assert(mock_get_s3.call_count == 2)

    @mock.patch('boto3.resource')
    @mock.patch('utils.put_file_s3')
    @mock.patch('shutil.rmtree')
    def test_worker_cleanup(self, mock_rmtree, mock_put_s3, mock_resource):
        command = commands['output_command']
        status, feedback = l.worker_cleanup(command, 0, 'worker log')
        assert(mock_put_s3.call_count == 2)

    def test_build_bash_command(self):
        command = json.loads('{"command":[{"type":"input","value":"/path/to/input.txt"}, \
                                           {"type":"parameter","name":"-p","value":"foo"}]}')
        expected = ['/path/to/input.txt', '-p foo']
        bash_command = l.build_bash_command(command)
        assert(bash_command == expected)
        
    @mock.patch('local_launch.localize_resource', return_value='/path/to/resource.txt')
    @mock.patch('os.makedirs', return_value=None)
    def test_localize_command(self, mock_localize_resource, mock_makedirs):
        command = json.loads('{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}')
        local_command = l.localize_command(command)
        assert(isinstance(local_command, dict))

    @mock.patch('local_launch.launch_container')
    def test_execute_docker(self, mock_launch_container):
        message = {'service': 'test', 'id': '1234',
                    'body': '{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}'}
        cmd = l.Command('docker', message, [])
        cmd.execute()
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
        mock_client.return_value.containers.run.return_value = str.encode('logs')
        command = json.loads('{"stdin":"s3://lanlytics/path/to/input/test.geojson", "command":[]}')
        result = l.launch_container('test', command)
        assert(mock_rmtree.called)

    @mock.patch('boto3.resource')
    @mock.patch('shutil.rmtree')
    @mock.patch('docker.DockerClient', autospec=True)
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('local_launch.localize_resource', 
                return_value='/path/to/resource.txt')
    def test_launch_container_fail(self, mock_localize_resource, 
                                   mock_makedirs, mock_client,
                                   mock_rmtree, mock_resource):
        expected = 'Job finished with exit code: -1\nContainer execution failed' 
        mock_client.return_value.containers.run.side_effect = docker.errors.ContainerError('error', -1, 'test', 'test', b'Container execution failed')
        command = json.loads('{"stdout":"s3://lanlytics/path/to/input/test.geojson", "command":[]}')
        status, result = l.launch_container('test', command)
        assert(status == 'failed')
        assert(result == expected) 

    @mock.patch('boto3.resource')
    @mock.patch('shutil.rmtree')
    @mock.patch('docker.DockerClient', autospec=True)
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('local_launch.localize_resource', 
                return_value='/path/to/resource.txt')
    def test_launch_container_notfound(self, mock_localize_resource, 
                                   mock_makedirs, mock_client,
                                   mock_rmtree, mock_resource):
        expected = 'Job finished with exit code: -1\nImage not found' 
        mock_client.return_value.containers.run.side_effect = docker.errors.ImageNotFound('Image not found')
        command = json.loads('{"stdout":"s3://lanlytics/path/to/input/test.geojson", "command":[]}')
        status, result = l.launch_container('test', command)
        assert(status == 'failed')
        assert(result == expected) 

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
        status, result = l.launch_native(['python', 'test.py'], command)
        assert(mock_rmtree.called)
