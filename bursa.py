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
import json
import urllib.request


class Deployment:
    def __init__(self, session, basename):
        self.session = session
        self.ec2 = self.session.resource("ec2")
        self.basename = basename

    def log_item(self, name, desc=""):
        """Log that we're going to start working on something.
        
        Don't call this if your method only works on one thing.
        This is meant to illustrate that we're doing lots of important work,
        but flooding the output with "nisac" over and over
        isn't helpful.
        
        """
        
        print("  %-30s | %s" % (name, desc))

    def setup(self):
        """Figure out where to deploy"""
        try:
            iid = urllib.request.urlopen("http://169.254.169.254/latest/meta-data/instance-id").read().decode()
        except Exception as e:
            raise RuntimeError("Can't get instance ID: am I running on an EC2 instance?")
        self.myInstance = self.ec2.Instance(iid)
        self.myVpc = self.ec2.Vpc(self.myInstance.vpc_id)

    def make_bucket(self):
        """Create cloud storage buckets"""
        
        bucket_name = self.basename
        client = boto3.client("s3")
        try:
            client.get_bucket_location(Bucket=bucket_name)
        except: # XXX: is there no way to catch only the Not Owned By You exception?
            client.create_bucket(
                Bucket=bucket_name,
                ACL="private",
                CreateBucketConfiguration={
                    "LocationConstraint": self.session.region_name
                },
            )

    def make_redis(self):
        """Create data structure store"""
        
        redis_name = self.basename
        client = boto3.client("elasticache")
        try:
            client.describe_cache_clusters(CacheClusterId=redis_name)
        except:
            client.create_cache_cluster(
                CacheClusterId=redis_name,
                NumCacheNodes=1,
                CacheNodeType="cache.t2.micro",
                Engine="redis",
            )
            
    def make_table(self):
        """Create NoSQL database table"""
        
        table_name = self.basename
        client = boto3.client("dynamodb")
        try:
            client.describe_table(TableName=table_name)
        except:
            response = client.create_table(
                TableName=table_name,
                AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
                KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            
    def make_roles(self):
        """Set up authentication roles"""
        
        role_prefix = self.basename
        client = boto3.client("iam")
        
        policyDoc = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                },
            ]
        }

        
        # Make API-Worker
        roleName = "%s+API-Worker" % role_prefix
        roleDesc = "Allows API workers to access S3 and DynamoDB"
        self.log_item(roleName, roleDesc)
        try:
            role = client.get_role(RoleName=roleName)
        except:
            role = None

        if not role:
            client.create_role(
                RoleName=roleName,
                AssumeRolePolicyDocument=json.dumps(policyDoc),
                Description=roleDesc,
            )
        client.attach_role_policy(
            RoleName=roleName,
            PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
        )
        client.attach_role_policy(
            RoleName=roleName,
            PolicyArn="arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess",
        )

        # Make S3-Full-Access
        roleName = "%s+S3-Full-Access" % role_prefix
        roleDesc = "Allows full access to S3"
        self.log_item(roleName, roleDesc)
        try:
            role = client.get_role(RoleName=roleName)
        except:
            role = None
            
        if not role:
            client.create_role(
                RoleName=roleName,
                AssumeRolePolicyDocument=json.dumps(policyDoc),
                Description=roleDesc,
            )
        client.attach_role_policy(
            RoleName=roleName,
            PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
        )
    
    def create_secgroup(self, client, groupName, desc):
        filters = [
            {
                "Name": "group-name",
                "Values": [groupName],
            }
        ]
        resp = client.describe_security_groups(Filters=filters)
        groups = resp['SecurityGroups']
        if not groups:
            group = client.create_security_group(
                GroupName=groupName,
                Description=desc,
                VpcId=self.myVpc.id,
            )
            return group["GroupId"]
        elif len(groups) > 1:
            raise RuntimeError("Security Group %s: Multiple groups with this name" % groupName)
        else:
            return groups[0]["GroupId"]
        raise RuntimeError("Security Group %s: Unable to determine GroupID" % groupName)

    def make_secgroups(self):
        """Establish network security groups"""

        basename = self.basename
        client = boto3.client("ec2")
        services = (
            ("Redis", [6379]),
            ("Docker Registry", [80, 443]),
        )
        
        self.secgroupIds = {}
        for service, ports in services:
            for role in ("Server", "Clients"):
                groupName = "%s+%s-%s" % (basename, service, role)
                desc = "%s %s" % (service, role)
                self.log_item(groupName, desc)
                groupId = self.create_secgroup(client, groupName, desc)
                self.secgroupIds[groupName] = groupId
                if role == "Server":
                    serverGroup = groupId
                else:
                    clientGroup = groupId
            for port in ports:
                try:
                    client.authorize_security_group_ingress(
                        GroupId=serverGroup,
                        IpPermissions=[
                            {
                                "IpProtocol": "tcp",
                                "FromPort": port,
                                "ToPort": port,
                                "UserIdGroupPairs": [{"GroupId": clientGroup}],
                            },
                        ],
                    )
                except botocore.exceptions.ClientError as e:
                    if e.response["Error"]["Code"] == "InvalidPermission.Duplicate":
                        # The rule we're trying to create already exists. Splendid!
                        pass
                    else:
                        raise e

    def go_run(self, method, *args):
        name = method.__name__
        desc = method.__doc__
        
        print("%-25s | %s" % (name, desc))
        method(*args)

    def build(self):
        self.go_run(self.setup)

        self.go_run(self.make_bucket)
        self.go_run(self.make_redis)
        self.go_run(self.make_table)
        self.go_run(self.make_roles)
        self.go_run(self.make_secgroups)


def setup():
  # Set up proxy if we"re at LANL
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
    
    dpl = Deployment(session, "nisac")
    dpl.build()

  
if __name__ == "__main__":
    main()
