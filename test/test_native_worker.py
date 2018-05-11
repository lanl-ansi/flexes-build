import os, pytest, sys

sys.path.append('.')
import mock
from native_worker import NativeWorker
from test_common import test_commands

class TestNativeWorker:
    @mock.patch('api_worker.StrictRedis')
    @mock.patch('boto3.resource')
    def setup_method(self, _, mock_resource, mock_redis):
        self.message = {'job_id': '1234', 'service': 'worker'}
        self.worker = NativeWorker(queue='test', poll_frequency=1, cmd_prefix=['python', 'test.py'])

    @mock.patch('shutil.rmtree')
    @mock.patch('os.makedirs', return_value=None)
    @mock.patch('launch.localize_resource', return_value='test/data/test.txt')
    @mock.patch('subprocess.Popen', autospec=True)
    def test_launch_native(self, mock_subprocess, mock_localize_resource, 
                           mock_makedirs, mock_rmtree):
        self.worker.localize_resource = mock.MagicMock(return_value='/path/to/resource.txt')
        self.worker.persist_command = mock.MagicMock()
        mock_subprocess.return_value.communicate.return_value = (b'test', b'test')
        mock_subprocess.return_value.returncode = 0
        command = test_commands['basic_command']['command']
        status, result, stdout_data, stderr_data = self.worker.launch(command)
        assert(mock_rmtree.called)
