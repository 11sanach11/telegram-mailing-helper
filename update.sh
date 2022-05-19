#!/bin/bash -e

workdir=`dirname $0`
echo "Workdir: $workdir"
[[ -f $workdir/update_config.sh ]] && source $workdir/update_config.sh
[[ $SERVICE_NAME ]] && service_name="$SERVICE_NAME" || service_name="telegram-mailing-helper"
echo "Try to stop service $service_name..."
sudo service $service_name stop
echo "CURRENT VERSION: $(git -C $workdir describe --tags --abbrev=0)"
git -C $workdir pull || true
echo "list of available version:"
git -C $workdir tag --sort=creatordate |tail -n 40
[[ $UPDATE_TO_VERSION ]] && version="$UPDATE_TO_VERSION" || read -p 'Please set update version: ' version
git -C $workdir checkout $version
echo "Switch into version: $(git -C $workdir describe --tags --abbrev=0)"
echo "Update project dependencies..."
cd $workdir
poetry install --no-dev
echo "Start..."
sudo service $service_name start
echo "Started... please check info! on 'http://host:port/info"
