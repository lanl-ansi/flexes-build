import pytest, sys

sys.path.append('.')

from flexes_build.server.app import app as test_app

@pytest.fixture
def app():
    return test_app
