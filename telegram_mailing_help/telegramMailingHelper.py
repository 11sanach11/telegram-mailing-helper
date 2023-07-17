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
# /usr/bin/env poetry run
import sys
from appConfig import prepareAndGetConfigOnly
from logging import getLogger
from signal import SIGINT, SIGTERM, SIGABRT, SIGHUP, signal
from gevent import signal_handler

import systemd.daemon

import telegram_mailing_help.db.migration as db
from telegram_mailing_help.appConfig import ApplicationConfiguration, Token
from telegram_mailing_help.db.dao import Dao
from telegram_mailing_help.logic.listPreparation import Preparation
from telegram_mailing_help.telegram import bot
from telegram_mailing_help.web import server

_SINGLE_MODE_CONST: str = "single_606e77dc-2b39-4ed5-b2c1-65fe1f3e425d"

log = getLogger()


class TelegramMailingHelper:

    def _logAndPrintMessage(self, message):
        print(message)
        log.info(message)

    def gevent_signal_stop_handler(self):
        self._logAndPrintMessage("Try to stop helper...")
        for mailingBot in self.telegramBotList.values():
            mailingBot.stop()
        self._logAndPrintMessage("Application stopped")
        systemd.daemon.notify(systemd.daemon.Notification.STOPPING)
        self._logAndPrintMessage("Helper had been stopped")
        sys.exit()

    def signal_stop_handler(self, signum, frame) -> None:
        self.gevent_signal_stop_handler()

    def gevent_signal_reload_handler(self) -> None:
        self._logAndPrintMessage("Try to reload bot configurations, please note: bot list only may be reconfigured!")
        if len(self.migrationList) == 1 and list(self.migrationList.keys())[0] == _SINGLE_MODE_CONST:
            self._logAndPrintMessage("Current mode is _SINGLE_MODE, can't update bot list. Stop reload!")
        else:
            currentBotList = dict(self.appConfig.telegramTokens)
            try:
                newBotList = prepareAndGetConfigOnly().telegramTokens
                for botName in newBotList.keys():
                    if currentBotList.get(botName):
                        self._logAndPrintMessage("Bot: %s already loaded, skip it" % botName)
                    elif not currentBotList.get(botName):
                        self._logAndPrintMessage("Bot: %s try to start it" % botName)
                        self.appConfig.telegramTokens[botName] = newBotList[botName]
                        self.prepareBotForStart(self.appConfig, botName)
                        self._logAndPrintMessage("Bot: %s started" % botName)
                    # list of bots which should be stopped
                for botName in set(currentBotList.keys()) - set(newBotList.keys()):
                    self._logAndPrintMessage("Bot: %s try to stop it" % botName)
                    self.stopBot(botName)
                    self.appConfig.telegramTokens.pop(botName)
                self._logAndPrintMessage(
                    "Bot list reloaded. current list of runned bots: %s" % self.appConfig.telegramTokens.keys())
            except Exception as e:
                self._logAndPrintMessage("Can't reload bot lists: %s" % e)
                self.appConfig.telegramTokens = currentBotList

    def signal_reload_handler(self, signum=None, frame=None) -> None:
        self.gevent_signal_stop_handler()

    def stopBot(self, botName):
        if self.daoList.get(botName):
            self.daoList[botName].stop()
            self.daoList.pop(botName)
        if self.preparationList.get(botName):
            self.preparationList.pop(botName)
        if self.telegramBotList.get(botName):
            self.telegramBotList[botName].stop()
            self.telegramBotList.pop(botName)

    def prepareBotForStart(self, appConfig: ApplicationConfiguration, botName: str):
        dbBotName = botName if botName is not None and botName != _SINGLE_MODE_CONST else None
        migration = db.Migration(appConfig, dbBotName)
        migration.migrate()
        self.migrationList[botName] = migration
        dao = Dao(appConfig, dbBotName)
        self.daoList[botName] = dao
        preparation = Preparation(appConfig, dao)
        self.preparationList[botName] = preparation
        webHookMode = appConfig.telegramToken is None
        telegramToken = appConfig.telegramTokens[botName].token if webHookMode else appConfig.telegramToken
        telegramWebhookURL = appConfig.telegramWebhookURL if webHookMode else None
        mailingBot = bot.MailingBot(botName, telegramToken, webHookMode, telegramWebhookURL, dao,
                                    preparation)
        mailingBot.start()
        self.telegramBotList[botName] = mailingBot

    def __init__(self, appConfig: ApplicationConfiguration):
        log.info("Start the application")
        self.appConfig = appConfig
        self.migrationList = {}
        self.daoList = {}
        self.preparationList = {}
        self.telegramBotList = {}
        if appConfig.telegramToken and not appConfig.telegramTokens:
            self.prepareBotForStart(appConfig, _SINGLE_MODE_CONST)
        elif not appConfig.telegramToken and appConfig.telegramTokens:
            for botName in appConfig.telegramTokens.keys():
                self.prepareBotForStart(appConfig, botName)
        else:
            raise RuntimeError(
                "Can't start helper, wrong parameters, please set either telegramToken on telegramTokens!")

        self.server = server.BottleServer(appConfig, self.daoList, self.preparationList, self.telegramBotList)
        self.server.start()

        if appConfig.server.engine == "gevent":
            for sig in (SIGINT, SIGTERM, SIGABRT):
                signal_handler(sig, self.gevent_signal_stop_handler)
            # process reload signal
            signal_handler(SIGHUP, self.gevent_signal_reload_handler)
        else:
            for sig in (SIGINT, SIGTERM, SIGABRT):
                signal(sig, self.signal_stop_handler)
            # process reload signal
            signal(SIGHUP, self.signal_reload_handler)
