#! /bin/sh

## Sets up your environment for running bursa.py

##
## This script must be idempotent!
##
## That means if it stops halfway through,
## you need to be able to run it again and have it pick up where it left off,
## without making any additional changes.
##

doing () {
  echo "==== $@"
}

## You're meant to drop these aliases into other scripts.

alias docker-compose="docker run \
    --rm \
    --volume /var/run/docker.sock:/var/run/docker.sock \
    --volume $cwd:/rootfs/$cwd \
    --workdir /rootfs/$cwd \
    docker/compose:1.15.0 \
"

alias aws="docker run \
    --interactive \
    --tty \
    --rm \
    --volume $HOME/.aws:/root/.aws:ro \
    anigeo/awscli \
"

dumpAliases () {
  echo "# Auto-generated by $0"
  echo "# If you make changes to this file, they are probably going to get blown away."
  awk '
    ($1=="alias") {
      d=1
    }

    (d) {
      print
    }

    ($0=="\"") {
      d=0
    }
  ' $1
}

aliases () {
  doing "Setting up bash aliases"
  dumpAliases $0 > $HOME/.bashrc-lanlytics

  if ! grep -q bashrc-lanlytics $HOME/.bashrc; then
    mv $HOME/.bashrc $HOME/.bashrc.orig
    cat $HOME/.bashrc.orig > $HOME/.bashrc
    echo '. $HOME/.bashrc-lanlytics' >> $HOME/.bashrc
  fi
}

creds () {
  [ -f $HOME/.aws/credentials ] && return

  doing "Caching credentials"

  if [ -z  "$region" ] || [ -z "$aws_access_key_id" ] || [ -z "$aws_secret_access_key" ]; then
    echo 'Error: You need to set $region, $aws_access_key_id, and $aws_secret_access_key.' 1>&2
    exit 1
  fi

  mkdir -p $HOME/.aws

  touch $HOME/.aws/config
  chmod 0600 $_
  cat <<EOD >$_
[default]
output = table
region = $region
EOD

  touch $HOME/.aws/credentials
  chmod 0600 $_
  cat <<EOD >$_
[default]
aws_access_key_id = $aws_access_key_id
aws_secret_access_key = $aws_secret_access_key
EOD
}

##
## Main
##

aliases
creds

echo "You should reload your aliases:"
echo "    . ~/.bashrc-lanlytics"
