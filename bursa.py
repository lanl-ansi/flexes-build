#! /usr/bin/python3

# Provision a controller node for a NISAC cloud deployment.
#
# Bursa (latin for "purse") is a fluid sac found near most joints.
# The best known bursae are those of the knee,
# or as I like to call them,
# "knee sacs"

import binascii
import boto3
import boto3.session
import botocore.exceptions
import socket
import os
import optparse
import random
import re
import shelve
import subprocess
import time
import json
import urllib.request
import warnings

class Deployment:
    def __init__(self, session, basename, config_dir, images_dir, ct_path):
        self.session = session
        self.ec2 = self.session.resource("ec2")
        self.basename = basename
        
        self.config_dir = config_dir
        self.images_dir = images_dir
        self.ct_path = ct_path
        
    def bursa_filename(self, ext):
        os.umask(0o77)
        dn = os.path.expanduser("~/.local/share/bursa")
        os.makedirs(dn, exist_ok=True)
        filename = os.path.join(dn, "%s.%s" % (self.basename, ext))
        return filename

    def log_item(self, name, desc=""):
        """Log that we're going to start working on something.
        
        Don't call this if your method only works on one thing.
        This is meant to illustrate that we're doing lots of important work,
        but flooding the output with "nisac" over and over
        isn't helpful.
        
        """
        
        print("  %-30s | %s" % (name, desc))

    def setup(self):
        """Figure out where to deploy, read user data"""
        try:
            iid = urllib.request.urlopen("http://169.254.169.254/latest/meta-data/instance-id").read().decode()
        except Exception as e:
            raise RuntimeError("Can't get instance ID: am I running on an EC2 instance?")
        self.myInstance = self.ec2.Instance(iid)
        self.myVpc = self.ec2.Vpc(self.myInstance.vpc_id)
            
    def transpile(self):
        """Transpile CoreOS Container Linux configurations"""
        
        self.configs = {}
        for cfg in ["default"]:
            self.log_item(cfg)
            yaml = open(os.path.join(self.config_dir, "%s.yaml" % cfg))
            transpile = subprocess.check_output([self.ct_path], stdin=yaml)
            self.configs[cfg] = transpile

    def make_bucket(self):
        """Create cloud storage buckets"""
        
        bucket_name = self.basename
        client = boto3.client("s3")
        try:
            client.get_bucket_location(Bucket=bucket_name)
            return
        except Exception as e:
            if e.response["Error"]["Code"] == 'AccessDenied':
                raise RuntimeError("Access denied listing bucket. Perhaps '%s' is already taken?" % bucket_name)
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
            return
        except:
            pass

        subnet = list(self.myVpc.subnets.all())[0]

        resp = client.create_cache_subnet_group(
            CacheSubnetGroupName=self.basename,
            CacheSubnetGroupDescription="Cache subnet for redis",
            SubnetIds=[subnet.id],
        )
        subnets = resp["CacheSubnetGroup"]["Subnets"]
        assert len(subnets) == 1
        subnetId = subnets[0]["SubnetIdentifier"]
        
        client.create_cache_cluster(
            CacheClusterId=redis_name,
            CacheSubnetGroupName=self.basename,
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

        
        # API-Worker
        roleName = "%s+API-Worker" % self.basename
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

        # S3-Full-Access
        roleName = "%s+S3-Full-Access" % self.basename
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
        
    def make_user(self):
        """Create IAM Users"""
        
        iam = boto3.resource("iam")
        
        # Docker-Registry
        userName = "%s-Docker-Registry" % self.basename
        userDesc = "Docker Registry"
        self.log_item(userName, userDesc)
        user = iam.User(userName)
        try:
            user.load()
        except:
            user.create()
        user.attach_policy(
            PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
        )
        
        accessKeyPath = self.bursa_filename("awskey")
        if not os.path.exists(accessKeyPath):
            self.log_item("DockerRegistryAccessKey")
            keyPair = user.create_access_key_pair()

            with open(accessKeyPath, "w") as f:
                f.write("%s %s" % (keyPair.access_key_id, keyPair.secret_access_key))

    def create_secgroup(self, client, groupName, desc):
        filters = [
            {
                "Name": "group-name",
                "Values": [groupName],
            },
            {
                "Name": "vpc-id",
                "Values": [self.myInstance.vpc_id],
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
        self.secgroupIds = {}
        
        services = (
            ("Management", [22], []),
            ("Redis", [], [6379]),
            ("Docker Registry", [], [80, 443]),
        )
        
        for service, cliports, srvports in services:
            for role in ("Server", "Clients"):
                groupName = "%s+%s-%s" % (basename, service, role)
                desc = "%s %s" % (service, role)
                self.log_item(groupName, desc)
                groupId = self.create_secgroup(client, groupName, desc)
                self.secgroupIds[groupName] = groupId
                if role == "Server":
                    srvGroupId = groupId
                else:
                    cliGroupId = groupId
            for port in srvports:
                try:
                    client.authorize_security_group_ingress(
                        GroupId=srvGroupId,
                        IpPermissions=[
                            {
                                "IpProtocol": "tcp",
                                "FromPort": port,
                                "ToPort": port,
                                "UserIdGroupPairs": [{"GroupId": cliGroupId}],
                            },
                        ],
                    )
                except botocore.exceptions.ClientError as e:
                    if e.response["Error"]["Code"] == "InvalidPermission.Duplicate":
                        # The rule we're trying to create already exists. Splendid!
                        pass
                    else:
                        raise e

            for port in cliports:
                try:
                    client.authorize_security_group_ingress(
                        GroupId=cliGroupId,
                        IpPermissions=[
                            {
                                "IpProtocol": "tcp",
                                "FromPort": port,
                                "ToPort": port,
                                "UserIdGroupPairs": [{"GroupId": srvGroupId}],
                            },
                        ],
                    )
                except botocore.exceptions.ClientError as e:
                    if e.response["Error"]["Code"] == "InvalidPermission.Duplicate":
                        # The rule we're trying to create already exists. Splendid!
                        pass
                    else:
                        raise e

    def get_image(self, nameGlobs):
        def numbers(img):
            vals = re.findall(r"[0-9]+", img.name)
            return [int(p) for p in vals]

        image = None
        for nameGlob in nameGlobs:
            images = self.ec2.images.filter(
                Filters=[
                    {
                        "Name": "name",
                        "Values": [nameGlob],
                    },
                    {
                        "Name": "virtualization-type",
                        "Values": ["hvm"],
                    }
                ]
            )
            images = list(images)
            images.sort(key=numbers)
            if images:
                return images[-1]
                
        raise KeyError("No images match")
        
    def make_keypair(self):
        """Create SSH keypair"""
        
        self.keyname = self.basename
        create = True
        self.pemFile = self.bursa_filename("pem")
        if os.path.exists(self.pemFile):
            keypairInfo = self.ec2.KeyPair(self.keyname)
            try:
                keypairInfo.load()
                create = False
            except:
                create = True

        if create:
            keypair = self.ec2.create_key_pair(KeyName=self.keyname)
            self.creds = keypair.key_material
            self.pemFile = self.bursa_filename("pem")
            open(self.pemFile, "w").write(self.creds)

    def create_instance(self, image, secGroups, instanceName, publicIp=False):
        instances = self.ec2.instances.filter(
            Filters=[
                {
                    "Name": "tag:Name",
                    "Values": [instanceName],
                }
            ]
        )
        instances = list(instances)
        if len(instances) > 1:
            raise RuntimeError("Multiple instances match this name")
        elif len(instances) == 1:
            pass
        else:
            subnet = list(self.myVpc.subnets.all())[0]
            instances = self.ec2.create_instances(
                InstanceType="t2.micro",
                MinCount=1,
                MaxCount=1,
                ImageId=image.id,
                KeyName=self.keyname,
                UserData=self.configs["default"],
                NetworkInterfaces=[
                    {
                        "DeviceIndex": 0,
                        "AssociatePublicIpAddress": publicIp,
                        "SubnetId": subnet.id,
                        "Groups": secGroups,
                    }
                ],
                TagSpecifications=[
                    {
                        "ResourceType": "instance",
                        "Tags": [
                            {
                                "Key": "Name",
                                "Value": instanceName
                            }
                        ]
                    }
                ]
            )
        instance = instances[0]
        return instance

    def make_instances(self):
        """Create EC2 Instances"""

        # Everybody gets CoreOS.
        image = self.get_image(["CoreOS-stable-*-hvm"])

        # DockerRegistry
        instanceName = "%s-DockerRegistry" % self.basename
        self.log_item(instanceName, "Private Docker registry")
        secGroups = [
            self.secgroupIds["%s+Management-Clients" % self.basename],
            self.secgroupIds["%s+Docker Registry-Server" % self.basename],
        ]
        self.dockerRegistry = self.create_instance(image, secGroups, instanceName)
        
        # WebApp
        instanceName = "%s-WebApp" % self.basename
        self.log_item(instanceName, "Main entry point to the engine")
        secGroups = [
            self.secgroupIds["%s+Management-Clients" % self.basename],
            self.secgroupIds["%s+Docker Registry-Clients" % self.basename],
            self.secgroupIds["%s+Redis-Clients" % self.basename],
        ]
        self.create_instance(image, secGroups, instanceName)
        
        # LinuxWorker
        instanceName = "%s-LinuxWorker" % self.basename
        self.log_item(instanceName, "Linux Worker: we probably don't need this, actually.")
        secGroups = [
            self.secgroupIds["%s+Management-Clients" % self.basename],
            self.secgroupIds["%s+Redis-Clients" % self.basename],
        ]
        self.create_instance(image, secGroups, instanceName)

        # Me!
        self.log_item("Myself", "Add this machine to Management Servers group")
        secGroups = set(g["GroupId"] for g in self.myInstance.security_groups)
        secGroups.add(self.secgroupIds["%s+Management-Server" % self.basename])
        self.myInstance.modify_attribute(
            Groups=list(secGroups)
        )

    def ssh(self, instance, command):
        return subprocess.check_output([
            "/usr/bin/ssh",
            "-i", self.pemFile,
            "-o", "StrictHostKeyChecking=no",
            instance.private_ip_address,
            command,
        ])
    def scp_up(self, instance, filename):
        return subprocess.check_output([
            "/usr/bin/scp",
            "-i", self.pemFile,
            "-o", "StrictHostKeyChecking=no",
            filename,
            "%s:" % instance.private_ip_address,
        ])
        
    def start_registry(self):
        """Start Docker registry"""
        
        if self.dockerRegistry.state != 16:
            self.log_item("wait_until_running", "Wait until the registry machine is up")
            self.dockerRegistry.wait_until_running()
            # Give it a little more time for sshd to generate keys and bind
            time.sleep(4)
        print(self.scp_up(self.dockerRegistry, "images/registry.tar"))
        print(self.ssh(self.dockerRegistry, "docker load < registry.tar"))
        print(self.ssh(self.dockerRegistry, "docker images"))

    def go_run(self, method, *args):
        name = method.__name__
        desc = method.__doc__
        
        print("%-25s | %s" % (name, desc))
        method(*args)

    def build(self):
        self.go_run(self.setup)

        self.go_run(self.transpile)
        self.go_run(self.make_bucket) # do this early, since the name must be globally unique
        self.go_run(self.make_redis)
        self.go_run(self.make_table)
        self.go_run(self.make_roles)
        self.go_run(self.make_user)
        self.go_run(self.make_secgroups)
        self.go_run(self.make_keypair)
        self.go_run(self.make_instances)
        self.go_run(self.start_registry)


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
    parser.add_option(
        "--basename",
        default="bursa",
        help="Base name for created resources in this ")
    parser.add_option(
        "--config",
        default="config/",
        help="Configuration directory"
    )
    parser.add_option(
        "--images",
        default="images/",
        help="Images directory"
    )
    parser.add_option(
        "--ct",
        default="ct",
        help="Path to ct executable"
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
    
    dpl = Deployment(session, options.basename,
        config_dir=options.config,
        images_dir=options.images,
        ct_path=options.ct,
    )
    dpl.build()

  
if __name__ == "__main__":
    main()
