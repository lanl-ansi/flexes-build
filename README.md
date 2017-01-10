# lanlytics API worker

Code for launching workers to communicate with the lanlytics API queue

## Message Format

## Docker Workers
Docker workers are run inside of a Docker container and from a Docker image stored on the host machine. If the image is not present is can be retrieved from DockerHub or hub.lanlytics.com, this allows a single worker to handle a variety of services without having to launch specific workers for each service.
```bash
python3 worker.py generic
```
## Native Workers
Native workers are run locally on the host machine without any containerization.
```bash
python3 worker.py native --prefix ["python", "my_script.py"]
```
