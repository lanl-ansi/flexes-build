FROM python:3-alpine

LABEL maintainer="James Arnold <arnold_j@lanl.gov>"

# Create non-root user
RUN addgroup -S flask && adduser -S -g flask flask

# Copy files
ENV APP_DIR /home/flask/lanlytics-api
WORKDIR $APP_DIR/

COPY app.py requirements.txt utils.py config.py default_config.json message_schema.json $APP_DIR/
COPY static/ $APP_DIR/static/
COPY templates/ $APP_DIR/templates/
COPY test/ $APP_DIR/test/

RUN apk add --no-cache alpine-sdk && \
    pip install -U --no-cache-dir pip && \
    pip install --no-cache-dir -r requirements.txt && py.test test/ && \
    apk del alpine-sdk

USER flask
