import os, pytest, sys

sys.path.append('.')

import app
import botocore
import utils
import json
import mock
from flask import url_for, jsonify
from flask_redis import FlaskRedis

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
    
    @mock.patch('requests.get')
    @mock.patch('app.submit_job', return_value='job_id')
    def test_service_post(self, mock_submit, mock_request):
        mock_request.return_value.json.return_value = {'name': 'test'}
        expected = {'job_id': 'job_id', 
                    'status': 'submitted',
                    'message': 'job submitted'}
        service_url = url_for('post_job', service='test')
        command = {
            'stderr': {'type': 'uri', 'value': 's3://path/to/data.json'},
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

    @mock.patch('requests.get')
    @mock.patch('app.submit_job', return_value='job_id')
    @mock.patch('app.db', return_value=mock.MagicMock())
    def test_service_post_queue_override(self, mock_db, mock_submit, mock_request):
        mock_request.return_value.json.return_value = {'name': 'test'}
        expected = {'job_id': 'job_id', 
                    'status': 'submitted',
                    'message': 'job submitted'}
        service_url = url_for('post_job', service='test')
        command = {
            'queue': 'custom-queue',
            'stderr': {'type': 'uri', 'value': 's3://path/to/data.json'},
            'command': [
                {'type': 'input', 'name': 'my_input', 'value': 'foo'},
                {'type': 'parameter', 'name': 'param1', 'value': 'bar'},
                {'type': 'parameter', 'name': 'param2', 'value': 3},
                {'type': 'output', 'name': 'out', 'value': 's3://path/out/out.tif'}
            ]    
        }
        attributes = {'service': 'test', 
                      'service_type': 'docker', 
                      'queue': 'custom-queue'}
        data = json.dumps(command)
        resp = self.client.post(service_url, data=data, content_type='application/json')
        assert(resp.json == expected)
        mock_submit.assert_called_with(mock_db, command, attributes)

    @mock.patch('requests.get')
    def test_service_post_image_not_found(self, mock_request):
        mock_request.return_value.json.return_value = {'errors': []}
        expected = {'job_id': None, 
                    'status': 'error',
                    'message': 'a docker image for test does not exist'}
        service_url = url_for('post_job', service='test')
        command = {
            'stderr': {'type': 'uri', 'value': 's3://path/to/data.json'},
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

    @mock.patch('app.submit_job', return_value='job_id')
    def test_native_dev_post(self, mock_submit):
        expected = {'job_id': 'job_id', 
                    'status': 'submitted',
                    'message': 'job submitted'}
        service_url = url_for('native_dev')
        command = {
            'stderr': {'type': 'uri', 'value': 's3://path/to/data.json'},
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

    def test_bad_native_dev_get(self):
        service_url = url_for('native_dev')
        assert(self.client.get(service_url).status_code == 404)
    
    @mock.patch('app.submit_job', return_value='job_id')
    def test_powerworld_post(self, mock_submit):
        expected = {'job_id': 'job_id', 
                    'status': 'submitted',
                    'message': 'job submitted'}
        service_url = url_for('powerworld')
        command = {
            'stderr': {'type': 'uri', 'value': 's3://path/to/data.json'},
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

    def test_bad_powerworld_get(self):
        service_url = url_for('powerworld')
        assert(self.client.get(service_url).status_code == 404)

    def test_service_post_empty(self):
        expected = {'job_id': None, 
                    'status': 'error',
                    'message': 'no message found in request'}
        service_url = url_for('post_job', service='test')
        resp = self.client.post(service_url)
        assert(resp.json == expected)

    def test_service_post_invalid(self):
        expected = {'job_id': None, 
                    'status': 'error',
                    'message': 'not a valid input'}
        service_url = url_for('post_job', service='test')
        data = json.dumps({'foo': 'bar'})
        resp = self.client.post(service_url, data=data, content_type='application/json')
        assert(resp.json == expected)

    def test_service_docs(self):
        service_url = url_for('render_docs', service='popecon')
        assert(self.client.get(service_url).status_code == 200)

    def test_bad_service_docs(self):
        service_url = url_for('render_docs', service='foo')
        assert(self.client.get(service_url).status_code == 404)

    @mock.patch('app.all_jobs', return_value=[{'status':'running'} for i in range(4)])
    def test_dashboard(self, mock_all_jobs):
        service_url = url_for('dashboard')
        assert(self.client.get(service_url).status_code == 200)

    @mock.patch('requests.get')
    def test_services(self, mock_request):
        mock_request.return_value.json.return_value = {'repositories': ['a', 'b', 'c']}
        service_url = url_for('services')
        assert(self.client.get(service_url).status_code == 200)


class TestUtils:
    def setup_method(self):
        self.db = mock.MagicMock()

    @mock.patch('utils.uuid4', return_value='test_job')
    def test_submit_job(self, mock_uuid):
        message = {'foo': 'bar'}
        attributes = {'service': 'test', 
                      'service_type': 'docker',
                      'queue': 'docker'}
        job_id = utils.submit_job(self.db, message, attributes)
        assert(job_id == 'test_job')

    def test_query_job(self):
        self.db.get.return_value = b'{"foo": "bar"}'
        expected = {'foo': 'bar'}
        query_result = utils.query_job(self.db, 'job_id')
        assert(query_result == expected)

    @mock.patch('boto3.resource')
    def test_query_job_old(self, mock_resource):
        self.db.get.return_value = None
        mock_resource.return_value.Table.return_value.get_item.return_value = {'Item': {'foo': 'bar'}}
        expected = {'foo': 'bar'}
        query_result = utils.query_job(self.db, 'job_id')
        assert(query_result == expected)

    @mock.patch('boto3.resource')
    def test_all_jobs(self, mock_resource):
        mock_resource.return_value.Table.return_value.scan.return_value = {'Items': [1, 2, 3]}
        expected = [1, 2, 3]
        query_result = utils.all_jobs()
        assert(query_result == expected)


class TestSchema:
    def setup_method(self, _):
        schema_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'message_schema.json')
        with open(schema_file) as f:
            self.input_schema = json.load(f)

    def test_valid_input(self):
        command = {
            'stderr': {'type': 'uri', 'value': 's3://path/to/data.json'},
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
