import sys
import time
from docker import Client


def launch_container(params):
    client = Client(base_url='unix://var/run/docker.sock')
    container = client.create_container(image='docker_worker', command=params)
    container_id = container['Id']
    response = client.start(container)
    result = None

    while result is None:
        print('still running')
        containers = client.containers(filters={'status': 'exited'})
        for c in containers:
            if c['Id'] == container_id:
                exited = True
                result = client.logs(container)
                client.remove_container(container)
                break
        time.sleep(1)
    return result


if __name__ == '__main__':
    launch_container(sys.argv[1])
