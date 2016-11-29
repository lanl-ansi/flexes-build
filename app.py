import json
import os
from flask import Flask, Markup, abort, \
                  jsonify, render_template, request
from jinja2.exceptions import TemplateNotFound
from markdown2 import markdown
from utils import query_job, submit_job

app = Flask(__name__)

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
        if message is not None:
            job_id = submit_job(message, service)
            response = {'jobId': job_id, 
                        'status': 'submitted', 
                        'message': 'job submitted'}
        else:
            response = {'jobId': None, 
                        'status': 'error', 
                        'message': 'no message found in request'}
        return jsonify(**response)


@app.route('/<service>/docs', methods=['GET'])
def render_docs(service):
    doc_path = 'static/docs/{}.md'.format(service)
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


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run()
