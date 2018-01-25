#!/usr/bin/env python

import json
import os
import requests
from flask import Flask, Markup, abort, \
                  jsonify, render_template, request
from flask_redis import FlaskRedis
from jinja2.exceptions import TemplateNotFound
from jsonschema import validate, ValidationError
from markdown2 import markdown
from settings import *
from utils import query_job, submit_job, all_jobs

app = Flask(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_STATIC = os.path.join(APP_ROOT, 'static')

REDIS_URL = 'redis://{}:{}/0'.format(REDIS_HOST, REDIS_PORT)
app.config['REDIS_URL'] = REDIS_URL
db = FlaskRedis(app)

with open(os.path.join(APP_ROOT, 'message_schema.json')) as f:
    message_schema = json.load(f)


def isvalid(obj, schema):
    try:
        validate(obj, schema)
        return True
    except ValidationError:
        return False


def service_response(message):
    if message is None:
        response = {'job_id': None, 
                    'status': 'error', 
                    'message': 'no message found in request'}
    elif isvalid(message, message_schema) is False:
        response = {'job_id': None,
                    'status': 'error',
                    'message': 'not a valid input'}
#    elif attributes['service_type'] == 'docker':
#        resp = requests.get('https://hub.lanlytics.com/v2/{}/tags/list'.format(attributes['service']))
#        if 'errors' in resp.json():
#            response = {'job_id': None,
#                        'status': 'error',
#                        'message': 'a docker image for {} does not exist'.format(attributes['service'])}
#        else:
#            job_id = submit_job(db, message, attributes)
#            response = {'job_id': job_id,
#                        'status': 'submitted',
#                        'message': 'job submitted'}
    else:
        job_id = submit_job(db, message)
        response = {'job_id': job_id, 
                    'status': 'submitted', 
                    'message': 'job submitted'}
    return response


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')
    elif request.method == 'POST':
        message = request.get_json()
        response = service_response(message)
        return jsonify(**response)


@app.route('/services', methods=['GET'])
def services():
    resp = requests.get('{}/v2/_catalog'.format(DOCKER_REGISTRY))
    services = {'services': resp.json()['repositories']}
    return jsonify(**services)


@app.route('/services/<service_name>', methods=['GET'])
def service_info(service_name):
    doc_path = os.path.join(APP_STATIC, 'docs', '{}.json'.format(service_name))
    if os.path.isfile(doc_path):
        with app.open_resource(doc_path) as f:
            content = json.load(f)
        return jsonify(**content)
    else:
        abort(404)


@app.route('/dashboard', methods=['GET'])
def dashboard():
    jobs = [job for job in all_jobs() if job['status'] != 'complete']
    return render_template('dashboard.html', jobs=jobs)


@app.route('/<service_name>', methods=['GET'])
def service(service_name):
    if request.method == 'GET':
        try:
            return render_template('{}.html'.format(service_name))
        except TemplateNotFound:
            abort(404)


@app.route('/jobs/<job_id>', methods=['GET'])
def query_status(job_id):
    return jsonify(**query_job(db, job_id))


@app.route('/deploy', methods=['GET'])
def deploy_app():
    return jsonify({'message': 'working on it'})


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__': # pragma: no cover
    app.run()
