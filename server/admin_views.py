from flask import Blueprint, jsonify

admin = Blueprint('admin', __name__)

@admin.route('/queues')
def queues():
    queues = {'queues': [queue for queue in db.smembers('queues')]}
    return jsonify(**queues)


@admin.route('/<queue>/jobs')
def jobs(queue):
    jobs = {'queue': queue, 
            'jobs': db.smembers('{}:jobs'.format(queue))}
    return jsonify(**jobs)


@admin.route('/<queue>/jobs/running')
def running_jobs(queue):
    jobs = {'queue': queue, 
            'jobs': db.smembers('{}:jobs:running'.format(queue))}
    return jsonify(**jobs)


@admin.route('/<queue>/workers')
def workers(queue):
    workers = {'queue': queue,
               'workers': db.smembers('{}:workers'.format(queue))}
    return jsonify(**workers)


@admin.route('/<queue>/workers/busy')
def busy_workers(queue):
    workers = {'queue': queue,
               'workers': db.smembers('{}:workers:busy'.format(queue))}
    return jsonify(**workers)
