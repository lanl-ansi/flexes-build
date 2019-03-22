FROM python:3-alpine as build

COPY . /

RUN apk add --no-cache alpine-sdk && \
    pip install -e .[dev] && \
    py.test test/test_api_worker.py test/test_docker_worker.py

FROM docker

LABEL maintainer="James Arnold <arnold_j@lanl.gov>"

WORKDIR /src

COPY --from=build /README.rst /setup.py /src/
COPY --from=build /flexes_build/worker/ /src/flexes_build/worker/
COPY --from=build /flexes_build/config.py /flexes_build/default_config.json \
                  /flexes_build/message_schema.json /flexes_build/__init__.py \
                  /src/flexes_build/

RUN apk add --no-cache python3 python3-dev alpine-sdk && \
    python3 -m ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    rm -r /root/.cache && \
    pip install --no-cache-dir . && \
    pip uninstall -y aiohttp flask flask-redis flask-swagger-ui gunicorn && \
    apk del alpine-sdk python3-dev

ENTRYPOINT ["python3", "-m", "flexes_build.worker.docker_worker"]
