# lanlytics API worker

Code for launching workers to communicate with the lanlytics API queue

## Message Format
Messages come from the client in JSON format.
```json
{
  "stdin": "s3://bucket/path/to/stdin.txt",
  "stdout": "s3://bucket/path/to/stdout.txt",
  "stderr": "s3://bucket/path/to/stderr.txt",
  "command": [
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
  ]
}
```
`stdin`, `stdout`, `stderr` parameters will write the output from the respective streams out to file and stored on S3 at the specified path.

Commands are fed to the worker in the order they are supplied to accomodate positional arguments. If a flag for the argument isn't needed the `name` parameter is optional. The `input` and `output` types expect a file URI, the worker will download/upload the necessary files locally and resolve the local path for execution.

## Docker Workers
Docker workers are run inside of a Docker container and from a Docker image stored on the host machine. 
If the image is not present it can be retrieved from DockerHub or hub.lanlytics.com, this allows a 
single worker to handle a variety of services without having to launch specific workers for each service.
```bash
python3 worker.py generic
```
## Native Workers
Native workers are run locally on the host machine without any containerization.
```bash
python3 worker.py native ["python", "my_script.py"]
```
