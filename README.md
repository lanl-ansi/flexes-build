# lanlytics-api
[![Build Status](https://ci.lanlytics.com/nisac/lanlytics-api.svg?token=RmFwLDimUxzrPXXq8Kti&branch=master)](https://ci.lanlytics.com/nisac/lanlytics-api)
[![codecov](https://cov.lanlytics.com/ghe/nisac/lanlytics-api/branch/master/graph/badge.svg)](https://cov.lanlytics.com/ghe/nisac/lanlytics-api)

Website for the lanlytics API

## Deployment
The web application can be deployed using [docker-compose](https://docs.docker.com/compose/). Once docker-compose is [installed](https://docs.docker.com/compose/install/) you can launch the application with the following:
```bash
$ docker-compose build
$ docker-compose up -d --force-recreate
```
to stop the application
```bash
$ docker-compose down
```
get logs for the containers
```bash
docker-compose logs
```
**Note: the server is configured to run on localhost so modifications may be needed for production** 
**Note: if the application is running in an AWS region besides us-gov-west-1 the docker-compose.yml will need to be modified** 
