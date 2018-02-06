#!/bin/bash

mkdir dist
echo "Packaging Docker registry"
mkdir dist/docker-registry
docker save nginx:stable-alpine registry:2 | gzip > dist/docker-registry/docker-registry.tgz
cd ../docker-registry \
  && git checkout master \
  && git pull origin master \
  && cp nginx-ssl.conf docker-compose-ssl.yml config.yml create_config.py requirements.txt ../bursa/dist/docker-registry/
echo "Packaging lanlytics API server"
mkdir ../bursa/dist/lanlytics-api
cd ../lanlytics-api \
  && git checkout master \
  && git pull origin master \
  && docker-compose up -d --build \
  && docker-compose down \
  && cp nginx.conf docker-compose.yml ../bursa/dist/lanlytics-api/
docker save nginx:stable-alpine lanlyticsapi_flask | gzip > ../bursa/dist/lanlytics-api/lanlytics-api-server.tgz
echo "Packaging lanlytics API worker"
mkdir ../bursa/dist/lanlytics-api-worker
cd ../lanlytics-api-worker \
  && git checkout master \
  && git pull origin master \
  && docker build -t hub.lanlytics.com/lanlytics-api-worker:latest .
docker save hub.lanlytics.com/lanlytics-api-worker:latest | gzip > ../bursa/dist/lanlytics-api-worker/lanlytics-api-worker.tgz
cd ../bursa
tar zcf lanlytics-api-dist.tgz dist/
echo "Packaging complete"
