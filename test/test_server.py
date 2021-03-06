import os, pytest, sys

import botocore
import json
import mock
from asynctest import CoroutineMock
from flask import url_for, jsonify
from flexes_build.config import load_message_schema
from flexes_build.server import app, utils

def mock_download_fileobj(key, data):
    data.write(b'{"foo": "bar"}')

@pytest.mark.usefixtures('client_class')
class TestEndpoints:
    def test_index(self):
        assert(self.client.get(url_for('index')).status_code == 200)

    @mock.patch('requests.get')
    @mock.patch('flexes_build.server.app.submit_job', return_value='job_id')
    def test_service_post(self, mock_submit, mock_request):
        mock_request.return_value.json.return_value = {'name': 'test'}
        expected = {'job_id': 'job_id', 
                    'status': 'submitted',
                    'message': 'job submitted'}
        service_url = url_for('index')
        message = {
            'service': 'test',
            'command': {
                'stderr': {'type': 'uri', 'value': 's3://path/to/data.json'},
                'arguments': [
                    {'type': 'input', 'name': 'my_input', 'value': 'foo'},
                    {'type': 'parameter', 'name': 'param1', 'value': 'bar'},
                    {'type': 'parameter', 'name': 'param2', 'value': 3},
                    {'type': 'output', 'name': 'out', 'value': 's3://path/out/out.tif'}
                ]
            }
        }
        data = json.dumps(message)
        resp = self.client.post(service_url, data=data, content_type='application/json')
        print(resp.data)
        assert(resp.json == expected)

    @mock.patch('requests.get')
    @mock.patch('flexes_build.server.app.submit_job', return_value='job_id')
    @mock.patch('flexes_build.server.app.db', return_value=mock.MagicMock())
    def test_service_post_queue_override(self, mock_db, mock_submit, mock_request):
        mock_request.return_value.json.return_value = {'name': 'test'}
        expected = {'job_id': 'job_id', 
                    'status': 'submitted',
                    'message': 'job submitted'}
        service_url = url_for('index')
        message = {
            'queue': 'custom-queue',
            'service': 'test',
            'command': {
                'stderr': {'type': 'uri', 'value': 's3://path/to/data.json'},
                'arguments': [
                    {'type': 'input', 'name': 'my_input', 'value': 'foo'},
                    {'type': 'parameter', 'name': 'param1', 'value': 'bar'},
                    {'type': 'parameter', 'name': 'param2', 'value': 3},
                    {'type': 'output', 'name': 'out', 'value': 's3://path/out/out.tif'}
                ]
            }
        }
        data = json.dumps(message)
        resp = self.client.post(service_url, data=data, content_type='application/json')
        assert(resp.json == expected)
        mock_submit.assert_called_with(mock_db, message)

    def test_service_post_empty(self):
        expected = {'job_id': None, 
                    'status': 'error',
                    'message': 'no message found in request'}
        service_url = url_for('index')
        resp = self.client.post(service_url)
        assert(resp.json == expected)

    def test_service_post_invalid(self):
        expected = {'job_id': None, 
                    'status': 'error',
                    'message': 'not a valid input'}
        service_url = url_for('index')
        data = json.dumps({'foo': 'bar'})
        resp = self.client.post(service_url, data=data, content_type='application/json')
        assert(resp.json == expected)

    @mock.patch('boto3.resource')
    @mock.patch('flexes_build.server.app.stream_from_s3', return_value={})
    def test_service_info(self, mock_stream, mock_resource):
        service_url = url_for('service_info', service_name='popecon')
        assert(self.client.get(service_url).status_code == 200)

    @mock.patch('boto3.resource')
    @mock.patch('flexes_build.server.app.stream_from_s3', side_effect=botocore.exceptions.ClientError({'Error': {'Code': 404}}, 'test'))
    def test_bad_service_info(self, mock_stream, mock_resource):
        service_url = url_for('service_info', service_name='foo')
        assert(self.client.get(service_url).status_code == 404)

    @mock.patch('flexes_build.server.app.all_running_jobs', return_value=[{'job_id':i,'status':'running'} for i in range(4)])
    @mock.patch('flexes_build.server.app.all_queues', return_value=[{'queue':i,'jobs':i} for i in range(4)])
    @mock.patch('flexes_build.server.app.all_workers', return_value=[{'id':i,'queue':'foo'} for i in range(4)])
    def test_dashboard(self, mock_all_workers, mock_all_queues, mock_all_running_jobs):
        service_url = url_for('dashboard')
        assert(self.client.get(service_url).status_code == 200)

    @mock.patch('flexes_build.server.app.list_services')
    def test_services(self, mock_list_services):
        mock_list_services.return_value = {'services': ['a', 'b', 'c']}
        service_url = url_for('services')
        assert(self.client.get(service_url).status_code == 200)


class TestUtils:
    def setup_method(self):
        self.db = mock.MagicMock()

    @mock.patch('flexes_build.server.utils.uuid4', return_value='test_job')
    def test_submit_job(self, mock_uuid):
        message = {'service': 'test', 'command': {'arguments': []}}
        job_id = utils.submit_job(self.db, message)
        assert(job_id == 'test_job')

    def test_query_job(self):
        self.db.hget.return_value = 'test'
        expected = {'status': 'test', 'job_id': 'job_id'}
        query_result = utils.query_job_status(self.db, 'job_id')
        assert(query_result == expected)

    @mock.patch('boto3.resource')
    def test_query_job_old(self, mock_resource):
        self.db.hget.return_value = None
        self.db.hgetall.return_value = {}
        mock_resource.return_value.Table.return_value.get_item.return_value = {'Item': {'foo': 'bar'}}
        expected = {'foo': 'bar'}
        query_result = utils.query_job_status(self.db, 'job_id')
        assert(query_result == expected)

    @mock.patch('boto3.resource')
    def test_query_job_no_exist(self, mock_resource):
        self.db.hget.return_value = None
        self.db.hgetall.return_value = {}
        mock_resource.return_value.Table.return_value.get_item.return_value = {}
        query_result = utils.query_job_status(self.db, 'job_id')
        assert(query_result['status'] == 'failed')

    def test_job_messages(self):
        self.db.get.return_value = '[1,2,3,4]'
        messages = utils.job_messages(self.db, 'test')
        assert(len(messages) == 4)
        self.db.get.assert_called_with('message:test')

    def test_all_running_jobs(self):
        return_keys = ['job_id', 'status', 'queue']
        self.db.hmget.return_value = {key: 'test' for key in return_keys}
        self.db.keys.return_value = ['foo', 'bar', 'baz']
        jobs = utils.all_running_jobs(self.db)
        assert(len(jobs) == 3)
        self.db.hmget.assert_called_with('baz', return_keys)
        assert(self.db.hmget.call_count == 3)

    def test_all_queues(self):
        queue_names = ['foo', 'bar', 'baz']
        self.db.keys.return_value = queue_names
        queues = utils.all_queues(self.db)
        assert(len(queues) == 3)

    def test_all_workers(self):
        return_keys = ['status', 'queue']
        self.db.hmget.return_value = {key: 'test' for key in return_keys}
        self.db.keys.return_value = ['foo', 'bar', 'baz']
        workers = utils.all_workers(self.db)
        assert(len(workers) == 3)
        self.db.hmget.assert_called_with('baz', return_keys)
        assert(self.db.hmget.call_count == 3)


    @mock.patch('flexes_build.server.utils.get_services', new_callable=CoroutineMock)
    def test_list_services(self, mock_get_services):
        mock_response_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data/services.json')
        with open(mock_response_file) as f:
            mock_responses = json.load(f)
        mock_get_services.return_value = mock_responses['raw']
        services = utils.list_services()
        assert(services == mock_responses['all'])

    @mock.patch('flexes_build.server.utils.get_services', new_callable=CoroutineMock)
    def test_list_services_tags(self, mock_get_services):
        mock_response_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data/services.json')
        with open(mock_response_file) as f:
            mock_responses = json.load(f)
        mock_get_services.return_value = mock_responses['raw']
        services = utils.list_services(tags=['lanl'])
        assert(services == mock_responses['lanl'])

    @mock.patch('boto3.resource')
    def test_stream_from_s3(self, mock_resource):
        mock_resource.Bucket.return_value.download_fileobj.side_effect = mock_download_fileobj
        result = utils.stream_from_s3('s3://bucket/test/file.txt', s3=mock_resource)
        assert(result == '{"foo": "bar"}')

    @mock.patch('boto3.resource')
    def test_stream_from_s3_json(self, mock_resource):
        mock_resource.Bucket.return_value.download_fileobj.side_effect = mock_download_fileobj
        result = utils.stream_from_s3('s3://bucket/test/file.txt', s3=mock_resource, json=True)
        assert(result == {'foo': 'bar'})


class TestSchema:
    def setup_method(self, _):
        self.input_schema = load_message_schema()

    def test_valid_input(self):
        message = {
            'queue': 'custom-queue',
            'service': 'test',
            'command': {
                'stderr': {'type': 'uri', 'value': 's3://path/to/data.json'},
                'arguments': [
                    {'type': 'input', 'name': 'my_input', 'value': 'foo'},
                    {'type': 'parameter', 'name': 'param1', 'value': 'bar'},
                    {'type': 'parameter', 'name': 'param2', 'value': 3},
                    {'type': 'output', 'name': 'out', 'value': 's3://path/out/out.tif'}
                ]
            }
        }
        assert(app.isvalid(message, self.input_schema) is True)

    def test_invalid_input(self):
        message = {
            'stderr': '/path/to/data.json',
            'command': [
                {'type': 'random', 'name': 'my_input', 'value': 'foo'},
                {'type': 'parameter', 'name': 'param1', 'value': 'bar'},
                {'type': 'parameter', 'name': 'param2', 'value': 3},
                {'type': 'output', 'name': 'out', 'value': 's3://path/out/out.tif'}
            ],
            'someprop': 'stuff'
        }
        assert(app.isvalid(message, self.input_schema) is False)
