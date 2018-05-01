import os, pytest, sys

sys.path.append('.')
import json
import mock
import utils
import worker
from argparse import ArgumentParser
from botocore.exceptions import ClientError
from collections import namedtuple
from docker.errors import ImageNotFound
from settings import *

class TestUtils:
    @mock.patch('docker.DockerClient')
    def test_image_exists(self, mock_client):
        assert(utils.image_exists('test'))

    @mock.patch('docker.DockerClient')
    def test_image_exists_remote(self, mock_client):
        mock_client.return_value.images.get.side_effect = ImageNotFound('image not found')
        assert(utils.image_exists('test'))

    @mock.patch('docker.DockerClient')
    def test_image_exists_fail(self, mock_client):
        mock_client.return_value.images.get.side_effect = ImageNotFound('image not found')
        mock_client.return_value.images.pull.side_effect = ImageNotFound('image not found')
        assert(utils.image_exists('test') is False)

