FROM python:3-alpine

RUN mkdir /project
WORKDIR /project

RUN pip install --upgrade pip awscli boto3

ENTRYPOINT ["python3"]