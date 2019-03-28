FROM python:3-alpine as build

LABEL maintainer="James Arnold <arnold_j@lanl.gov>"

COPY . /

RUN apk add --no-cache alpine-sdk && \
    pip install -e .[dev] && \
    py.test test/test_server.py


FROM python:3-alpine

# Create non-root user and install dependencies
RUN addgroup -S flask && adduser -S -g flask flask

ENV APP_DIR /home/flask/flexes_build
WORKDIR $APP_DIR/

COPY --from=build /README.rst /setup.py ../
COPY --from=build /flexes_build/server/ ./server/
COPY --from=build /flexes_build/config.py /flexes_build/default_config.json \
                  /flexes_build/message_schema.json /flexes_build/__init__.py \
                  ./

RUN apk add --no-cache alpine-sdk && \
    pip install --no-cache-dir ../ && \
    apk del alpine-sdk

USER flask
