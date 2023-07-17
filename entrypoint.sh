#!/bin/bash
if [ ! -e /app/config/config.json ];then
cat <<EOF >/app/config/config.json
{
  "db": {
    "dbFile": "prod_db.db"
  },
  "server": {
    "port": 23455,
    "host": "0.0.0.0",
    "engine": "gevent"
  },
  "rootConfigDir": "/app/db/",
  "telegramToken": "${APP_TELEGRAM_TOKEN}",
  "telegramTokens": {},
  "telegramWebhookURL":"https://domain",
  "logFileName": "/dev/null",
  "logOnlyInFile": false
}
EOF
fi;
export PYTHONPATH="${PYTHONPATH}:/app/"
exec poetry run python ./telegram_mailing_help/main.py /app/config/config.json
