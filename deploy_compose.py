import boto3
import docker
import os
import subprocess
from argparse import ArgumentParser

def download_images(images, dest=''):
    s3 = boto3.resource('s3')

    local_images = []
    for image in images:
        bucket, key = parse_s3_uri(image)
        local_file = os.path.join(dest, os.path.basename(key))
        bucket.download_file(key, dest)
        local_images.append(local_file)
    return local_images


def extract_images(images):
    client = docker.DockerClient(base_url='unix://var/run/docker.sock', version='auto')

    for image in images:
        with open(image, 'rb') as f:
            client.images.load(f)
        print('{} loaded'.format(image))


def launch_application():
    subprocess.call('docker-compose up -d --force-recreate', shell=True)


def deploy_application(images, dest=''):
    local_images = download_images(images, dest)
    extract_images(local_images)
    launch_application()


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-i', '--images', nargs='+', help='List of image URIs on S3')
    parser.add_argument('-d', '--dest', default='', help='Destination folder for downloaded images')
    args = parser.parse_args()
    deploy_application(args.images, args.dest)
