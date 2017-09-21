#! /bin/sh

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 BASENAME"
    exit
fi

if [ $1 == "--fast" ]; then
    fast=1
    shift
fi

cd $(dirname $0)
basename=$1; shift

if [ -n "$fast" ]; then
    runargs="--volume $(pwd)/bursa.py:/bursa/bin/bursa.py:ro"
else
    echo "==="
    echo "=== Building images"
    echo "==="
    mkdir -p images
    
    {
        docker build --quiet --tag bursa .
        echo "Saving image"
        docker save -o images/bursa.zip bursa
    } | sed 's/^/bursa: /'
    
    for img in registry; do
        {
            docker pull $img
            echo "Saving image"
            docker save -o images/$img.tar $img
        } | sed "s/^/$img: /"
    done
    
    wait
fi

echo "==="
echo "=== Running bursa"
echo "==="
docker run \
  --rm \
  -t \
  --user $(id -u):$(id -g) \
  --env HOME=$HOME \
  --volume /etc/passwd:/etc/passwd:ro \
  --volume /etc/group:/etc/group:ro \
  --volume $(pwd)/images:/bursa/images:ro \
  --volume $(pwd)/config:/bursa/config:ro \
  --volume $HOME:$HOME \
  $runargs \
  bursa \
  python3 /bursa/bin/bursa.py --config /bursa/config --images /bursa/images --basename $basename "$@"
