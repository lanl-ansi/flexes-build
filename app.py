import json
from flask import Flask, jsonify, \
                  render_template, request
from client import query_job, submit_job

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/<service>', methods=['POST'])
def post_job():
    message = request.get_json()
    job_id = submit_job(message, service)
    response = {'jobId': job_id, 'status': 'submitted'}
    return jsonify(**response)


@app.route('/<service>/jobs/<job_id>', methods=['GET'])
def query_job():
    status = query_job(job_id)
    response = {'jobId': job_id, 'status': status}
    return jsonify(**response)


if __name__ == '__main__':
#    app.run(host='0.0.0.0', debug=True)
    app.run(host='127.0.0.1', debug=True)
