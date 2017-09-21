FROM alpine

# Python3 + boto3
RUN apk --no-cache add python3
RUN mkdir /project
WORKDIR /project
RUN pip3 install --upgrade pip awscli boto3

# Make wget work with https
RUN apk --no-cache add ca-certificates openssl
RUN update-ca-certificates

RUN mkdir -p /bursa/bin

# CoreOS Container Linux Configuration Transpiler
RUN wget -O /usr/bin/ct https://github.com/coreos/container-linux-config-transpiler/releases/download/v0.4.2/ct-v0.4.2-x86_64-unknown-linux-gnu
RUN chmod +x /usr/bin/ct

COPY bursa.py /bursa/bin/bursa.py
RUN chmod +x /bursa/bin/bursa.py

RUN apk --no-cache add openssh-client

WORKDIR /bursa
CMD ["bin/bursa.py"]
