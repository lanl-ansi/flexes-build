import asyncio
import boto3
import botocore
import json
import sys
from config import load_config
from aiohttp import ClientSession
from uuid import uuid4

config = load_config()

def submit_job(db, message):
    job_id = str(uuid4())
    message['job_id'] = job_id
    message['status'] = 'submitted'
    queue = message['queue'] if 'queue' in message.keys() else 'docker'

    job = config['JOB_PREFIX'] + job_id
    # Create job db entry
    db.hmset(job, message)
    # Push to queue
    db.lpush(queue, json.dumps(message))
    db.sadd('{}:jobs'.format(queue), job_id)
    return job_id


def query_job_status(db, job_id):
    job = config['JOB_PREFIX'] + job_id
    status = db.hget(job, 'status')
    if status is not None:
        return {'job_id': job_id, 'status': status}
    else:
        return get_job_result(db, job_id)


def get_job_result(db, job_id):
    job = config['JOB_PREFIX'] + job_id
    result = db.hgetall(job)
    if result != {}:
        return result
    else:
        dyn = boto3.resource('dynamodb', endpoint_url=config['DYNAMODB_ENDPOINT'])
        table = dyn.Table(config['JOBS_TABLE'])
        response = table.get_item(Key={'job_id': job_id})
        return response['Item']


def parse_hashmap(db, name, keys):
    try:
        return dict(zip(keys, db.hmget(name, keys)))
    except Exception as e:
        return None


def job_messages(db, job_id):
    job = config['MESSAGE_PREFIX'] + job_id
    messages = db.get(job)
    return json.loads(messages) if messages is not None else []


def all_running_jobs(db):
    jobs = [parse_hashmap(db, job, ['job_id', 'status', 'queue']) 
            for job in db.keys(pattern='{}*'.format(config['JOB_PREFIX']))]
    return jobs


def all_queues(db):
    queues = [{'name': queue.replace(config['QUEUE_PREFIX'], ''), 'jobs': db.scard(queue)} 
              for queue in db.keys(pattern='{}*'.format(config['QUEUE_PREFIX']))] 
    return queues


def all_workers(db):
    workers = []
    for worker in db.keys(pattern='{}*'.format(config['WORKER_PREFIX'])):
        worker_id = worker.replace(config['WORKER_PREFIX'], '')
        workers.append({**{'id': worker_id}, **parse_hashmap(db, worker, ['status', 'queue'])})
    return workers


def list_services(tags=None):
    loop = asyncio.get_event_loop()
    responses = loop.run_until_complete(get_services())

    if tags is not None:
        services = {'services': []}
        for response in responses:
            t = [tag for tag in tags if tag in response['tags']]
            if len(t) > 0:
                response['tags'] = t
                services['services'].append(response) 
        return services
    else:
        return {'services': responses}


async def get_services():
    async with ClientSession() as session:
        url = 'https://{}/v2/_catalog'.format(config['DOCKER_REGISTRY'])
        services = await fetch(session, url)
        tasks = []
        for service in services['repositories']:
            url = 'https://{}/v2/{}/tags/list'.format(config['DOCKER_REGISTRY'], service)
            task = asyncio.ensure_future(fetch(session, url))
            tasks.append(task)

        return await asyncio.gather(*tasks)


async def fetch(session, url):
    async with session.get(url) as response:
        return await response.json()
