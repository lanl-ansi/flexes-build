FROM python:3-alpine

MAINTAINER James Arnold <arnold_j@lanl.gov>

COPY message_schema.json launch.py requirements.txt settings.py utils.py worker.py /src/
ADD test/ /src/test/

WORKDIR /src

RUN pip install -r requirements.txt && ls && py.test test/

VOLUME /usr/bin/docker
VOLUME /var/run/docker.sock

ENTRYPOINT ["python3", "worker.py"]

CMD ["-h"]
