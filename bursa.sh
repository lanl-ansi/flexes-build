#! /bin/sh

set -e

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

for cfg in default; do
  yaml=$cfg.cfg.yaml
  json=$cfg.cfg.json
  if [ $yaml -nt $json ]; then
    echo "=== Retranspiling $yaml"
    docker run -i --rm johnt337/container-linux-config-transpiler:alpine-test <$yaml >$json
    if ! grep -q . $json; then
        rm $json
        echo "ERROR: empty output"
        exit 1
    fi
  fi
done

docker run \
  --rm \
  -t \
  --user $(id -u):$(id -g) \
  --env HOME=$HOME \
  --volume $cwd:/project:ro \
  --volume $HOME:$HOME \
  aws-python \
  bursa.py "@"
