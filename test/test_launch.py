import os, pytest, sys

sys.path.append('.')

import docker
import json
import mock

import launch as l

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
        command = test_commands['input_command']['command']
        local_command = l.build_localized_command(command)
        assert(mock_get_s3.call_count == 2)

    @mock.patch('boto3.resource')
    @mock.patch('utils.put_file_s3')
    @mock.patch('shutil.rmtree')
    def test_worker_cleanup(self, mock_rmtree, mock_put_s3, mock_resource):
        command = test_commands['output_command']['command']
        status, feedback, stdout_data, stderr_data = l.worker_cleanup(command, 0, 'worker log', None, None)
        assert(mock_put_s3.call_count == 2)

    def test_build_bash_command(self):
        command = test_commands['basic_command']['command']
        expected = ['s3://bucket/path/to/input.txt', 
                    '--arg1 arg_val', 
                    '--output s3://bucket/path/to/output.txt']
        bash_command = l.build_bash_command(command)
        assert(bash_command == expected)
        
    @mock.patch('launch.localize_resource', return_value='/path/to/resource.txt')
    @mock.patch('os.makedirs', return_value=None)
    def test_localize_command(self, mock_localize_resource, mock_makedirs):
        command = test_commands['std_command']['command'] 
        local_command = l.localize_command(command)
        assert(isinstance(local_command, dict))

    @mock.patch('launch.launch_container')
    def test_execute_docker(self, mock_launch_container):
        message = test_commands['basic_command']
        cmd = l.Command('docker', [], message['service'], message['command'])
        cmd.execute()
        assert(mock_launch_container.called)

    @mock.patch('launch.launch_native')
    def test_execute_native(self, mock_launch_native):
        message = test_commands['basic_command']
        cmd = l.Command('native', [], message['service'], message['command'])
        cmd.execute()
        assert(mock_launch_native.called)


class TestLaunch:
    @mock.patch('boto3.resource')
    @mock.patch('shutil.rmtree')
    @mock.patch('docker.DockerClient', autospec=True)
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('launch.localize_resource', return_value='/path/to/resource.txt')
    @mock.patch('launch.persist_command')
    def test_launch_container(self, mock_persist_command, mock_localize_resource, 
                              mock_makedirs, mock_client,
                              mock_rmtree, mock_resource):
        mock_client.return_value.containers.run.return_value.wait.return_value = 0
        type(mock_client.return_value.containers.run.return_value).status = mock.PropertyMock(side_effect=['running', 'running', 'exited'])
        message = test_commands['basic_command']
        status, feedback, stdout_data, stderr_data = l.launch_container(message['service'], message['command'])
        assert(status == 'complete')
        assert(stdout_data == None)
        assert(stderr_data == None)
        assert(mock_rmtree.called)

    @mock.patch('boto3.resource')
    @mock.patch('shutil.rmtree')
    @mock.patch('docker.DockerClient', autospec=True)
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('launch.localize_resource', return_value='/path/to/resource.txt')
    @mock.patch('launch.persist_command')
    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_launch_container_pipe(self, mock_open, 
                              mock_persist_command, mock_localize_resource, 
                              mock_makedirs, mock_client,
                              mock_rmtree, mock_resource):
        mock_client.return_value.containers.run.return_value.wait.return_value = 0
        type(mock_client.return_value.containers.run.return_value).status = mock.PropertyMock(side_effect=['running', 'running', 'exited'])
        message = test_commands['pipe_command']
        status, feedback, stdout_data, stderr_data = l.launch_container(message['service'], message['command'])
        assert(status == 'complete')
        assert(stdout_data == [])
        assert(stderr_data == None)

    @mock.patch('boto3.resource')
    @mock.patch('shutil.rmtree')
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('os.listdir', return_value=[])
    @mock.patch('launch.localize_resource', return_value='test/data/test.txt')
    @mock.patch('subprocess.Popen', autospec=True)
    def test_launch_native(self, mock_subprocess, mock_localize_resource, 
                           mock_listdir, mock_makedirs, 
                           mock_rmtree, mock_resource):
        mock_subprocess.return_value.communicate.return_value = (b'test', b'test')
        mock_subprocess.return_value.returncode = 0
        command = test_commands['basic_command']['command']
        status, result, stdout_data, stderr_data = l.launch_native(['python', 'test.py'], command)
        assert(mock_listdir.called)
        assert(mock_rmtree.called)

    @mock.patch('boto3.resource')
    @mock.patch('shutil.rmtree')
    @mock.patch('docker.DockerClient', autospec=True)
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('launch.localize_resource', return_value='/path/to/resource.txt')
    def test_launch_container_fail(self, mock_localize_resource, 
                                   mock_makedirs, mock_client,
                                   mock_rmtree, mock_resource):
        expected = 'Job finished with exit code: -1\nContainer execution failed' 
        mock_client.return_value.containers.run.side_effect = docker.errors.ContainerError('error', -1, 'test', 'test', b'Container execution failed')
        message = test_commands['basic_command']
        status, result, stdout_data, stderr_data = l.launch_container(message['service'], message['command'])
        assert(status == 'failed')
        assert(result == expected) 

    @mock.patch('boto3.resource')
    @mock.patch('shutil.rmtree')
    @mock.patch('docker.DockerClient', autospec=True)
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('launch.localize_resource', return_value='/path/to/resource.txt')
    def test_launch_container_notfound(self, mock_localize_resource, 
                                   mock_makedirs, mock_client,
                                   mock_rmtree, mock_resource):
        expected = 'Job finished with exit code: -1\nImage not found' 
        mock_client.return_value.containers.run.side_effect = docker.errors.ImageNotFound('Image not found')
        message = test_commands['basic_command']
        status, result, stdout_data, stderr_data = l.launch_container(message['service'], message['command'])
        assert(status == 'failed')
        assert(result == expected) 
