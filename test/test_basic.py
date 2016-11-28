import os, pytest, sys

sys.path.append('.')
import botocore
import client
import json
import mock
from docker_worker import docker_launch as dw


class TestIO:
    def setup_method(self, _):
        self.params = '{"aoi": "/root/input/simple_polyWGS84.shp", \
                        "fields": "Total Population;Total Jobs"}'

    def test_append_command(self):
        cmd = '--bin BIN'
        expected = '--bin BIN --output /root/output/test.json'
        arg_name = '--output'
        arg_value = '/root/output/test.json'
        cmd = dw.append_command(cmd, arg_name, arg_value)
        assert(cmd == expected)    

    def test_append_command_none(self):
        expected = '--bin BIN'
        arg_name = '--bin'
        arg_value = 'BIN'
        cmd = dw.append_command(None, arg_name, arg_value)
        assert(cmd == expected)    

    @mock.patch('boto3.resource')
    def test_resolve_input_s3_json(self, mock_resource):
        expected = '/home/ec2-user/input/test.geojson'
        filename = 's3://lanlytics/path/to/input/test.geojson'
        aoi = dw.resolve_input(filename)
        assert(aoi == expected)

    @mock.patch('boto3.resource')
    def test_resolve_input_s3_shp(self, mock_resource):
        expected = '/home/ec2-user/input/test.shp'
        filename = 's3://lanlytics/path/to/input/test.shp'
        aoi = dw.resolve_input(filename)
        assert(aoi == expected)

    @mock.patch('boto3.resource')
    def test_resolve_input_s3_fail(self, mock_resource):
        filename = 's3://lanlytics/path/to/input/test.txt'
        with pytest.raises(ValueError):
            dw.resolve_input(filename)

    def test_resolve_input_json(self):
        filename = '{"foo": "bar"}'
        aoi = dw.resolve_input(filename)
        assert(aoi == filename)

    def test_resolve_input_local(self):
        filename = '/home/ec2-user/output/test.geojson'
        aoi = dw.resolve_input(filename)
        assert(aoi == filename)

    def test_parse_params(self):
        expected = '/root/input/simple_polyWGS84.shp --fields="Total Population;Total Jobs"'
        params = json.loads(self.params)
        cmd = dw.parse_params(params)
        assert(cmd == expected)


class TestClient():
    @mock.patch('boto3.resource')
    def test_submit_job(self, mock_resource):
        mock_resource.return_value.get_queue_by_name.return_value.send_message.return_value.get.return_value = 'job'
        message = {'foo': 'bar'}
        service = 'test'
        job_id = client.submit_job(message, service)
        assert(isinstance(job_id, str))

    @mock.patch('boto3.resource')
    def test_no_region_error(self, mock_resource):
        mock_resource.side_effect = botocore.exceptions.NoRegionError()
        message = {'foo': 'bar'}
        service = 'test'
        job_id = client.submit_job(message, service)
        assert(job_id is None)

# docker-py doesn't mock
#    @mock.patch('docker.Client')
#    def test_launch_container(self, mock_client):
#        expected = '/home/ec2-user/output/test.json' 
#        mock_client.return_value.wait.return_value = 0
#        output = dw.launch_container(self.params, 'test')
#
#    @mock.patch('docker.Client')
#    def test_launch_container_fail(self, mock_client):
#        mock_client.return_value.wait.return_value = 1
#        with pytest.raises(RuntimeError):
#            dw.launch_container(self.params, 'test')
