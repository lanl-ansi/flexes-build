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


class Deployment:
    def __init__(self, session):
        self.session = session
        self.ec2 = self.session.resource("ec2")

    def log_item(self, name, desc=""):
        """Log that we're going to start working on something.
        
        Don't call this if your method only works on one thing.
        This is meant to illustrate that we're doing lots of important work,
        but flooding the output with "nisac" over and over
        isn't helpful.
        
        """
        
        print("  %-30s | %s" % (name, desc))

    def make_vpc(self, vpc_name):
        """Create machine group for this service"""
        
        cidr_block = "10.33.0.0/16"
        filters = [{"Name": "tag:Name", "Values": [vpc_name]}]
        vpcs = list(self.ec2.vpcs.filter(Filters=filters))
        if len(vpcs) == 1:
            self.vpc = vpcs[0]
            assert self.vpc.cidr_block == cidr_block
        elif len(vpcs) > 1:
            raise RuntimeError("You have more than one VPC named %s" % vpc_name)
        else:
            # Let"s get to making this VPC
            self.vpc = self.ec2.create_vpc(CidrBlock=cidr_block)
            self.vpc.create_tags(Tags=[{"Key": "Name", "Value": vpc_name}])

        # Enable external DNS for this VPC
        self.vpc.modify_attribute(EnableDnsHostnames={"Value": True})
        
    def make_bucket(self, bucket_name):
        """Create cloud storage buckets"""
        
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

    def make_redis(self, redis_name):
        """Create data structure store"""
        
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
            
    def make_table(self, table_name):
        """Create NoSQL database table"""
        
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
            
    def make_roles(self, role_prefix):
        """Set up authentication roles"""
        
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
                VpcId=self.vpc.id,
            )
            return group["GroupId"]
        else:
            for group in groups:
               if group["GroupName"] == groupName:
                 return group["GroupId"]
        raise RuntimeError("Security Group %s: Unable to determine GroupID" % groupName)

    def make_secgroups(self, basename):
        """Establish network security groups"""

        client = boto3.client("ec2")
        services = (
            ("Redis", [6379]),
            ("Docker Registry", [80,443]),
            ("Management", [22]),
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
    
    def update_default_secgroup(self):
        """Update default security group to allow access from management server"""
        
        pass

    def go_run(self, method, *args):
        name = method.__name__
        desc = method.__doc__
        
        print("%-25s | %s" % (name, desc))
        method(*args)

    def build(self):
        name = "nisac"
        self.go_run(self.make_vpc, name)
        self.go_run(self.make_bucket, name)
        self.go_run(self.make_redis, name)
        self.go_run(self.make_table, name)
        self.go_run(self.make_roles, name)
        self.go_run(self.make_secgroups, name)
        self.go_run(self.update_default_secgroup)


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
    
    dpl = Deployment(session)
    dpl.build()

  
if __name__ == "__main__":
    main()
