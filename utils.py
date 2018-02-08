import asyncio
import boto3
import botocore
import json
import sys
from aiohttp import ClientSession
from settings import *
from uuid import uuid4

def submit_job(db, message):
    job_id = str(uuid4())
    message['job_id'] = job_id
    message['status'] = 'submitted'
    queue = message['queue'] if 'queue' in message.keys() else 'docker'
    queue_message = json.dumps(message)
    # Remove command key from message for status queries
    if 'command' in message:
        message.pop('command')
    db.set(job_id, json.dumps(message))
    # Push to queue
    db.lpush(queue, queue_message)
    return job_id


def query_job(db, job_id):
    response = db.get(job_id)
    if response is not None:
        return json.loads(response.decode())
    else:
        dyn = boto3.resource('dynamodb')
        table = dyn.Table(TABLE_NAME)
        response = table.get_item(Key={'job_id': job_id})
        return response['Item']


def all_jobs():
    dyn = boto3.resource('dynamodb')
    table = dyn.Table(TABLE_NAME)
    response = table.scan(Select='ALL_ATTRIBUTES')
    return response['Items']


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
        url = '{}/v2/_catalog'.format(DOCKER_REGISTRY)
        services = await fetch(session, url)
        tasks = []
        for service in services['repositories']:
            url = '{}/v2/{}/tags/list'.format(DOCKER_REGISTRY, service)
            task = asyncio.ensure_future(fetch(session, url))
            tasks.append(task)

        return await asyncio.gather(*tasks)


async def fetch(session, url):
    async with session.get(url) as response:
        return await response.json()
