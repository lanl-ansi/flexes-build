import boto3
import json


def send_message(msg, service):
    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName='service-experiment')
    resp = queue.send_message(MessageBody=json.dumps(msg),
                              MessageAttributes={'Service': {'StringValue': service, 
                                                             'DataType': 'String'}})
    return resp.get('MessageId')


def receive_message(service):
    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName='service-experiment')
    message = None

    # Process message with optional Service attribute
    for msg in queue.receive_messages(MessageAttributeNames=['Service']):
        if msg.message_attributes is not None:
            service_name = msg.message_attributes.get('Service').get('StringValue')
            if service_name == service:
                message = msg.body
                msg_id = msg.message_id
                msg.delete()
                break
    return message, msg_id
                

def main():
    msg = {'foo': 'bar'}
    job_id = send_message(msg, 'TestService')
    print(job_id)
    received_msg = receive_message('TestService')
    print(received_msg)


if __name__ == '__main__':
    main()
    
