FROM docker

MAINTAINER James Arnold <arnold_j@lanl.gov>

COPY default_config.json message_schema.json api_worker.py docker_worker.py requirements.txt config.py utils.py /src/
ADD test/ /src/test/

WORKDIR /src

RUN apk add --no-cache python3 && \
    python3 -m ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    rm -r /root/.cache && \
    pip install -r requirements.txt && ls && py.test test/

VOLUME /var/run/docker.sock

ENTRYPOINT ["python3", "docker_worker.py"]

CMD ["-h"]
