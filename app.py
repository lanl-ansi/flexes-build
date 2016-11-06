import json
from flask import Flask, Markup, jsonify, \
                  render_template, request
from markdown2 import markdown
from client import send_message, query_job, submit_job

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/<service>', methods=['GET', 'POST'])
def post_job(service):
    if request.method == 'GET':
        return render_template('{}.html'.format(service))
    elif request.method == 'POST':
        message = request.get_json()
        job_id = send_message(message, service)
        submit_job(job_id, service)
        response = {'jobId': job_id, 'status': 'submitted'}
        return jsonify(**response)


@app.route('/<service>/docs', methods=['GET'])
def render_docs(service):
    with app.open_resource('static/docs/{}.md'.format(service)) as f:
        content = f.read()
    content = Markup(markdown(content, extras=['fenced-code-blocks']))
    print(content)
    return render_template('docs.html', **locals())


@app.route('/<service>/jobs/<job_id>', methods=['GET'])
def query_status(service, job_id):
    return jsonify(**query_job(job_id))


if __name__ == '__main__':
    app.run()
