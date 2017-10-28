#!/usr/bin/env python

import requests
import yaml

def create_compose():
    with open('docker-compose.yml') as f:
        compose = yaml.load(f)

    resp = requests.get('http://169.254.169.254/latest/dynamic/instance-identity/document')
    region = resp.json()['region']

    compose['services']['flask']['environment'] = ['AWS_DEFAULT_REGION={}'.format(region)]

    with open('docker-compose.yml', 'w') as f:
        yaml.dump(compose, f, default_flow_style=False)

if __name__ == '__main__':
    create_compose()
