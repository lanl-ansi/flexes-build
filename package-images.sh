#!/bin/bash

cd ../lanlytics-api \
  && git checkout master \
  && git pull origin master \
  && docker-compose up -d --build \
  && docker-compose down
cd ../lanlytics-api-worker \
  && git checkout master \
  && git pull origin master \
  && docker build -t hub.lanlytics.com/lanlytics-api-worker:latest .
cd ../bursa
docker save nginx:stable-alpine registry:2 | gzip > docker-registry.tar.gz
docker save nginx:stable-alpine lanlyticsapi_flask | gzip > lanlytics-api-server.tar.gz
docker save hub.lanlytics.com/lanlytics-api-worker:latest | gzip > lanlytics-api-worker.tar.gz
