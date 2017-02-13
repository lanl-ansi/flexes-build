import os, pytest, sys

sys.path.append('.')

import app
import botocore
import utils
import json
import mock
from flask import url_for, jsonify

class MockBoto:
    def __init__(self):
        self.resources = {'sqs': mock.MagicMock(), 'dynamodb': mock.MagicMock()}

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
    
    @mock.patch('app.boto', return_value=MockBoto())
    @mock.patch('app.submit_job', return_value='job_id')
    def test_service_post(self, mock_boto, mock_submit):
        expected = {'job_id': 'job_id', 
                    'status': 'submitted',
                    'message': 'job submitted'}
        service_url = url_for('post_job', service='test')
        command = {
            'stderr': 's3://path/to/data.json',
            'command': [
                {'type': 'input', 'name': 'my_input', 'value': 'foo'},
                {'type': 'parameter', 'name': 'param1', 'value': 'bar'},
                {'type': 'parameter', 'name': 'param2', 'value': 3},
                {'type': 'output', 'name': 'out', 'value': 's3://path/out/out.tif'}
            ]    
        }
        data = json.dumps(command)
        resp = self.client.post(service_url, data=data, content_type='application/json')
        assert(resp.json == expected)

    def test_service_post_empty(self):
        expected = {'job_id': None, 
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
    def test_submit_job(self):
        mock_db = mock.MagicMock()
        mock_sqs = mock.MagicMock()
        mock_dyn = mock.MagicMock()
        mock_sqs.get_queue_by_name.return_value.send_message.return_value = {'MessageId': 'job'}
        message = {'foo': 'bar'}
        attributes = {'Service': 'test', 'ServiceType': 'generic'}
        job_id = utils.submit_job(mock_db, mock_dyn, mock_sqs, message, attributes)
        assert(job_id == 'job')


class TestSchema:
    def setup_method(self, _):
        schema_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'message_schema.json')
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
