import sys
import time
from docker import Client


def launch_container(params):
    client = Client(base_url='unix://var/run/docker.sock', version='auto')
    container = client.create_container(image='worker/test', command=params)
    container_id = container['Id']
    response = client.start(container)
    exit_code = client.wait(container)

    if exit_code == 0:
        print('Container exited with 0')
        client.remove_container(container)
    else:
        print('Someting went wrong')
        raise RuntimeError(str(client.logs(container, tail=10),'utf-8'))


if __name__ == '__main__':
    launch_container(sys.argv[1])
