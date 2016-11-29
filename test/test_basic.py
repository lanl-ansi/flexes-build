import os, pytest, sys

sys.path.append('.')

from flask import url_for

@pytest.mark.usefixtures('client_class')
class TestEndpoints:
    def test_index(self):
        assert(self.client.get(url_for('index')).status_code == 200)
