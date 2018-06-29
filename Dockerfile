FROM docker

MAINTAINER James Arnold <arnold_j@lanl.gov>

COPY requirements.txt /src/

WORKDIR /src

RUN apk add --no-cache python3 && \
    python3 -m ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    rm -r /root/.cache && \
    pip install -r requirements.txt 
    
COPY default_config.json message_schema.json api_worker.py docker_worker.py config.py utils.py /src/
COPY test/ /src/test/

RUN py.test test/test_api_worker.py test/test_docker_worker.py

ENTRYPOINT ["python3", "docker_worker.py"]
