# telegram-mailing-helper
## Pre requirements
```shell
apt install python3-pip build-essential libsystemd-dev git
pip3 install poetry
```
## Installation (example)
- clone repo from github into /opt:
```shell
WORKDIR=/opt
sudo mkdir -p $WORKDIR/telegram-mailing-helper
sudo chown $USER:$USER $WORKDIR/telegram-mailing-helper
cd $WORKDIR
git clone https://github.com/11sanach11/telegram-mailing-helper.git
cd telegram-mailing-helper
poetry install --no-dev
cp ./test_config.json ./config.json
<<<!!! PREPARE CONFIG FILE, SET server.port, telegramToken, etc...
sudo cp ./template_for_service/telegram-mailing-helper.service /etc/systemd/system/telegram-mailing-helper.service
sudo sed -i -e "s/%USER%/$USER/g" -e "s|%WORKDIR%|$WORKDIR|g" /etc/systemd/system/telegram-mailing-helper.service
sudo systemctl enable telegram-mailing-helper
$WORKDIR/update.sh
```

## UPDATE
```shell
telegram-mailing-helper
$WORKDIR/telegram-mailing-helper/update.sh
```
