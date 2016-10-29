import boto3
import json
import os
import sys
import time
from docker import Client


def append_command(cmd, arg_name, arg_value):
    if cmd is not None:
        cmd = ' '.join([cmd, arg_name, arg_value])
    else:
        cmd = ' '.join([arg_name, arg_value])
    return cmd


def resolve_input(filename):
    in_path = '/home/ec2-user/input'
    if filename.startswith('s3://'):
        s3 = boto3.resource('s3')
        path = filename.split('//')[1]
        basename = os.path.basename(filename)
        bucket = s3.Bucket(path.split('/')[0])
        if os.path.splitext(filename)[1] == '.shp':
            aoi = os.path.join(in_path, basename)
            folder = path.split('/')[1:-1] 
            name = os.path.splitext(basename)[0]        
            for obj in bucket.objects.filter(Prefix=folder):
                if os.path.splitext(os.path.basename(obj.key))[0] == name:
                    s3.download_file(bucket, obj.key, os.path.join(in_path, 
                                                                   os.path.basename(obj.key)))
        elif os.path.splitext(filename)[1] in ['.json', '.geojson']:
            aoi = os.path.join(in_path, basename)
            bucket.download_file(path.split('/')[1:], aoi)
        else:
            raise ValueError('File type {} not supported'.format(os.path.splitext(filename)))
    elif (filename.startswith('{')
             or os.path.splitext(filename)[1] 
                 in ['.shp', '.json', '.geojson']):
        aoi = filename
    else:
        raise ValueError('Input file not supported\nMust be .shp, .json, .geojson or json string')
    return aoi


def parse_params(params):
    aoi = resolve_input(params['aoi'])
    cmd = None
    if 'fields' in params.keys():
        cmd = '--fields="{}"'.format(params['fields'])    
    if 'bin' in params.keys():
        cmd = append_command(cmd, '--bin', params['bin'])
    if 'disaggregation' in params.keys():
        cmd = append_command(cmd, '--disag', params['disaggregation'])
    if 'output' in params.keys():
        cmd = append_command(cmd, '--output', params['output'])
    if cmd is None:
        cmd = aoi
    else:
        cmd = '{} {}'.format(aoi, cmd)
    return cmd


def launch_container(params, job_id):
    client = Client(base_url='unix://var/run/docker.sock', version='auto')
    params = json.loads(params)
    params['output'] = os.path.join('/root/output', '{}.json'.format(job_id))    
    cmd = parse_params(params)    
    print(cmd)
    input_volume = '/home/ec2-user/input'
    output_volume = '/home/ec2-user/output'
    binds = ['{}:/root/input'.format(input_volume), '{}:/root/output'.format(output_volume)]
    container = client.create_container(image='worker/popecon', command=cmd,
                                        volumes=['/root/input', '/root/outputput'],
                                        host_config=client.create_host_config(binds=binds))
    client.start(container)
    exit_code = client.wait(container)
    print('Exit code: {}'.format(exit_code))

    if exit_code == 0:
        client.remove_container(container)
        return os.path.join(output_volume, '{}.json'.format(job_id))
    else:
        e = str(client.logs(container, tail=10),'utf-8')
        client.remove_container(container)
        raise RuntimeError(e)

if __name__ == '__main__':
    print(sys.argv[1])
    print(sys.argv[2])
    launch_container(sys.argv[1], sys.argv[2])
