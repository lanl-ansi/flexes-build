#! /bin/sh

cwd=$(realpath $(dirname $0))

if [ "$1" == "--rebuild" ] || ! docker images | grep -q aws-python; then
  rebuild=true
fi

if [ -n "$rebuild" ]; then
  echo "==="
  echo "=== Rebuilding aws-python image..."
  echo "==="
  docker build \
    --tag aws-python \
    .
  echo "==="
  echo "=== Done rebuilding aws-python image"
  echo "==="
fi

docker run \
  --rm \
  -t \
  --volume $HOME/.aws:/root/.aws:ro \
  --volume $cwd:/project:ro \
  aws-python \
  bursa.py
