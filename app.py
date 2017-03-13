#!/usr/bin/env python

import json
import os
import redis
import requests
from deploy import deploy
from flask import Flask, Markup, abort, \
                  jsonify, render_template, request
from flask_redis import FlaskRedis
from jinja2.exceptions import TemplateNotFound
from jsonschema import validate, ValidationError
from markdown2 import markdown
from utils import query_job, submit_job, all_jobs

app = Flask(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_STATIC = os.path.join(APP_ROOT, 'static')

REDIS_HOST = 'jobs.be6b1p.0001.usgw1.cache.amazonaws.com'
REDIS_PORT = 6379
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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/services', methods=['GET'])
def services():
    resp = requests.get('https://hub.lanlytics.com/v2/_catalog')
    services = resp.json()['repositories']
    return render_template('services.html', services=services)


@app.route('/dashboard', methods=['GET'])
def dashboard():
    jobs = [job for job in all_jobs() if job['status'] != 'complete']
    return render_template('dashboard.html', jobs=jobs)


@app.route('/api', methods=['GET', 'POST'])
def job():
    if request.method == 'GET':
        service = request.args.get('service')
        try:
            return render_template('{}.html'.format(service))
        except TemplateNotFound:
            abort(404)


@app.route('/api/docs', methods=['GET'])
def render_docs():
    service = request.args.get('service')
    doc_path = os.path.join(APP_STATIC, 'docs', '{}.md'.format(service))
    if os.path.isfile(doc_path):
        with app.open_resource(doc_path) as f:
            content = f.read()
        content = Markup(markdown(content, extras=['fenced-code-blocks']))
        return render_template('docs.html', **locals())
    else:
        abort(404)


@app.route('/api/jobs', methods=['GET'])
def query_status():
    job_id = request.args.get('job_id')
    return jsonify(**query_job(db, job_id))


@app.route('/deploy', methods=['GET'])
def deploy_app():
    return jsonify({'message': 'working on it'})


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__': # pragma: no cover
    app.run()
