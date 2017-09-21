#! /bin/sh

set -e

if [ $? -eq 0 ]; then
    echo "Usage: $0 BASENAME"
fi

cd $(dirname $0)
basename=$1; shift


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

echo "==="
echo "=== Running bursa"
echo "==="
docker run \
  --rm \
  -t \
  --user $(id -u):$(id -g) \
  --env HOME=$HOME \
  --volume $(pwd)/images:/bursa/images:ro \
  --volume $(pwd)/config:/bursa/config:ro \
  --volume $HOME:$HOME \
  bursa \
  /bursa/bin/bursa.py --config /bursa/config --images /bursa/images --basename $basename "$@"
