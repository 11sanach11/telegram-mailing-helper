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

import bottle
from bottle import TEMPLATE_PATH, HTTPResponse, BaseRequest, request, response, get, post, redirect, template, \
    static_file, run as run_bottle

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


bottle.BaseTemplate.defaults["hash"] = hashSumForStatic
db: Dao = None
preparation: Preparation = None
bot: MailingBot = None


def _getTemplateFile(templateName):
    return str(pathlib.Path(__file__).parent.absolute()) + '/templates/' + templateName


@get("/")
def rootRedirect():
    return redirect("/pages/dispatch_lists.html")


@get("/info")
def info():
    return {"version": __version__, "app": "telegram_mailing_helper"}


@get("/pages/users.html")
def users():
    return template(_getTemplateFile("users.tpl"), users=db.getAllUsers(), userStateCls=UserState)


@get("/pages/settings.html")
def settings():
    return template(_getTemplateFile("settings.tpl"), settings=db.getAllStorages())


@get("/pages/reports.html")
def settings():
    top_today = preparation.prepareReport(
        "SELECT u.name, count(dla.dispatch_list_id) as assignedCount from DISPATCH_LIST_ASSIGNS dla "
        "left join USERS u on (u.id = dla.users_id ) "
        "where dla.state='assigned' AND DATE(dla.change_date)=DATE('now') GROUP BY dla.users_id ORDER BY assignedCount DESC",
        ["Имя", "Кол-во взятых блоков"])
    top_yesterday = preparation.prepareReport(
        "SELECT u.name, count(dla.dispatch_list_id) as assignedCount from DISPATCH_LIST_ASSIGNS dla "
        "left join USERS u on (u.id = dla.users_id ) "
        "where dla.state='assigned' AND DATE(dla.change_date)=DATE('now','-1 day') GROUP BY dla.users_id ORDER BY assignedCount DESC",
        ["Имя", "Кол-во взятых блоков"])
    top_month = preparation.prepareReport(
        "SELECT u.name, count(dla.dispatch_list_id) as assignedCount from DISPATCH_LIST_ASSIGNS dla "
        "left join USERS u on (u.id = dla.users_id ) "
        "where dla.state='assigned' AND "
        "strftime('%Y',dla.change_date) = strftime('%Y',date('now')) AND  strftime('%m',dla.change_date) = strftime('%m',date('now'))"
        " GROUP BY dla.users_id ORDER BY assignedCount DESC",
        ["Имя", "Кол-во взятых блоков"]
    )
    top_lists_today = preparation.prepareReport(
        "SELECT dlg.dispatch_group_name, count(dla.uuid) as assignedCount FROM DISPATCH_LIST_ASSIGNS dla "
        "LEFT JOIN DISPATCH_LIST dl ON (dl.id = dla.dispatch_list_id ) "
        "LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.id = dl.dispatch_group_id )"
        " WHERE dla.state='assigned' AND DATE(dla.change_date)=DATE('now') GROUP BY dlg.id  ORDER BY assignedCount DESC",
        ["Наименование кнопки", "Кол-во взятых блоков"]
    )
    top_lists_yesterday = preparation.prepareReport(
        "SELECT dlg.dispatch_group_name, count(dla.uuid) as assignedCount FROM DISPATCH_LIST_ASSIGNS dla "
        "LEFT JOIN DISPATCH_LIST dl ON (dl.id = dla.dispatch_list_id ) "
        "LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.id = dl.dispatch_group_id )"
        " WHERE dla.state='assigned' AND DATE(dla.change_date)=DATE('now','-1 day') GROUP BY dlg.id  ORDER BY assignedCount DESC",
        ["Наименование кнопки", "Кол-во взятых блоков"]
    )
    return template(_getTemplateFile("reports.tpl"),
                    top_today=top_today,
                    top_yesterday=top_yesterday,
                    top_month=top_month,
                    top_lists_today=top_lists_today,
                    top_lists_yesterday=top_lists_yesterday,
                    )


@get("/pages/dispatch_lists.html")
def users():
    return template(_getTemplateFile("dispatch_lists.tpl"), dispatchGroupNames=list(db.getAllDispatchGroupNames()))


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
def getPreparationState(state_id):
    return _convertToClientResponse(preparation.getPreparationState(state_id))


@post("/api/lists/add")
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
    state = preparation.addDispatchList(dispatchGroupName, description, links, groupSize,
                                        disableByDefault, showCommentWithBlock,
                                        repeatTimes=repeatTimes)
    return _convertToClientResponse(state)


@get("/templates/dispatch_group_buttons")
def getDispatchGroupButtons():
    return template(_getTemplateFile("dispatch_group_buttons.tpl"),
                    dispatchGroupNames=list(db.getAllDispatchGroupNames()))


@get("/templates/lists/<gr_id>")
def getDispatchGroupInfo(gr_id):
    info = db.getDispatchGroupInfo(gr_id)
    return template(_getTemplateFile("dispatch_group_info.tpl"), data={
        "info": info,
        "state": {
            "text": "Скрыть кнопку" if info.enabled else "Показывать кнопку",
            "value": "disable" if info.enabled else "enable"
        }
    })


@post("/api/lists/<gr_id>/change")
def changeParamOfGroup(gr_id: int):
    body = json.load(request.body)
    dispatchGroup = db.getDispatchListGroupById(gr_id)
    for (k, v) in body.items():
        if v and type(v) == str:
            v = v.strip()
        if k != "id":
            dispatchGroup.__setattr__(k, v)
    db.saveDispatchListGroup(dispatchGroup)


@post("/api/lists/<gr_id>/state")
def changeStateOfGroupAt(gr_id):
    body = json.load(request.body)
    if body["state"] == "enable":
        db.enableDispatchGroupName(gr_id)
    elif body["state"] == "disable":
        db.disableDispatchGroupName(gr_id)
    else:
        raise RuntimeError("Unknown state for group: %s : %s" % (gr_id, body["state"]))
    return {"success": True, "gr_id": gr_id}


@post("/api/users/state/change")
def confirmUser():
    body = json.load(request.body)
    userId = body["id"]
    user = db.getUserById(userId)
    userState = UserState(user.state)
    newUserState = UserState.CONFIRMED if userState in [UserState.NEW, UserState.BLOCKED] else UserState.BLOCKED
    user.state = newUserState.value
    user = db.saveUser(user)
    if userState == UserState.NEW:
        bot.sendFreeMessageToRegisteredUser(int(user.telegram_id), "Поздравляю, теперь у вас есть доступ до бота,"
                                                                   " давайте начнем сначала, жми /start!")
    return {"success": True, "state": user.state, "localizedState": UserState(user.state).getLocalizedMessage()}


@post("/api/settings/change")
def confirmUser():
    body = json.load(request.body)
    key = body["key"]
    newValue = body["value"]
    db.setValueInfoStorage(key, newValue)
    return {"success": True, "key": key, "value": newValue}


class BottleServer(threading.Thread):

    def __init__(self, config: ApplicationConfiguration, dao: Dao, preparationList: Preparation, tbot: MailingBot):
        global db, preparation, bot
        threading.Thread.__init__(self, name=__name__)
        db = dao
        preparation = preparationList
        bot = tbot
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
                    'WEB: %(method)s %(url)s %(login)s: %(message)s (exec: %(timer)s ms); params: %(addr)s %(http_status)s; reqBody=[%(requestBody)s], respBody=[%(responseBody)s]',
                    {
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
