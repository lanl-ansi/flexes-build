import json
from flask import Flask, jsonify, \
                  render_template, request
from client import send_message, query_job, submit_job

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/message', methods=['POST'])
def message():
    message = request.get_json()
    service = 'TestService'
    job_id = send_message(message, service)
    submit_job(job_id, service)
    response = {'jobId': job_id, 'status': 'success'}
    return jsonify(**response)


@app.route('/query-job', methods=['GET'])
def query():
    job_id = request.args.get('jobId')
    status = query_job(job_id)
    response = {'jobId': job_id, 'status': status}
    return jsonify(**response)


if __name__ == '__main__':
#    app.run(host='0.0.0.0', debug=True)
    app.run(host='127.0.0.1', debug=True)
