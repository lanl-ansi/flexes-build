import os, pytest, sys

sys.path.append('.')

import docker
import json
import mock

import local_launch as l

from test_common import test_commands


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
        command = test_commands['input_command']
        local_command = l.build_localized_command(command)
        assert(mock_get_s3.call_count == 2)

    @mock.patch('boto3.resource')
    @mock.patch('utils.put_file_s3')
    @mock.patch('shutil.rmtree')
    def test_worker_cleanup(self, mock_rmtree, mock_put_s3, mock_resource):
        command = test_commands['output_command']
        status, feedback, stdout_data, stderr_data = l.worker_cleanup(command, 0, 'worker log', None, None)
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
        command = json.loads('{"stdin":{"type":"uri", "value":"s3://lanlytics/path/to/input/test.geojson"}, "command":[]}')
        local_command = l.localize_command(command)
        assert(isinstance(local_command, dict))

    @mock.patch('local_launch.launch_container')
    def test_execute_docker(self, mock_launch_container):
        message = {'service': 'test', 'id': '1234',
                    'command': {'stdin':{'type':'uri', 'value':'s3://lanlytics/path/to/input/test.geojson'}, 'command':[]}}
        cmd = l.Command('docker', message, [])
        cmd.execute()
        assert(mock_launch_container.called)

    @mock.patch('local_launch.launch_native')
    def test_execute_native(self, mock_launch_native):
        message = {'service': 'test', 'id': '1234',
                    'command': {'stdin':{'type':'uri', 'value':'s3://lanlytics/path/to/input/test.geojson'}, 'command':[]}}
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
    @mock.patch('docker.models.containers.Container.wait', return_value=0)
    def test_launch_container(self, mock_localize_resource, 
                              mock_makedirs, mock_client,
                              mock_rmtree, mock_resource, mock_wait):
        status, feedback, stdout_data, stderr_data = l.launch_container('test', test_commands['basic_command'])
        assert(status == 'failed')
        #assert(feedback == TBD)
        assert(stdout_data == None)
        assert(stderr_data == None)
        assert(mock_rmtree.called)

    @mock.patch('boto3.resource')
    @mock.patch('shutil.rmtree')
    @mock.patch('docker.DockerClient', autospec=True)
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('local_launch.localize_resource', 
                return_value='/path/to/resource.txt')
    @mock.patch('docker.models.containers.Container.wait', return_value=0)
    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_launch_container_pipe(self, mock_localize_resource, 
                              mock_makedirs, mock_client,
                              mock_rmtree, mock_resource, mock_wait, mock_open):
        status, feedback, stdout_data, stderr_data = l.launch_container('test', test_commands['pipe_command'])
        assert(status == 'failed')
        #assert(feedback == TBD)
        assert(stdout_data == None)
        assert(stderr_data == None)
        #mock_open.assert_called_with('/bucket/path/to/stderr.txt', 'w')
        #assert(mock_rmtree.called)

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
        command = json.loads('"command":[]}')
        status, result, stdout_data, stderr_data = l.launch_native(['python', 'test.py'], command)
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
        command = json.loads('{"stdout":{"type":"uri", "value":"s3://lanlytics/path/to/output/test.geojson"}, "command":[]}')
        status, result, stdout_data, stderr_data = l.launch_container('test', command)
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
        command = json.loads('{"stdout":{"type":"uri", "value":"s3://lanlytics/path/to/output/test.geojson"}, "command":[]}')
        status, result, stdout_data, stderr_data = l.launch_container('test', command)
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
        command = json.loads('{"stdin":{"type":"uri", "value":"s3://lanlytics/path/to/input/test.geojson"}, "command":[]}')
        status, result, stdout_data, stderr_data = l.launch_native(['python', 'test.py'], command)
        assert(mock_rmtree.called)
