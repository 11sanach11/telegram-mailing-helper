# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser Public License for more details.
#
# You should have received a copy of the GNU Lesser Public License
# along with this program.  If not, see [http://www.gnu.org/licenses/].
import json
import os
import sys
from dataclasses import dataclass
from typing import List, Dict, Optional

import dacite

import telegram_mailing_help.db.config as configDb
import telegram_mailing_help.web.config as configServer

_config = None


@dataclass
class Login:
    user: str
    password: str


@dataclass
class Token:
    token: str
    logins: list[Login]


@dataclass
class ApplicationConfiguration:
    rootConfigDir: str
    telegramToken: Optional[str]
    logFileName: str
    db: configDb.Configuration
    telegramTokens: dict[str, Token]
    server: configServer.Configuration = configServer.Configuration()
    logOnlyInFile: bool = False
    telegramWebhookURL: str = None  # https://example.com, but post in https://example.com/t_webhook (or https://example.com/t_webhook/<bot_name> if multibot mode)


def prepareConfig():
    global _config
    _config = prepareAndGetConfigOnly()
    return _config


def prepareAndGetConfigOnly() -> ApplicationConfiguration:
    configFile = sys.argv[1] if len(sys.argv) > 1 else "../test_config.json"
    with open(configFile) as json_config:
        rawJson = json.load(json_config)
        appConfig = dacite.from_dict(ApplicationConfiguration, rawJson)
        if rawJson["telegramTokens"]:
            appConfig.telegramTokens = dict()
            for token in rawJson["telegramTokens"].keys():
                appConfig.telegramTokens[token] = dacite.from_dict(Token, rawJson["telegramTokens"][token])
        for key in filter(lambda x: x.startswith('appConfig.'), os.environ.keys()):
            print("CONFIGURATION: override value for: %s in appConfig from env" % key)
            try:
                exec("%s = %s" % (key, os.environ.get(key)))
            except Exception as e:
                print("Can't apply env variable for config: %s because: %s" % (key, e))
        return appConfig
