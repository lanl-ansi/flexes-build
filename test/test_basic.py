import os, pytest, sys

sys.path.append('.')

import app
import botocore
import utils
import json
import mock
from flask import url_for, jsonify

@pytest.mark.usefixtures('client_class')
class TestEndpoints:
    def test_index(self):
        assert(self.client.get(url_for('index')).status_code == 200)

    def test_service_get(self):
        service_url = url_for('post_job', service='popecon')
        assert(self.client.get(service_url).status_code == 200)

    def test_bad_service_get(self):
        service_url = url_for('post_job', service='foo')
        assert(self.client.get(service_url).status_code == 404)

    @mock.patch('app.submit_job', return_value='job_id')
    def test_service_post(self, mock_submit):
        expected = {'jobId': 'job_id', 
                    'status': 'submitted',
                    'message': 'job submitted'}
        service_url = url_for('post_job', service='test')
        data = json.dumps({'foo': 'bar'})
        resp = self.client.post(service_url, data=data, content_type='application/json')
        assert(resp.json == expected)

    def test_service_post_empty(self):
        expected = {'jobId': None, 
                    'status': 'error',
                    'message': 'no message found in request'}
        service_url = url_for('post_job', service='test')
        resp = self.client.post(service_url)
        assert(resp.json == expected)

    def test_service_docs(self):
        service_url = url_for('render_docs', service='popecon')
        assert(self.client.get(service_url).status_code == 200)

    def test_bad_service_docs(self):
        service_url = url_for('render_docs', service='foo')
        assert(self.client.get(service_url).status_code == 404)


class TestUtils:
    @mock.patch('boto3.resource')
    def test_submit_job(self, mock_resource):
        mock_resource.return_value.get_queue_by_name.return_value.send_message.return_value.get.return_value = 'job'
        message = {'foo': 'bar'}
        service = 'test'
        job_id = utils.submit_job(message, service)
        assert(isinstance(job_id, str))

    @mock.patch('boto3.resource')
    def test_no_region_error(self, mock_resource):
        mock_resource.side_effect = botocore.exceptions.NoRegionError()
        message = {'foo': 'bar'}
        service = 'test'
        job_id = utils.submit_job(message, service)
        assert(job_id is None) 


class TestSchema:
    def setup_method(self, _):
        schema_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'input_schema.json')
        with open(schema_file) as f:
            self.input_schema = json.load(f)

    def test_valid_input(self):
        command = {
            'stderr': 's3://path/to/data.json',
            'command': [
                {'type': 'input', 'name': 'my_input', 'value': 'foo'},
                {'type': 'parameter', 'name': 'param1', 'value': 'bar'},
                {'type': 'parameter', 'name': 'param2', 'value': 3},
                {'type': 'output', 'name': 'out', 'value': 's3://path/out/out.tif'}
            ]    
        }
        assert(app.isvalid(command, self.input_schema) is True)

    def test_invalid_input(self):
        command = {
            'stderr': '/path/to/data.json',
            'command': [
                {'type': 'random', 'name': 'my_input', 'value': 'foo'},
                {'type': 'parameter', 'name': 'param1', 'value': 'bar'},
                {'type': 'parameter', 'name': 'param2', 'value': 3},
                {'type': 'output', 'name': 'out', 'value': 's3://path/out/out.tif'}
            ],
            'someprop': 'stuff'
        }
        assert(app.isvalid(command, self.input_schema) is False)
