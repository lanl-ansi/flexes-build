# Service Experiment
An experimental architecture for web services

## Description
This project is an attempt to implement a robust architecture for deploying web services on AWS using [SQS](https://aws.amazon.com/sqs/) and [DynamoDB](https://aws.amazon.com/dynamodb/). The process is implemented as follows:

1. A client passes job parameters to a message queue
2. The message is posted to the queue and a unique message ID is returned
3. A job is added to a jobs database using the message ID as the primary key
4. The service worker polls the message queue containing jobs needing to be completed
5. If the worker can perform the job it begins processing the message
6. Once a service processes a message it deletes it from the queue
7. The worker updates the job's status in a database along with the job's results
