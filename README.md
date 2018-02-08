Bursa
=====

Bursa is a lanlytics provisioning script.
After packaging the components running `buildout.py` will give 
you a fully-deployed lanlytics API setup running in its own VPC.

Getting Ready
-------------

### Access Key

You will need an AWS IAM account with an access key.

Create an access key through the AWS console, under "IAM".
Navigate to the (admin) user to whom the key should be bound,
then in that user's "Security credentials" tab,
under the "Access keys" section,
select the "Create access key" button.

Download the `.csv` file to a safe location
(you may need it again later).
Open the `.csv` to obtain your "access key ID" and "secret access key".

The credentials should be stored in `~/.aws/credentials` along with the
default region where the resources will be deployed. More information 
can be found [here](https://docs.aws.amazon.com/cli/latest/userguide/cli-config-files.html).

### Python Environment

We recommend installing the required Python libraries in a virtual environment.

```bash
$ python3 -m venv env
$ source env/bin/activate
(env)$ pip install -U pip boto3
```

Packaging Script
-------------

`package-images.sh` collects the necessary files and compresses them into a
file called `lanlytics-api-dist.tgz`. The script assumes that the necessary
repositories are cloned in the same directory as the bursa repository.

* [docker-registry](https://github.lanlytics.com/SREs/docker-registry)
* [lanlytics-api](https://github.lanlytics.com/nisac/lanlytics-api)
* [lanlytics-api-worker](https://github.lanlytics.com/nisac/lanlytics-api-worker)
* [echo-test](https://github.lanlytics.com/SREs/echo-test)

Run it like this:

```bash
$ ./package-images.sh
```

Running buildout
-------------

After things are setup you are ready to run can run the buildout script:

```bash
$ source env/bin/activate
(env)$ ./buildout.py -h
```
