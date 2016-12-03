import os, pytest, sys

sys.path.append('.')
import botocore
import json
import mock
import docker_launch as dw


class TestIO:
    def setup_method(self, _):
        self.command = {
            "command": [
                {"type":"parameter", "value":"/root/input/simple_polyWGS84.shp"},
                {"type":"parameter", "name":"--fields=", "value":"\"Total Population;Total Jobs\""}
            ]}

    def test_resolve_input_s3_json(self):
        expected = dw.local_files_path+'/lanlytics/path/to/input/test.geojson'
        file_uri = 's3://lanlytics/path/to/input/test.geojson'
        local_path = dw.get_local_path(file_uri)
        assert(local_path == expected)

    def test_resolve_input_s3_shp(self):
        expected = dw.local_files_path+'/lanlytics/path/to/input/test.shp'
        file_uri = 's3://lanlytics/path/to/input/test.shp'
        local_path = dw.get_local_path(file_uri)
        assert(local_path == expected)

    def test_resolve_input_local(self):
        filename = '/home/ec2-user/output/test.geojson'
        aoi = dw.get_local_path(filename)
        assert(aoi == filename)

    def test_resolve_input_json(self):
        filename = '{"foo": "bar"}'
        aoi = dw.get_local_path(filename)
        assert(aoi == filename)

    @mock.patch('boto3.resource')
    def test_s3_file_not_found(self, mock_resource):
        filename = 's3://lanlytics/path/to/input/test.txt'
        with pytest.raises(botocore.exceptions.ClientError):
            dw.localize_resource(filename)

    def test_parse_params(self):
        expected = '/root/input/simple_polyWGS84.shp --fields="Total Population;Total Jobs"'
        cmd = dw.build_command(self.command)
        cmd = ' '.join(cmd)
        assert(cmd == expected)
