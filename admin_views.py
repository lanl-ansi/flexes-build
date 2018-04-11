from flask import Blueprint, jsonify

admin = Blueprint('admin', __name__)

def members(db, key):
    return [val.decode() for val in db.smembers(key)]


@admin.route('/queues')
def queues():
    queues = {'queues': [queue.decode() for queue in db.smembers('queues')]}
    return jsonify(**queues)


@admin.route('/<queue>/jobs')
def jobs(queue):
    jobs = {'queue': queue, 
            'jobs': members(db, '{}:jobs'.format(queue))}
    return jsonify(**jobs)


@admin.route('/<queue>/jobs/running')
def running_jobs(queue):
    jobs = {'queue': queue, 
            'jobs': members(db, '{}:jobs:running'.format(queue))}
    return jsonify(**jobs)


@admin.route('/<queue>/workers')
def workers(queue):
    workers = {'queue': queue,
               'workers': members(db, '{}:workers'.format(queue))}
    return jsonify(**workers)


@admin.route('/<queue>/workers/busy')
def busy_workers(queue):
    workers = {'queue': queue,
               'workers': members(db, '{}:workers:busy'.format(queue))}
    return jsonify(**workers)
