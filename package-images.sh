#!/bin/bash

DOCKER_VERSION=17.12.0
DOCKER_COMPOSE_VERSION=1.18.0

echo "Downloading Docker binaries"
mkdir dist
mkdir dist/docker
curl -L https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-Linux-x86_64 -o dist/docker/docker-compose
curl -L https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_VERSION}-ce.tgz -o dist/docker/docker.tgz
curl -L https://raw.githubusercontent.com/tianon/cgroupfs-mount/master/cgroupfs-mount -o dist/docker/cgroupfs-mount
cp docker.service dist/docker/

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
  && cp nginx-ssl.conf docker-compose-ssl.yml ../bursa/dist/lanlytics-api/
docker save nginx:stable-alpine lanlyticsapi_flask | gzip > ../bursa/dist/lanlytics-api/lanlytics-api-server.tgz
echo "Packaging lanlytics API worker"
mkdir ../bursa/dist/lanlytics-api-worker
cd ../lanlytics-api-worker \
  && git checkout master \
  && git pull origin master \
  && docker build -t hub.lanlytics.com/lanlytics-api-worker:latest .
docker save hub.lanlytics.com/lanlytics-api-worker:latest | gzip > ../bursa/dist/lanlytics-api-worker/lanlytics-api-worker.tgz
cd ../bursa/dist/
tar cf docker.tar docker/ && rm -r docker
tar cf docker-registry.tar docker-registry/ && rm -r docker-registry
tar cf lanlytics-api.tar lanlytics-api/ && rm -r lanlytics-api
tar cf lanlytics-api-worker.tar lanlytics-api-worker/ && rm -r lanlytics-api-worker
tar zcf ../lanlytics-api-dist.tgz docker.tar docker-registry.tar lanlytics-api.tar lanlytics-api-worker.tar
cd ../ && rm -r dist/
echo "Packaging complete"
