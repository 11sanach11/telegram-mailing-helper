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
import base64
import hashlib
import json
import logging
import pathlib
import threading
import time
from functools import wraps
from dataclasses import dataclass

import bottle
from bottle import TEMPLATE_PATH, HTTPResponse, BaseRequest, request, auth_basic, response, get, post, redirect, template, \
    static_file, run as run_bottle

from telegram_mailing_help.telegramMailingHelper import _SINGLE_MODE_CONST

HELPER_TEMPLATE_PATH = str(pathlib.Path(__file__).parent.absolute()) + '/templates/'
TEMPLATE_PATH.append(HELPER_TEMPLATE_PATH)

from telegram_mailing_help.telegram.bot import MailingBot

BaseRequest.MEMFILE_MAX = 1024 * 1024 * 1024 * 10

from telegram_mailing_help.appConfig import ApplicationConfiguration
from telegram_mailing_help import __version__
from telegram_mailing_help.db.dao import Dao, UserState
from telegram_mailing_help.logic.listPreparation import Preparation

log = logging.getLogger("bottleServer")

HASHES_CACHE = {}


def hashSumForStatic(staticFileName):
    if not HASHES_CACHE.get(staticFileName):
        md5_hash = hashlib.md5()
        with open(HELPER_TEMPLATE_PATH + "/" + staticFileName, "rb") as a_file:
            content = a_file.read()
            md5_hash.update(content)
            HASHES_CACHE[staticFileName] = md5_hash.hexdigest()
    return staticFileName + "?hash=" + HASHES_CACHE.get(staticFileName)


def botName():
    name = getXHelperBotNameHeader()
    if name == _SINGLE_MODE_CONST:
        return "SINGLE"
    else:
        return name


bottle.BaseTemplate.defaults["hash"] = hashSumForStatic
bottle.BaseTemplate.defaults["botName"] = botName
# db: Dao = None
# preparation: Preparation = None
# bot: MailingBot = None
dbMap = {}
preparationMap = {}
botMap = {}
appConfig = {"config": None}


def _getTemplateFile(templateName):
    return str(pathlib.Path(__file__).parent.absolute()) + '/templates/' + templateName


def getXHelperBotNameHeader():
    if appConfig["config"].telegramToken is None:
        return request.environ.get("TG_BOT_NAME")
    else:
        return _SINGLE_MODE_CONST


def is_auth_user(user, password):
    if appConfig["config"].telegramToken is None:
        for botInfo in appConfig["config"].telegramTokens.items():
            for loginInfo in botInfo[1].logins:
                if user == loginInfo.get("user"):
                    if password == loginInfo.get("password"):
                        request.environ["TG_BOT_NAME"] = botInfo[0]
                        return True
                    else:
                        return False
        return False
    else:
        return True


@get("/")
def rootRedirect():
    return redirect("/pages/dispatch_lists.html")


@get("/info")
def info():
    return {"version": __version__, "app": "telegram_mailing_helper"}


@get("/pages/users.html")
@auth_basic(is_auth_user)
def users():
    return template(_getTemplateFile("users.tpl"), users=getDb().getAllUsers(), userStateCls=UserState)


@get("/pages/settings.html")
@auth_basic(is_auth_user)
def settings():
    return template(_getTemplateFile("settings.tpl"), settings=getDb().getAllStorages())


@dataclass
class ReportTemplate:
    key: str
    title: str
    data: str
    selected: bool


@get("/pages/reports.html")
@auth_basic(is_auth_user)
def settings():
    top_today = getPreparation().prepareReport(
        "SELECT u.name, sum(case when dla.state=='assigned' then 1 end) as assignedCount, sum(case when dla.state=='rollback' then 1 end) as rollbackCount from DISPATCH_LIST_ASSIGNS dla "
        "left join USERS u on (u.id = dla.users_id ) "
        "where DATE(dla.change_date)>=DATE('now','localtime') GROUP BY dla.users_id ORDER BY assignedCount DESC",
        ["Имя", "Кол-во взятых блоков", "Кол-во возвращенных блоков"])
    top_today_by_groups = getPreparation().prepareReport(
        "select  dlg.dispatch_group_name, u.name, count(dla.uuid) as 'get' from DISPATCH_LIST_ASSIGNS dla "
        "left join USERS u on dla.users_id=u.id "
        "left join DISPATCH_LIST dl on dla.dispatch_list_id=dl.id "
        "left join DISPATCH_LIST_GROUP dlg on dl.dispatch_group_id=dlg.id "
        "where dla.state=='assigned' and DATE(dla.change_date)>=DATE('now','localtime') "
        "group by u.id,dl.dispatch_group_id order by dlg.dispatch_group_name,u.name",
        ["Название", "Имя польз.", "Кол-во взятых блоков"])
    top_yesterday_by_groups = getPreparation().prepareReport(
        "select  dlg.dispatch_group_name, u.name, count(dla.uuid) as 'get' from DISPATCH_LIST_ASSIGNS dla "
        "left join USERS u on dla.users_id=u.id "
        "left join DISPATCH_LIST dl on dla.dispatch_list_id=dl.id "
        "left join DISPATCH_LIST_GROUP dlg on dl.dispatch_group_id=dlg.id "
        "where dla.state=='assigned' and DATE(dla.change_date)=DATE('now','localtime' ,'-1 day') "
        "group by u.id,dl.dispatch_group_id order by dlg.dispatch_group_name,u.name",
        ["Название", "Имя польз.", "Кол-во взятых блоков"])
    top_yesterday = getPreparation().prepareReport(
        "SELECT u.name, sum(case when dla.state=='assigned' then 1 end) as assignedCount, sum(case when dla.state=='rollback' then 1 end) as rollbackCount from DISPATCH_LIST_ASSIGNS dla "
        "left join USERS u on (u.id = dla.users_id ) "
        "where DATE(dla.change_date)=DATE('now','localtime' ,'-1 day') GROUP BY dla.users_id ORDER BY assignedCount DESC",
        ["Имя", "Кол-во взятых блоков", "Кол-во возвращенных блоков"])
    top_last_7_day = getPreparation().prepareReport(
        "SELECT u.name, sum(case when dla.state=='assigned' then 1 end) as assignedCount, sum(case when dla.state=='rollback' then 1 end) as rollbackCount from DISPATCH_LIST_ASSIGNS dla "
        "left join USERS u on (u.id = dla.users_id ) "
        "where DATE(dla.change_date)>=DATE('now','localtime' ,'-7 day') GROUP BY dla.users_id ORDER BY assignedCount DESC",
        ["Имя", "Кол-во взятых блоков", "Кол-во возвращенных блоков"])
    top_month = getPreparation().prepareReport(
        "SELECT u.name, sum(case when dla.state=='assigned' then 1 end) as assignedCount, sum(case when dla.state=='rollback' then 1 end) as rollbackCount from DISPATCH_LIST_ASSIGNS dla "
        "left join USERS u on (u.id = dla.users_id ) "
        "where strftime('%Y',dla.change_date) = strftime('%Y',date('now','localtime')) AND  strftime('%m',dla.change_date) = strftime('%m',date('now','localtime'))"
        " GROUP BY dla.users_id ORDER BY assignedCount DESC",
        ["Имя", "Кол-во взятых блоков", "Кол-во возвращенных блоков"]
    )
    top_last_month = getPreparation().prepareReport(
        "SELECT u.name, sum(case when dla.state=='assigned' then 1 end) as assignedCount, sum(case when dla.state=='rollback' then 1 end) as rollbackCount from DISPATCH_LIST_ASSIGNS dla "
        "left join USERS u on (u.id = dla.users_id ) "
        "where strftime('%Y',dla.change_date) = strftime('%Y',date('now','localtime', '-1 month')) AND  strftime('%m',dla.change_date) = strftime('%m',date('now','localtime', '-1 month'))"
        " GROUP BY dla.users_id ORDER BY assignedCount DESC",
        ["Имя", "Кол-во взятых блоков", "Кол-во возвращенных блоков"]
    )
    top_lists_today = getPreparation().prepareReport(
        "SELECT dlg.dispatch_group_name, count(dla.uuid) as assignedCount FROM DISPATCH_LIST_ASSIGNS dla "
        "LEFT JOIN DISPATCH_LIST dl ON (dl.id = dla.dispatch_list_id ) "
        "LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.id = dl.dispatch_group_id )"
        " WHERE dla.state='assigned' AND DATE(dla.change_date)=DATE('now','localtime') GROUP BY dlg.id  ORDER BY assignedCount DESC",
        ["Наименование кнопки", "Кол-во взятых блоков"]
    )
    top_lists_yesterday = getPreparation().prepareReport(
        "SELECT dlg.dispatch_group_name, count(dla.uuid) as assignedCount FROM DISPATCH_LIST_ASSIGNS dla "
        "LEFT JOIN DISPATCH_LIST dl ON (dl.id = dla.dispatch_list_id ) "
        "LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.id = dl.dispatch_group_id )"
        " WHERE dla.state='assigned' AND DATE(dla.change_date)=DATE('now','localtime' ,'-1 day') GROUP BY dlg.id  ORDER BY assignedCount DESC",
        ["Наименование кнопки", "Кол-во взятых блоков"]
    )
    available_blocks_count = getPreparation().prepareReport(
        '''SELECT dlg.dispatch_group_name, CASE WHEN dlg.enabled=true THEN "активна" ELSE "скрыта" END, COUNT(dl.id) 
        FROM DISPATCH_LIST dl LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.id=dl.dispatch_group_id) 
        WHERE dl.is_assigned=false AND dlg.hidden=false GROUP BY dlg.id ORDER BY dlg.dispatch_group_name''',
        ["Наименование кнопки", "Состояние", "Кол-во оставшихся блоков"]
    )
    return template(_getTemplateFile("reports.tpl"),
                    reports=[
                        ReportTemplate(title="Топ по людям за сегодня", key="top_today", data=top_today, selected=True),
                        ReportTemplate(title="Топ по людям за вчера", key="top_yesterday", data=top_yesterday, selected=False),
                        ReportTemplate(title="Топ по людям за последние 7 дней", key="top_last_7_day", data=top_last_7_day, selected=False),
                        ReportTemplate(title="Топ по людям за месяц", key="top_month", data=top_month, selected=False),
                        ReportTemplate(title="Топ по людям за прошлый месяц", key="top_last_month", data=top_last_month, selected=False),
                        ReportTemplate(title="Взятые кнопки по людям за сегодня", key="top_today_by_groups", data=top_today_by_groups, selected=False),
                        ReportTemplate(title="Взятые кнопки по людям за вчера", key="top_yesterday_by_groups", data=top_yesterday_by_groups, selected=False),
                        ReportTemplate(title="Топ по обработанным блокам за сегодня", key="top_lists_today", data=top_lists_today, selected=False),
                        ReportTemplate(title="Топ по обработанным блокам за вчера", key="top_lists_yesterday", data=top_lists_yesterday, selected=False),
                        ReportTemplate(title="Оставшиеся блоки", key="available_blocks_count", data=available_blocks_count, selected=False),
                    ])


@get("/pages/dispatch_lists.html")
@auth_basic(is_auth_user)
def users():
    return template(_getTemplateFile("dispatch_lists.tpl"), dispatchGroupNames=list(getDb().getAllDispatchGroupNames()))


@get("/favicon.ico")
def favicon():
    return static_file("images/favicon.png", root=_getTemplateFile(""))


@get("/pages/<page>")
def pages(page):
    return static_file(page, root=_getTemplateFile(""))


def _convertToClientResponse(state):
    if state and state.get("state"):
        text = None
        if state.get("state") == "starting":
            text = "Загрузка данных начинается, подождите еще немного времени"
        elif state.get("state") == "inProcess":
            text = "Происходит загрузка данных, загружено %s записей из %s" \
                   % (state.get("processed"), state.get("totalCount"))
        elif state.get("state") == "finished":
            text = "Список был успешно добавлен, теперь его можно использовать. Добавлено %s новых блоков" \
                   % state.get("processed")
        else:
            text = "Список должен быть добавлен, теперь его можно использовать"
        return {"success": True,
                "id": state.get("id"),
                "state": state.get("state"),
                "countOfAddedItems": state.get("processed"),
                "totalCount": state.get("totalCount"),
                "text": text}
    else:
        return {"success": False,
                "countOfAddedItems": 0,
                "text": "Что-то пошло не так, попробуйте добавить записи еще раз"}


@get("/api/lists/<state_id>/state")
@auth_basic(is_auth_user)
def getPreparationState(state_id):
    return _convertToClientResponse(getPreparation().getPreparationState(state_id))


@post("/api/lists/add")
@auth_basic(is_auth_user)
def addDispatchList():
    dispatchGroupName = request.forms.name
    if dispatchGroupName:
        dispatchGroupName = dispatchGroupName.strip()
    description = request.forms.description
    links = request.forms.list.splitlines()
    groupSize = int(request.forms.groupSize)
    repeatTimes = int(request.forms.repeatTimes)
    disableByDefault = bool(request.forms.disableByDefault)
    showCommentWithBlock = bool(request.forms.showCommentWithBlock)
    state = getPreparation().addDispatchList(dispatchGroupName, description, links, groupSize,
                                             disableByDefault, showCommentWithBlock, False, "",
                                             repeatTimes=repeatTimes)
    return _convertToClientResponse(state)


@get("/templates/dispatch_group_buttons")
@auth_basic(is_auth_user)
def getDispatchGroupButtons():
    return template(_getTemplateFile("dispatch_group_buttons.tpl"),
                    dispatchGroupNames=list(getDb().getAllDispatchGroupNames()))


@get("/templates/lists/<gr_id>")
@auth_basic(is_auth_user)
def getDispatchGroupInfo(gr_id):
    info = getDb().getDispatchGroupInfo(gr_id)
    return template(_getTemplateFile("dispatch_group_info.tpl"), data={
        "info": info,
        "state": {
            "text": "Скрыть кнопку" if info.enabled else "Показывать кнопку",
            "value": "disable" if info.enabled else "enable"
        }
    })


@post("/api/lists/<gr_id>/change")
@auth_basic(is_auth_user)
def changeParamOfGroup(gr_id: int):
    body = json.load(request.body)
    dispatchGroup = getDb().getDispatchListGroupById(gr_id)
    for (k, v) in body.items():
        if v and type(v) == str:
            v = v.strip()
        if k != "id":
            dispatchGroup.__setattr__(k, v)
    getDb().saveDispatchListGroup(dispatchGroup)


@post("/api/lists/<gr_id>/state")
@auth_basic(is_auth_user)
def changeStateOfGroupAt(gr_id):
    body = json.load(request.body)
    if body["state"] == "enable":
        getDb().enableDispatchGroupName(gr_id)
    elif body["state"] == "disable":
        getDb().disableDispatchGroupName(gr_id)
    else:
        raise RuntimeError("Unknown state for group: %s : %s" % (gr_id, body["state"]))
    return {"success": True, "gr_id": gr_id}


@post("/api/users/state/change")
@auth_basic(is_auth_user)
def confirmUser():
    body = json.load(request.body)
    userId = body["id"]
    user = getDb().getUserById(userId)
    userState = UserState(user.state)
    newUserState = UserState.CONFIRMED if userState in [UserState.NEW, UserState.BLOCKED] else UserState.BLOCKED
    user.state = newUserState.value
    user = getDb().saveUser(user)
    if userState == UserState.NEW:
        getBot().sendFreeMessageToRegisteredUser(int(user.telegram_id), "Поздравляю, теперь у вас есть доступ до бота,"
                                                                        " давайте начнем сначала, жми /start!")
    return {"success": True, "state": user.state, "localizedState": UserState(user.state).getLocalizedMessage()}


@get("/api/lists/<gr_id>/downloadData.txt")
@auth_basic(is_auth_user)
def downloadUnassignedData(gr_id):
    response.content_type = 'text/text; charset=UTF8'
    for s in getDb().freeQuery(
            "select links_values_butch from dispatch_list where dispatch_group_id=%s and is_assigned=0" % gr_id):
        yield s[0] + "\n"


def getDb(botName: str = None) -> Dao:
    botKey = botName if botName else getXHelperBotNameHeader()
    return dbMap[botKey]


def getPreparation(botName: str = None) -> Preparation:
    botKey = botName if botName else getXHelperBotNameHeader()
    return preparationMap[botKey]


def getBot(botName: str = None) -> MailingBot:
    botKey = botName if botName else getXHelperBotNameHeader()
    return botMap[botKey]


@post("/api/settings/change")
@auth_basic(is_auth_user)
def confirmUser():
    body = json.load(request.body)
    key = body["key"]
    newValue = body["value"]
    getDb().setValueInfoStorage(key, newValue)
    return {"success": True, "key": key, "value": newValue}


@post("/t_webhook/<bot_name>/<bot_token>")
def update(bot_name: str, bot_token: str):
    if bot_token != getBot(bot_name).telegramToken:
        raise RuntimeError("wrong webhook call for helper bot %s: expected bot number: %s" %
                           (getXHelperBotNameHeader(), getBot().telegramToken.split(":")[0]))
    getBot(bot_name).update(json.load(request.body))


class BottleServer(threading.Thread):

    def __init__(self, config: ApplicationConfiguration,
                 daoMap,
                 preparationMapParam,
                 tbotMap):
        global dbMap, preparationMap, botMap
        threading.Thread.__init__(self, name=__name__)
        dbMap = daoMap
        preparationMap = preparationMapParam
        botMap = tbotMap
        appConfig["config"] = config
        self.daemon = True
        self.config = config

    def logToLogger(self, fn):
        @wraps(fn)
        def _logToLogger(*args, **kwargs):
            try:
                raisedException = None
                actual_response = None
                execMessage = "OK"
                start_time = time.time()
                try:
                    actual_response = fn(*args, **kwargs)
                except Exception as e:
                    execMessage = "%s" % e
                    raisedException = e
                timer = int((time.time() - start_time) * 100000) / 100.0
                login = None
                if request.get_header("Authorization") and request.get_header("Authorization").startswith("Basic "):
                    try:
                        base64_message = request.get_header("Authorization")[6:]
                        base64_bytes = base64_message.encode('ascii')
                        message_bytes = base64.b64decode(base64_bytes)
                        login = message_bytes.decode('ascii').split(':')[0]
                    except Exception as e:
                        log.error("Can't get login from header: %s", e)
                buffer = request.body.getbuffer()
                requestBody = '<empty>'
                if len(buffer) > 0:
                    try:
                        requestBody = bytes(buffer[0:min(len(buffer), 1000)]).decode("UTF-8")
                    except Exception as cantPrepareBodyExp:
                        requestBody = "<can't prepare body: %s>" % cantPrepareBodyExp
                responseBody = '<unknown>'
                if actual_response is None:
                    responseBody = '<empty>'
                elif type(actual_response) == dict:
                    try:
                        responseBody = ("%s" % actual_response)[0:1000]
                    except Exception as cantPrepareBodyExp:
                        responseBody = "<can't prepare body: %s>" % cantPrepareBodyExp
                log.info(
                    '%(bot)s WEB: %(method)s %(url)s %(login)s: %(message)s (exec: %(timer)s ms); params: %(addr)s %(http_status)s; reqBody=[%(requestBody)s], respBody=[%(responseBody)s]',
                    {
                        'bot': getXHelperBotNameHeader(),
                        'login': login if login else request.get_header("Ssl-Dn", "non-ssl"),
                        'message': execMessage,
                        'timer': timer,
                        'addr': request.remote_addr,
                        'method': request.method,
                        'url': request.url,
                        'http_status': response.status,
                        'requestBody': requestBody,
                        'responseBody': responseBody
                    })
                if raisedException:
                    raise raisedException
                return actual_response
            except Exception as e:
                if type(e) is HTTPResponse and e.status_code in [302, 303]:
                    log.info("redirect %s %s %s %s",
                             request.remote_addr,
                             request.method,
                             request.url,
                             response.status)
                else:
                    log.exception("Exception while call %s %s %s %s:",
                                  request.remote_addr,
                                  request.method,
                                  request.url,
                                  response.status)
                raise e

        return _logToLogger

    def run(self) -> None:
        run_bottle(host=self.config.server.host,
                   port=self.config.server.port,
                   server=self.config.server.engine,
                   plugins=[self.logToLogger],
                   quiet=True)
