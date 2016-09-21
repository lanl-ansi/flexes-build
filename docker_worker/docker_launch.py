import sys
import time
from docker import Client

client = Client(base_url='unix://var/run/docker.sock')
container = client.create_container(image='docker_worker', command=sys.argv[1])
container_id = container['Id']
response = client.start(container)
exited = False

while exited is False:
    print('still running')
    containers = client.containers(filters={'status': 'exited'})
    for c in containers:
        if c['Id'] == container_id:
            exited = True
            print(client.logs(container))
            client.remove_container(container)
            break
    time.sleep(1)
