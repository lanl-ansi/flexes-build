FROM docker

MAINTAINER James Arnold <arnold_j@lanl.gov>

COPY message_schema.json launch.py requirements.txt settings.py utils.py worker.py /src/
COPY test/ /src/test/

WORKDIR /src

RUN apk add --no-cache python3 && \
    python3 -m ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    rm -r /root/.cache && \
    pip install -r requirements.txt && ls && py.test test/

ENTRYPOINT ["python3", "worker.py"]

CMD ["-h"]
