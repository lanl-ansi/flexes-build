# lanlytics API worker
[![Build Status](https://ci.lanlytics.com/nisac/lanlytics-api-worker.svg?token=RmFwLDimUxzrPXXq8Kti&branch=master)](https://ci.lanlytics.com/nisac/lanlytics-api-worker)
[![codecov](https://cov.lanlytics.com/ghe/nisac/lanlytics-api-worker/branch/master/graph/badge.svg)](https://cov.lanlytics.com/ghe/nisac/lanlytics-api-worker)

Code for launching workers to communicate with the lanlytics API queue

## Message Format
Messages come from the client in JSON format.
```json
{
  "test": true,
  "service": "my_service",
  "queue": "docker",
  "command": {
    "stdin": {
      "type":"pipe",
      "value":"raw input data"
    },
    "stdout": {
      "type":"pipe",
      "value":null
    },
    "stderr": {
      "type":"uri",
      "value":"s3://bucket/path/to/stderr.txt"
    },
    "arguments":[
      {
        "type": "input",
        "name": "--infile",
        "value": "s3://bucket/path/to/input.txt"
      },
      {
        "type": "parameter",
        "name": "--arg1",
        "value": "myargvalue"
      },
      {
        "type": "output",
        "name": "--outfile",
        "value": "s3://bucket/path/to/output.txt"
      }
    ],
    "input": ["s3://bucket/path/to/some/input"],
    "output": ["s3://bucket/path/to/some/output"]
  }
}
```

`test` is used to see if there is a worker that is listening to a particular endpoint.

`stdin`, `stdout`, `stderr` parameters will write the output from the respective streams out to file and stored on S3 at the specified path.

Commands are fed to the worker in the order they are supplied to accomodate positional arguments. If a flag for the argument isn't needed the `name` parameter is optional. The `input` and `output` types expect a file URI, the worker will download/upload the necessary files locally and resolve the local path for execution.

`input` and `output` are used to fetch additional files that don't appear in `commands`. The S3 URI can accomodate the use of a prefix so that all files that match the prefix are downloaded/uploaded. For example if the command uses a shapefile (`--input poly.shp`) the accompanying files also need to be downloaded for the shapefile to be valid. You would need to add `"input":["s3://bucket/path/to/poly"]` to ensure all of the necessary files are downloaded. 

## Docker Workers
Docker workers are run inside of a Docker container and from a Docker image stored on the host machine. 
If the image is not present it can be retrieved from DockerHub or hub.lanlytics.com, this allows a 
single worker to handle a variety of services without having to launch specific workers for each service.
```bash
$ python3 worker.py docker
```
## Native Workers
Native workers are run locally on the host machine without any containerization.
```bash
$ python3 worker.py native ["python", "my_script.py"]
```
## Start Worker on Boot
1. Place the `api-worker.service` file in the `/lib/systemd/system/` directory
2. Activate the service
```bash
$ sudo systemctl daemon-reload
$ sudo systemctl enable api-worker.service
# reboot
$ sudo reboot
# check service status
$ sudo systemctl status api-worker.service
```
## Docker
The worker can also be run inside of a Docker container for easy deployment. To run the worker using Docker you can either pull the image from the Docker Registry or build it locally and run it. Once the image is on the host machine you can run it with the following command:
```bash
docker run -d -e AWS_DEFAULT_REGION=us-gov-west-1 --env HOME -v /<host-home-directory>:/<host-home-directory> -v /var/run/docker.sock:/var/run/docker.sock hub.lanlytics.com/lanlytics-api-worker
```
