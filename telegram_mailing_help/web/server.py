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
import dataclasses
import json
import logging
import pathlib
import threading
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from telegram_mailing_help import __version__
from telegram_mailing_help.appConfig import ApplicationConfiguration, SINGLE_MODE_CONST as _SINGLE_MODE_CONST
from telegram_mailing_help.db.dao import Dao, UserState
from telegram_mailing_help.logic.listPreparation import Preparation
from telegram_mailing_help.telegram.bot import MailingBot

STATIC_PATH = str(pathlib.Path(__file__).parent.absolute()) + '/templates/'

log = logging.getLogger("fastapiServer")

dbMap: dict = {}
preparationMap: dict = {}
botMap: dict = {}
_appConfig: Optional[ApplicationConfiguration] = None

app = FastAPI()
security = HTTPBasic(auto_error=False)


# ── Auth ──────────────────────────────────────────────────────────────────────

def _get_bot_name(credentials: Optional[HTTPBasicCredentials] = Depends(security)) -> str:
    if _appConfig.telegramToken is not None:
        return _SINGLE_MODE_CONST
    if credentials is None:
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})
    for bot_name, bot_info in _appConfig.telegramTokens.items():
        for login_info in bot_info.logins:
            if credentials.username == login_info.get("user"):
                if credentials.password == login_info.get("password"):
                    return bot_name
                raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})
    raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})


def _get_db(bot_name: str = Depends(_get_bot_name)) -> Dao:
    return dbMap[bot_name]


def _get_preparation(bot_name: str = Depends(_get_bot_name)) -> Preparation:
    return preparationMap[bot_name]


def _get_mailing_bot(bot_name: str = Depends(_get_bot_name)) -> MailingBot:
    return botMap[bot_name]


def _convert_state_response(state: Optional[dict]) -> dict:
    if state and state.get("state"):
        s = state["state"]
        if s == "starting":
            text = "Загрузка данных начинается, подождите еще немного времени"
        elif s == "inProcess":
            text = "Происходит загрузка данных, загружено %s записей из %s" % (
                state.get("processed"), state.get("totalCount"))
        elif s == "finished":
            text = "Список был успешно добавлен, теперь его можно использовать. Добавлено %s новых блоков" % state.get(
                "processed")
        else:
            text = "Список должен быть добавлен, теперь его можно использовать"
        return {"success": True, "id": state.get("id"), "state": s,
                "countOfAddedItems": state.get("processed"), "totalCount": state.get("totalCount"), "text": text}
    return {"success": False, "countOfAddedItems": 0,
            "text": "Что-то пошло не так, попробуйте добавить записи еще раз"}


# ── Static files ──────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


# ── Utility ───────────────────────────────────────────────────────────────────

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC_PATH + "images/favicon.png")


@app.get("/info")
def info():
    return {"version": __version__, "app": "telegram_mailing_helper"}


# ── SPA routes ────────────────────────────────────────────────────────────────

@app.get("/")
def root(_: str = Depends(_get_bot_name)):
    return FileResponse(STATIC_PATH + "index.html")


@app.get("/pages/{page:path}")
def pages(_page: str, _: str = Depends(_get_bot_name)):
    return FileResponse(STATIC_PATH + "index.html")


# ── New JSON endpoints for Vue SPA ────────────────────────────────────────────

@app.get("/api/app-info")
def app_info(bot_name: str = Depends(_get_bot_name)):
    display = "SINGLE" if bot_name == _SINGLE_MODE_CONST else bot_name
    return {"botName": display, "version": __version__}


@app.get("/api/dispatch-groups")
def get_dispatch_groups(db: Dao = Depends(_get_db)):
    return [dataclasses.asdict(g) for g in db.getAllDispatchGroupNames()]


@app.get("/api/dispatch-groups/{gr_id}")
def get_dispatch_group_info(gr_id: int, db: Dao = Depends(_get_db)):
    info = db.getDispatchGroupInfo(gr_id)
    if info is None:
        grp = db.getDispatchListGroupById(gr_id)
        if grp is None:
            raise HTTPException(404, detail="Group not found")
        info_dict = {
            "id": grp.id, "dispatch_group_name": grp.dispatch_group_name,
            "description": grp.description, "count": 0, "assigned_count": 0,
            "free_count": 0, "enabled": bool(grp.enabled),
            "priority": grp.priority, "repeat": grp.repeat,
            "show_comment_with_block": grp.show_comment_with_block,
            "show_count_of_taken_blocks": grp.show_count_of_taken_blocks,
            "show_group_only_for": grp.show_group_only_for,
        }
    else:
        info_dict = dataclasses.asdict(info)
    return {
        "info": info_dict,
        "state": {
            "text": "Скрыть кнопку" if info_dict["enabled"] else "Показывать кнопку",
            "value": "disable" if info_dict["enabled"] else "enable",
        }
    }


@app.get("/api/users-list")
def get_users(db: Dao = Depends(_get_db)):
    return [{"id": u.id, "telegram_id": u.telegram_id, "name": u.name,
             "state": u.state, "localizedState": UserState(u.state).getLocalizedMessage(),
             "created": u.created} for u in db.getAllUsers()]


@app.get("/api/settings-list")
def get_settings(db: Dao = Depends(_get_db)):
    return [dataclasses.asdict(s) for s in db.getAllStorages()]


@app.get("/api/reports")
def get_reports(preparation: Preparation = Depends(_get_preparation)):
    def q(sql, headers):
        return preparation.prepareReport(sql, headers)

    return [
        {"key": "top_today", "title": "Топ по людям за сегодня", "data": q(
            "SELECT u.name, sum(case when dla.state=='assigned' then 1 end) as assignedCount,"
            " sum(case when dla.state=='rollback' then 1 end) as rollbackCount"
            " from DISPATCH_LIST_ASSIGNS dla left join USERS u on (u.id = dla.users_id)"
            " where DATE(dla.change_date)>=DATE('now','localtime') GROUP BY dla.users_id ORDER BY assignedCount DESC",
            ["Имя", "Кол-во взятых блоков", "Кол-во возвращенных блоков"])},
        {"key": "top_yesterday", "title": "Топ по людям за вчера", "data": q(
            "SELECT u.name, sum(case when dla.state=='assigned' then 1 end) as assignedCount,"
            " sum(case when dla.state=='rollback' then 1 end) as rollbackCount"
            " from DISPATCH_LIST_ASSIGNS dla left join USERS u on (u.id = dla.users_id)"
            " where DATE(dla.change_date)=DATE('now','localtime','-1 day') GROUP BY dla.users_id ORDER BY assignedCount DESC",
            ["Имя", "Кол-во взятых блоков", "Кол-во возвращенных блоков"])},
        {"key": "top_last_7_day", "title": "Топ по людям за последние 7 дней", "data": q(
            "SELECT u.name, sum(case when dla.state=='assigned' then 1 end) as assignedCount,"
            " sum(case when dla.state=='rollback' then 1 end) as rollbackCount"
            " from DISPATCH_LIST_ASSIGNS dla left join USERS u on (u.id = dla.users_id)"
            " where DATE(dla.change_date)>=DATE('now','localtime','-7 day') GROUP BY dla.users_id ORDER BY assignedCount DESC",
            ["Имя", "Кол-во взятых блоков", "Кол-во возвращенных блоков"])},
        {"key": "top_month", "title": "Топ по людям за месяц", "data": q(
            "SELECT u.name, sum(case when dla.state=='assigned' then 1 end) as assignedCount,"
            " sum(case when dla.state=='rollback' then 1 end) as rollbackCount"
            " from DISPATCH_LIST_ASSIGNS dla left join USERS u on (u.id = dla.users_id)"
            " where strftime('%Y',dla.change_date)=strftime('%Y',date('now','localtime'))"
            " AND strftime('%m',dla.change_date)=strftime('%m',date('now','localtime'))"
            " GROUP BY dla.users_id ORDER BY assignedCount DESC",
            ["Имя", "Кол-во взятых блоков", "Кол-во возвращенных блоков"])},
        {"key": "top_last_month", "title": "Топ по людям за прошлый месяц", "data": q(
            "SELECT u.name, sum(case when dla.state=='assigned' then 1 end) as assignedCount,"
            " sum(case when dla.state=='rollback' then 1 end) as rollbackCount"
            " from DISPATCH_LIST_ASSIGNS dla left join USERS u on (u.id = dla.users_id)"
            " where strftime('%Y',dla.change_date)=strftime('%Y',date('now','localtime','-1 month'))"
            " AND strftime('%m',dla.change_date)=strftime('%m',date('now','localtime','-1 month'))"
            " GROUP BY dla.users_id ORDER BY assignedCount DESC",
            ["Имя", "Кол-во взятых блоков", "Кол-во возвращенных блоков"])},
        {"key": "top_today_by_groups", "title": "Взятые кнопки по людям за сегодня", "data": q(
            "select dlg.dispatch_group_name, u.name, count(dla.uuid) as 'get'"
            " from DISPATCH_LIST_ASSIGNS dla"
            " left join USERS u on dla.users_id=u.id"
            " left join DISPATCH_LIST dl on dla.dispatch_list_id=dl.id"
            " left join DISPATCH_LIST_GROUP dlg on dl.dispatch_group_id=dlg.id"
            " where dla.state=='assigned' and DATE(dla.change_date)>=DATE('now','localtime')"
            " group by u.id,dl.dispatch_group_id order by dlg.dispatch_group_name,u.name",
            ["Название", "Имя польз.", "Кол-во взятых блоков"])},
        {"key": "top_yesterday_by_groups", "title": "Взятые кнопки по людям за вчера", "data": q(
            "select dlg.dispatch_group_name, u.name, count(dla.uuid) as 'get'"
            " from DISPATCH_LIST_ASSIGNS dla"
            " left join USERS u on dla.users_id=u.id"
            " left join DISPATCH_LIST dl on dla.dispatch_list_id=dl.id"
            " left join DISPATCH_LIST_GROUP dlg on dl.dispatch_group_id=dlg.id"
            " where dla.state=='assigned' and DATE(dla.change_date)=DATE('now','localtime','-1 day')"
            " group by u.id,dl.dispatch_group_id order by dlg.dispatch_group_name,u.name",
            ["Название", "Имя польз.", "Кол-во взятых блоков"])},
        {"key": "top_lists_today", "title": "Топ по обработанным блокам за сегодня", "data": q(
            "SELECT dlg.dispatch_group_name, count(dla.uuid) as assignedCount"
            " FROM DISPATCH_LIST_ASSIGNS dla"
            " LEFT JOIN DISPATCH_LIST dl ON (dl.id=dla.dispatch_list_id)"
            " LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.id=dl.dispatch_group_id)"
            " WHERE dla.state='assigned' AND DATE(dla.change_date)=DATE('now','localtime')"
            " GROUP BY dlg.id ORDER BY assignedCount DESC",
            ["Наименование кнопки", "Кол-во взятых блоков"])},
        {"key": "top_lists_yesterday", "title": "Топ по обработанным блокам за вчера", "data": q(
            "SELECT dlg.dispatch_group_name, count(dla.uuid) as assignedCount"
            " FROM DISPATCH_LIST_ASSIGNS dla"
            " LEFT JOIN DISPATCH_LIST dl ON (dl.id=dla.dispatch_list_id)"
            " LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.id=dl.dispatch_group_id)"
            " WHERE dla.state='assigned' AND DATE(dla.change_date)=DATE('now','localtime','-1 day')"
            " GROUP BY dlg.id ORDER BY assignedCount DESC",
            ["Наименование кнопки", "Кол-во взятых блоков"])},
        {"key": "available_blocks_count", "title": "Оставшиеся блоки", "data": q(
            'SELECT dlg.dispatch_group_name, CASE WHEN dlg.enabled=true THEN "активна" ELSE "скрыта" END, COUNT(dl.id)'
            ' FROM DISPATCH_LIST dl LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.id=dl.dispatch_group_id)'
            ' WHERE dl.is_assigned=false AND dlg.hidden=false GROUP BY dlg.id ORDER BY dlg.dispatch_group_name',
            ["Наименование кнопки", "Состояние", "Кол-во оставшихся блоков"])},
    ]


# ── Existing API endpoints ────────────────────────────────────────────────────

@app.get("/api/lists/{state_id}/state")
def get_preparation_state(state_id: str, preparation: Preparation = Depends(_get_preparation)):
    return _convert_state_response(preparation.getPreparationState(state_id))


@app.post("/api/lists/add")
async def add_dispatch_list(request: Request, preparation: Preparation = Depends(_get_preparation)):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        name = (body.get("name") or "").strip()
        description = body.get("description", "")
        links_text = body.get("list", "")
        group_size = int(body.get("groupSize", 5))
        repeat_times = int(body.get("repeatTimes", 1))
        disable_by_default = bool(body.get("disableByDefault", False))
        show_comment = bool(body.get("showCommentWithBlock", False))
    else:
        form = await request.form()
        name = (form.get("name") or "").strip()
        description = form.get("description", "")
        links_text = form.get("list", "")
        group_size = int(form.get("groupSize", 5))
        repeat_times = int(form.get("repeatTimes", 1))
        disable_by_default = bool(form.get("disableByDefault", ""))
        show_comment = bool(form.get("showCommentWithBlock", ""))

    links = links_text.splitlines()
    state = preparation.addDispatchList(name, description, links, group_size,
                                        disable_by_default, show_comment, False, "",
                                        repeatTimes=repeat_times)
    return _convert_state_response(state)


@app.post("/api/lists/{gr_id}/change")
async def change_group_params(gr_id: int, request: Request, db: Dao = Depends(_get_db)):
    body = await request.json()
    group = db.getDispatchListGroupById(gr_id)
    for k, v in body.items():
        if v and isinstance(v, str):
            v = v.strip()
        if k != "id":
            setattr(group, k, v)
    db.saveDispatchListGroup(group)


@app.post("/api/lists/{gr_id}/state")
async def change_group_state(gr_id: int, request: Request, db: Dao = Depends(_get_db)):
    body = await request.json()
    state = body["state"]
    if state == "enable":
        db.enableDispatchGroupName(gr_id)
    elif state == "disable":
        db.disableDispatchGroupName(gr_id)
    else:
        raise HTTPException(400, detail="Unknown state: %s" % state)
    return {"success": True, "gr_id": gr_id}


@app.post("/api/users/state/change")
async def change_user_state(request: Request, db: Dao = Depends(_get_db),
                            mailing_bot: MailingBot = Depends(_get_mailing_bot)):
    body = await request.json()
    user = db.getUserById(body["id"])
    current_state = UserState(user.state)
    new_state = UserState.CONFIRMED if current_state in [UserState.NEW, UserState.BLOCKED] else UserState.BLOCKED
    user.state = new_state.value
    user = db.saveUser(user)
    if current_state == UserState.NEW:
        mailing_bot.sendFreeMessageToRegisteredUser(
            int(user.telegram_id),
            "Поздравляю, теперь у вас есть доступ до бота, давайте начнем сначала, жми /start!")
    return {"success": True, "state": user.state, "localizedState": UserState(user.state).getLocalizedMessage()}


@app.get("/api/lists/{gr_id}/downloadData.txt")
def download_unassigned(gr_id: int, db: Dao = Depends(_get_db)):
    def generate():
        for row in db.freeQuery(
                "select links_values_butch from dispatch_list where dispatch_group_id=%s and is_assigned=0" % gr_id):
            yield row[0] + "\n"

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=data.txt"})


@app.post("/api/settings/change")
async def change_settings(request: Request, db: Dao = Depends(_get_db)):
    body = await request.json()
    db.setValueInfoStorage(body["key"], body["value"])
    return {"success": True, "key": body["key"], "value": body["value"]}


@app.post("/t_webhook/{bot_name}/{bot_token}")
async def telegram_webhook(bot_name: str, bot_token: str, request: Request):
    if bot_name not in botMap or bot_token != botMap[bot_name].telegramToken:
        raise HTTPException(400, detail="Wrong webhook call for bot %s" % bot_name)
    body = await request.json()
    botMap[bot_name].update(body)


# ── Logging middleware ────────────────────────────────────────────────────────

class _LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        login = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                login = base64.b64decode(auth[6:]).decode("ascii").split(":")[0]
            except Exception:
                pass
        await request.body()  # cache so route handlers can read it too
        response = await call_next(request)
        elapsed = int((time.time() - start) * 100000) / 100.0
        log.info("WEB: %s %s [%s] %s %.1fms",
                 request.method, request.url.path,
                 response.status_code, login or "-", elapsed)
        return response


app.add_middleware(_LoggingMiddleware)


# ── Server thread ─────────────────────────────────────────────────────────────

class FastAPIServer(threading.Thread):

    def __init__(self, config: ApplicationConfiguration, daoMap, preparationMapParam, tbotMap):
        global dbMap, preparationMap, botMap, _appConfig
        threading.Thread.__init__(self, name=__name__)
        dbMap = daoMap
        preparationMap = preparationMapParam
        botMap = tbotMap
        _appConfig = config
        self.daemon = True
        self.config = config
        self._extra_apps = []  # list of (fastapi_app, host, port)

    def add_app(self, extra_app, host: str, port: int):
        """Register an additional FastAPI app to serve in the same event loop."""
        self._extra_apps.append((extra_app, host, port))

    def run(self) -> None:
        import asyncio

        def _make_server(asgi_app, host, port):
            cfg = uvicorn.Config(asgi_app, host=host, port=port,
                                 log_level="warning", access_log=False)
            srv = uvicorn.Server(cfg)
            srv.install_signal_handlers = lambda: None
            return srv

        servers = [_make_server(app, self.config.server.host, self.config.server.port)]
        for extra_app, host, port in self._extra_apps:
            servers.append(_make_server(extra_app, host, port))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(asyncio.gather(*[s.serve() for s in servers]))
        finally:
            loop.close()


# Backward-compatibility alias used by existing tests and configs
BottleServer = FastAPIServer
