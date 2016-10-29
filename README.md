# Service Experiment
[![Build Status](https://ci.lanlytics.com/arnold/service-experiment.svg?token=RmFwLDimUxzrPXXq8Kti&branch=master)](https://ci.lanlytics.com/arnold/service-experiment)  
## Description
This project is an attempt to implement a robust architecture for deploying web 
services on AWS using [SQS](https://aws.amazon.com/sqs/) and [DynamoDB](https://aws.amazon.com/dynamodb/). 
The process is implemented as follows:

1. A client passes job parameters to a message queue
2. The message is posted to the queue and a unique message ID is returned
3. A job is added to a jobs database using the message ID as the primary key
4. The service worker polls the message queue containing jobs needing to be completed
5. If the worker can perform the job it begins processing the message
6. Once a service processes a message it deletes it from the queue
7. The worker updates the job's status in a database along with the job's results

The [docker folder](./docker_worker/) is an experiment for executing the model code 
inside of a Docker container. This separates the worker logic from the actual work. 
It also allows model developers to develop their model code in a Docker container 
without having to write any worker boilerplate for service deployment.

## Setup
The setup the demo you need:

1. Access to an AWS account
2. Permission to access SQS (the queue name is service-experiment)
3. Permission to access DynamoDB (table name is service experiment and the
   primary key is job_id)
4. [Docker](https://docker.io) installed

Once things are set up install the Python dependencies in a virtual
environment:

```bash
$ virtualenv -p python3 env
$ source env/bin/activate
(env) $ pip install -r requirements.txt
(env) $ deactivate
$
```

Build the worker Docker image:

```bash
$ cd docker_worker
$ docker build -t worker/test .
```

Start the worker polling the message queue:

```bash
$ source env/bin/activate
(env) $ python worker.py test-service 10
```

Open a new terminal window and start the client application:

```bash
$ source env/bin/activate
(env) $ python app.py
```

Open a web browser and navigate to `localhost:5000`
