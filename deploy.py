import subprocess
from git import Repo

def deploy():
    repo = Repo('.')
    origin = repo.remotes.origin
    origin.pull()
    subprocess.call(['touch', 'production.wsgi'])


if __name__ == '__main__':
    deploy()
