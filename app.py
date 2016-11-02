import json
from flask import Flask, jsonify, \
                  render_template, request
from client import send_message, query_job, submit_job

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/<service>', methods=['POST'])
def post_job(service):
    message = request.get_json()
    job_id = send_message(message, service)
    submit_job(job_id, service)
    response = {'jobId': job_id, 'status': 'submitted'}
    return jsonify(**response)


@app.route('/<service>/jobs/<job_id>', methods=['GET'])
def query_status(service, job_id):
    status = query_job(job_id)
    response = {'jobId': job_id, 'status': status}
    return jsonify(**response)


if __name__ == '__main__':
    app.run()
