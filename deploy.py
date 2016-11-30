import subprocess
from git import Repo

def deploy():
    Repo('.').remotes.origin.pull()
    subprocess.call(['touch', 'production.wsgi'])

if __name__ == '__main__':
    deploy()
