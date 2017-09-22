Bursa
=====

Bursa is a lanlytics provisioning script.
After setting up AWS credentials,
running bursa will give you a fully-deployed lanlytics setup.


Getting Ready
-------------

### Access Key

You will need an access key.
We recommend creating an access key specifically for bursa.

Create an access key through the AWS console, under "IAM".
Navigate to the (admin) user to whom the key should be bound,
then in that user's "Security credentials" tab,
under the "Access keys" section,
select the "Create access key" button.

Download the `.csv` file to a safe location
(you may need it again later).
Open the `.csv` to obtain your "access key ID" and "secret access key".
You will use these values when running the setup script.

### Make a VPC

You can use the default VPC if you want,
or you can make a new VPC for lanlytics.
Bursa will put all the instances it creates
in whichever VPC the management server is in.

### Management Server

Create a management server in your VPC,
from which to run bursa,
and perform administrative tasks on your deployment.

We used CoreOS Container Linux on a `t2.nano` instance.


Dependencies
------------

Bursa has been tested on CoreOS-stable.
CoreOS Container Linux is a minimalistic self-upgrading Linux distribution,
made specifically for hosting containers.

Due to the constraints imposed by CoreOS Container Linux,
bursa only needs a few commants installed,
provided it has Internet access.

Required programs:

* `/bin/sh`
* `docker`
* `openssl`

Bursa should run fine in Ubuntu, Debian, Red Hat, Arch, Slackware,
or anything else that has these installed.


Setup Script
-------------

`setup.sh` sets up some bash aliases for debugging,
and creates the AWS credentials file.

Run it like this:

    export region=us-west-2 # or whatever region you want
    export aws_access_key_id=YOUR_ACCESS_KEY
    export aws_secret_access_key=YOUR_SECRET_KEY
    sh setup.sh


Running bursa
-------------

After you have set up your account, you can run bursa:

    sh bursa.sh YOUR_INSTANCE_BASENAME

Bursa stores important state information in `~/.local/share/bursa/`.