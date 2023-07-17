# telegram-mailing-helper


docker-compose example:
```yaml
version: '2'

services:
  telegtam-mailing-helper:
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
