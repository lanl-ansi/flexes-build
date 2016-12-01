import os, pytest, sys

sys.path.append('.')
import botocore
import json
import mock
import docker_launch as dw


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
