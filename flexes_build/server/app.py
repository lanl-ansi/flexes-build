#!/usr/bin/env python

import boto3
import json
import os
import requests
from .. import config as configure
from botocore.exceptions import ClientError
from flask import Flask, Markup, abort, \
                  jsonify, render_template, request
from flask_swagger_ui import get_swaggerui_blueprint
from flask_redis import FlaskRedis
from jinja2.exceptions import TemplateNotFound
from jsonschema import validate, ValidationError
from .utils import query_job_status, get_job_result, submit_job, \
        all_running_jobs, all_queues, all_workers, list_services, \
        stream_from_s3

app = Flask(__name__)

config = configure.load_config()
message_schema = configure.load_message_schema()

REDIS_URL = 'redis://{}:{}/0'.format(config['REDIS_HOST'], config['REDIS_PORT'])
app.config['REDIS_URL'] = REDIS_URL
db = FlaskRedis(app, decode_responses=True)

SWAGGER_URL = '/docs'
SWAGGER_PATH = '../static/docs/swagger.yml'
swagger_blueprint = get_swaggerui_blueprint(SWAGGER_URL, SWAGGER_PATH)
app.register_blueprint(swagger_blueprint, url_prefix=SWAGGER_URL)

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
        response = jsonify(**response)
        response.status_code = 400
    elif isvalid(message, message_schema) is False:
        response = {'job_id': None,
                    'status': 'error',
                    'message': 'not a valid input'}
        response = jsonify(**response)
        response.status_code = 400
    else:
        job_id = submit_job(db, message)
        response = {'job_id': job_id, 
                    'status': 'submitted', 
                    'message': 'job submitted'}
        response = jsonify(**response)
        response.status_code = 202
        response.scheme = 'https'
        response.headers['Location'] = '{}/jobs/{}'.format(config['API_ENDPOINT'], job_id)
        response.autocorrect_location_header = False
    return response


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')
    elif request.method == 'POST':
        message = request.get_json()
        response = service_response(message)
        return response


@app.route('/services', methods=['GET'])
def services():
    tags = request.args.get('tags')
    tags = tags.split(',') if tags is not None else tags
    services = list_services(tags=tags)
    return jsonify(**services)


@app.route('/services/<service_name>', methods=['GET'])
def service_info(service_name):
    tag = request.args.get('tag', config['DEFAULT_TAG'])
    doc_path = 's3://{}/lanlytics-api/docs/{}/{}/service_docs.json'.format(config['DOCS_BUCKET'], service_name, tag)
    try:
        s3 = boto3.resource('s3')
        content = stream_from_s3(doc_path, s3=s3, json=True)
        return jsonify(**content)
    except ClientError:
        abort(404)


@app.route('/dashboard', methods=['GET'])
def dashboard():
    jobs = all_running_jobs(db)
    queues = all_queues(db)
    workers = all_workers(db)
    return render_template('dashboard.html', jobs=jobs, queues=queues, workers=workers)


@app.route('/jobs/<job_id>/status', methods=['GET'])
def query_job(job_id):
    return jsonify(**get_job_status(db, job_id))


@app.route('/jobs/<job_id>', methods=['GET'])
def job_result(job_id):
    return jsonify(**get_job_result(db, job_id))


@app.route('/jobs/<job_id>/messages', methods=['GET'])
def get_job_messages(job_id):
    return jsonify(**job_messages(db, job_id))


@app.route('/deploy', methods=['GET'])
def deploy_app():
    return jsonify({'message': 'working on it'})


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__': # pragma: no cover
    app.run()
