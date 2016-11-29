import os, pytest, sys

sys.path.append('.')

import app
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
        assert(self.client.get(service_url).status_code == 500)

    @mock.patch('app.submit_job', return_value='job_id')
    def test_service_post(self, mock_submit):
        expected = {'jobId': 'job_id', 'status': 'submitted'}
        service_url = url_for('post_job', service='test')
        resp = self.client.post(service_url)
        assert(resp.json == expected)
