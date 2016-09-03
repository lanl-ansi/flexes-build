import boto3

def query_job(job_id):
    db = boto3.resource('dynamodb')
    table = db.Table('service-experiment')
    response = table.get_item(Key={'job_id': job_id})
    job = response['Item']
    return job['status']


def update_job(job_id):
    db = boto3.resource('dynamodb')
    table = db.Table('service-experiment')
    table.update_item(Key={'job_id': job_id},
                      UpdateExpression='SET #job_status = :val1',
                      ExpressionAttributeNames={'#job_status': 'status'},
                      ExpressionAttributeValues={':val1': 'complete'})


def submit_job(job_id, service):
    db = boto3.resource('dynamodb')
    table = db.Table('service-experiment')
    table.put_item(Item={
        'job_id': job_id,
        'service': service,
        'result': None,
        'status': 'submitted'
    })
