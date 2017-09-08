#! /usr/bin/python3

# Provision a controller node for a NISAC cloud deployment.
#
# Bursa (latin for "purse") is a fluid sac found near most joints.
# The best known bursae are those of the knee,
# or as I like to call them,
# "knee sacs"

import boto3
import boto3.session
import botocore.exceptions
import socket
import os
import optparse
import random


class Deployment:
    def __init__(self, session):
        self.session = session
        self.ec2 = self.session.resource("ec2")

    def make_vpc(self, vpc_name):
        cidr_block = "10.33.0.0/16"
        filters = [{"Name": "tag:Name", "Values": [vpc_name]}]
        vpcs = list(self.ec2.vpcs.filter(Filters=filters))
        if len(vpcs) == 1:
            self.vpc = vpcs[0]
            assert self.vpc.cidr_block == cidr_block
        elif len(vpcs) > 1:
            raise RuntimeError("You have more than one VPC named %s" % vpc_name)
        else:
            # Let's get to making this VPC
            self.vpc = self.ec2.create_vpc(CidrBlock=cidr_block)
            self.vpc.create_tags(Tags=[{"Key": "Name", "Value": vpc_name}])

        # Enable external DNS for this VPC
        self.vpc.modify_attribute(EnableDnsHostnames={"Value": True})
        
    def make_bucket(self, bucket_name):
        s3 = boto3.client("s3")
        try:
            s3.get_bucket_location(Bucket=bucket_name)
        except: # XXX: is there no way to catch only the Not Owned By You exception?
            s3.create_bucket(
                Bucket=bucket_name,
                ACL='private',
                CreateBucketConfiguration={
                    "LocationConstraint": self.session.region_name
                },
            )

    def make_redis(self, redis_name):
        elasticache = boto3.client("elasticache")
        try:
            elasticache.describe_cache_clusters(CacheClusterId=redis_name)
        except:
            elasticache.create_cache_cluster(
                CacheClusterId=redis_name,
                NumCacheNodes=1,
                CacheNodeType='cache.t2.micro',
                Engine='redis',
            )

    def build(self):
        name = "nisac"
        self.make_vpc(name)
        self.make_bucket(name)
        self.make_redis(name)


def setup():
  # Set up proxy if we're at LANL
    fqdn = socket.getfqdn()
    if fqdn.endswith("lanl.gov"):
        proxy = "http://proxyout.lanl.gov:8080/"
        os.environ["HTTP_PROXY"] = proxy
        os.environ["HTTPS_PROXY"] = proxy


def parse_options():
    parser = optparse.OptionParser()
    parser.add_option(
        "--access-key-id", dest="access_key_id",
        default=None,
        help="AWS Access Key ID"
    )
    parser.add_option(
        "--secret-access-key", dest="secret_access_key",
        default=None,
        help="AWS Secret Access Key"
    )
    parser.add_option(
        "--region", dest="region",
        default=None,
        help="AWS Region"
    )
    
    options, args = parser.parse_args()
    return (options, args)


def main():
    setup()
    options, args = parse_options()
    
    session = boto3.session.Session(
    aws_access_key_id=options.access_key_id,
    aws_secret_access_key=options.secret_access_key,
        region_name=options.region
    )
    
    dpl = Deployment(session)
    dpl.build()

  
if __name__ == "__main__":
    main()
