#! /bin/sh

cwd=$(realpath $(dirname $0))

if [ "$1" == "--rebuild" ]; then
  docker build \
    --quiet \
    --tag aws-python \
    .
fi

docker run \
  --rm \
  -t \
  --volume $HOME/.aws:/root/.aws:ro \
  --volume $cwd:/project:ro \
  aws-python \
  bursa.py
