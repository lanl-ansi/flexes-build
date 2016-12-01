import json
import os
from deploy import deploy
from flask import Flask, Markup, abort, \
                  jsonify, render_template, request
from jinja2.exceptions import TemplateNotFound
from jsonschema import validate, ValidationError
from markdown2 import markdown
from utils import query_job, submit_job

app = Flask(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_STATIC = os.path.join(APP_ROOT, 'static')

with open('input_schema.json') as f:
    input_schema = json.load(f)


def isvalid(obj, schema):
    try:
        validate(obj, schema)
        return True
    except ValidationError:
        return False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/<service>', methods=['GET', 'POST'])
def post_job(service):
    if request.method == 'GET':
        try:
            return render_template('{}.html'.format(service))
        except TemplateNotFound:
            abort(404)
    elif request.method == 'POST':
        message = request.get_json()

        if message is None:
            response = {'jobId': None, 
                        'status': 'error', 
                        'message': 'no message found in request'}
        elif isvalid(message, input_schema) is False:
            response = {'jobId': None,
                        'status': 'error',
                        'message': 'not a valid input'}
        else:
            job_id = submit_job(message, service)
            response = {'jobId': job_id, 
                        'status': 'submitted', 
                        'message': 'job submitted'}
        return jsonify(**response)


@app.route('/<service>/docs', methods=['GET'])
def render_docs(service):
    doc_path = os.path.join(APP_STATIC, 'docs', '{}.md'.format(service))
    if os.path.isfile(doc_path):
        with app.open_resource(doc_path) as f:
            content = f.read()
        content = Markup(markdown(content, extras=['fenced-code-blocks']))
        return render_template('docs.html', **locals())
    else:
        abort(404)


@app.route('/<service>/jobs/<job_id>', methods=['GET'])
def query_status(service, job_id):
    return jsonify(**query_job(job_id))


@app.route('/deploy', methods=['GET'])
def deploy_app():
    return jsonify({'message': 'working on it'})


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run()
