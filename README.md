# telegram-mailing-helper


docker-compose example:
```yaml
version: '2'

services:
  telegram-mailing-helper:
    build: ./build
    restart: always
    ports:
      - 23455:23455
    volumes:
      - ./db:/app/db
      - ./config:/app/config
```
### for new installation of update:
1. clone/pull in ./build directory repository from github
1. checkout required version `git checkout x.x.x`
1. restart container: `docker-compose down; docker-compose up --build -d`

### example of reload script
```shell
sudo docker compose -f /docker/telegram-mailing-helper/docker-compose.yml exec -T telegtam-mailing-helper sh -c 'kill -1 1'
```
### example of update.sh script
```shell
#!/bin/bash
WORK_DIR=/docker/telegram-mailing-helper
echo "CURRENT VERSION: $(git -C ${WORK_DIR}/build/ describe --tags --abbrev=0)"
sudo -u chikago git -C ${WORK_DIR}/build/ pull || true
echo "list of available version:"
sudo -u chikago git -C ${WORK_DIR}/build/ tag --sort=creatordate |tail -n 40
[[ $UPDATE_TO_VERSION ]] && version="$UPDATE_TO_VERSION" || read -p 'Please set update version: ' version
sudo -u chikago git -C ${WORK_DIR}/build/ checkout $version
echo "Switch into version: $(git -C ${WORK_DIR}/build/ describe --tags --abbrev=0)"
sudo docker compose -f ${WORK_DIR}/docker-compose.yml up -d --build
```