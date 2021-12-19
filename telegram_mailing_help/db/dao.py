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
import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlite3worker import Sqlite3Worker

from telegram_mailing_help.db.daoExp import OptimisticLockException
from telegram_mailing_help.db.utils import getDbFullPath

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

log = logging.getLogger()


class AssignState(Enum):
    ASSIGNED = 'assigned'
    ROLLBACK = 'rollback'


class UserState(Enum):
    NEW = 'new'
    CONFIRMED = 'confirmed'
    BLOCKED = 'blocked'

    def getLocalizedMessage(self):
        if self == UserState.NEW:
            return "\U00002753 Новый пользователь"
        elif self == UserState.CONFIRMED:
            return "\U00002705 Подтвержденный"
        elif self == UserState.BLOCKED:
            return "\U0000274C Заблокированный"
        else:
            raise Exception("Unsupported userState: %s" % self.name)


@dataclass
class DispatchListItem:
    id: Optional[int]
    dispatch_group_id: int
    links_values_butch: str
    created: str
    _check_sum: str = None
    _version: int = 0
    is_assigned: bool = False


@dataclass
class DispatchListGroupItem:
    id: Optional[int]
    dispatch_group_name: str
    social_network: Optional[str]
    description: str
    enabled: bool = True
    priority: int = 100
    repeat: int = 1
    hidden: bool = False
    show_comment_with_block: bool = False
    show_count_of_taken_blocks: bool = False
    show_group_only_for: str = None


@dataclass
class DispatchGroupInfo:
    id: int
    dispatch_group_name: str
    description: str
    count: int
    assigned_count: int
    free_count: int
    enabled: bool
    priority: int = 100
    repeat: int = 1
    show_comment_with_block: bool = False
    show_count_of_taken_blocks: bool = False
    show_group_only_for: str = None


@dataclass
class DispatchGroupNameInfo:
    id: int
    dispatch_group_name: str
    description: str
    enabled: bool
    show_group_only_for: str


@dataclass
class User:
    id: Optional[int]
    telegram_id: str
    name: str
    state: str
    created: str


@dataclass
class Storage:
    key: str
    value: str
    description: str


class Dao:
    def __init__(self, config):
        self.config = config
        self.worker = Sqlite3Worker(getDbFullPath(self.config))
        self.dispatchListFields = list(DispatchListItem.__annotations__.keys())
        self.userFields = list(User.__annotations__.keys())

    def freeQuery(self, sql):
        return self.worker.execute(sql)

    def __saveEntity(self, tableName, item, useVersion=False):
        if item.id is None:
            if useVersion:
                item._version = 0
            sql = "INSERT INTO %(tableName)s (%(fields)s) VALUES (%(values)s)" % {
                "tableName": tableName,
                "fields": ",".join(list(item.__dict__.keys())),
                "values": ",".join(["?"] * len(item.__dict__))
            }
            self.worker.execute(sql, values=tuple(item.__dict__.values()))
            item.id = self.worker.execute("Select last_insert_rowid() as id")[0][0]
        else:
            setVersionWhere = ""
            if useVersion:
                setVersionWhere = "and _version=%s" % item._version
                item._version = item._version + 1
            sql = "UPDATE %(tableName)s set %(values)s where id=? %(setVersionWhere)s" % {
                "tableName": tableName,
                "values": ",".join(list(map(lambda k: "%s=?" % k, item.__dict__.keys()))),
                "setVersionWhere": setVersionWhere
            }
            self.worker.execute(sql, values=tuple(list(item.__dict__.values()) + [item.id]))
            if useVersion:
                if self.worker.execute(
                        "SELECT COUNT(id) FROM %(tableName)s WHERE id=? AND _version=?" % {"tableName": tableName},
                        values=(item.id, item._version))[0][0] != 1:
                    raise OptimisticLockException()
        return item

    def getFreeDispatchListItem(self, dispatch_group_id, user: User):
        result = self.worker.execute(
            "SELECT dl.*, SUM(CASE dla.state when ? then 1 else 0 end) AS r_count, dlg.repeat AS repeat "
            "FROM DISPATCH_LIST dl LEFT JOIN DISPATCH_LIST_ASSIGNS dla ON (dla.dispatch_list_id=dl.id) "
            "LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.id=dl.dispatch_group_id ) "
            "WHERE dl.dispatch_group_id=? AND dl.is_assigned=0 "
            "GROUP BY dl.id HAVING r_count<dlg.repeat AND "
            "(r_count=0 OR ? NOT IN (SELECT users_id FROM DISPATCH_LIST_ASSIGNS WHERE state=? AND dispatch_list_id=dl.id)) "
            "LIMIT 1",
            values=(AssignState.ASSIGNED.value, dispatch_group_id, user.id, AssignState.ASSIGNED.value))
        if len(result) != 1:
            return None, False, 0
        else:
            return DispatchListItem(*result[0][0:7]), result[0][8] - result[0][7] <= 1, result[0][7]
        endif

    def assignBlockIntoUser(self, user: User, dispatch_list: DispatchListItem, setIs_assigned: bool):
        self.worker.execute("UPDATE DISPATCH_LIST set is_assigned=?, _version=? WHERE id=? and _version=?",
                            values=(1 if setIs_assigned else 0, dispatch_list._version + 1, dispatch_list.id,
                                    dispatch_list._version))
        assignId = str(uuid.uuid4())
        self.worker.execute(
            "INSERT INTO DISPATCH_LIST_ASSIGNS (uuid,dispatch_list_id,users_id,state,change_date) values (?,?,?,?,?)",
            values=(assignId, dispatch_list.id, user.id, AssignState.ASSIGNED.value, datetime.now().isoformat()))
        # if self.worker.execute(
        #         "SELECT COUNT(dl.id) FROM DISPATCH_LIST dl LEFT JOIN DISPATCH_LIST_ASSIGNS dla ON (dla.dispatch_list_id=dl.id ) "
        #         "WHERE dl.id =? AND dl._version=? AND dla.users_id =? AND dl.is_assigned=1 AND dla.state=?",
        #         values=(dispatch_list.id, dispatch_list._version + 1, user.id, AssignState.ASSIGNED.value))[0][0] != 1:
        #     self.worker.execute("DELETE FROM DISPATCH_LIST_ASSIGNS WHERE uuid=?", values=(assignId,))
        #     raise OptimisticLockException()
        # else:
        dispatch_list._version = dispatch_list._version + 1
        dispatch_list.is_assigned = True

    def freeAssignedBlockFromUser(self, user: User, dispatch_list: DispatchListItem):
        assignRecord = \
            self.worker.execute(
                "SELECT uuid FROM DISPATCH_LIST_ASSIGNS WHERE users_id=? AND dispatch_list_id=? AND state=?",
                values=(user.id, dispatch_list.id, AssignState.ASSIGNED.value))
        if assignRecord:
            assignId = assignRecord[0][0]
            self.worker.execute("UPDATE DISPATCH_LIST set is_assigned=0, _version=? WHERE id=? and _version=?",
                                values=(dispatch_list._version + 1, dispatch_list.id, dispatch_list._version))

            self.worker.execute(
                "UPDATE DISPATCH_LIST_ASSIGNS SET state=?, change_date=? WHERE uuid=?",
                values=(AssignState.ROLLBACK.value, datetime.now().isoformat(), assignId))
            dispatch_list._version = dispatch_list._version + 1
            dispatch_list.is_assigned = False
        return dispatch_list

    def saveDispatchList(self, item: DispatchListItem):
        item._check_sum = hashlib.md5(
            bytearray(item.links_values_butch + str(item.dispatch_group_id), encoding="utf-8")).hexdigest()
        return self.__saveEntity("DISPATCH_LIST", item, useVersion=True)

    def saveDispatchListGroup(self, item: DispatchListGroupItem):
        return self.__saveEntity("DISPATCH_LIST_GROUP", item, useVersion=False)

    def saveUser(self, item: User):
        return self.__saveEntity("USERS", item)

    def getDispatchListById(self, id: int):
        result = self.worker.execute("SELECT * from DISPATCH_LIST where id=?", values=(id,))
        if len(result) != 1:
            rez = None
        else:
            rez = DispatchListItem(*result[0])
        return rez

    def getUserById(self, id: int):
        result = self.worker.execute("SELECT * from USERS where id=?", values=(id,))
        if len(result) != 1:
            rez = None
        else:
            rez = User(*result[0])
        return rez

    def getDispatchListGroupById(self, id: int):
        result = self.worker.execute("SELECT * from DISPATCH_LIST_GROUP where id=?", values=(id,))
        if len(result) != 1:
            rez = None
        else:
            rez = DispatchListGroupItem(*result[0])
        return rez

    def getDispatchListGroupByName(self, dispatch_group_name: str):
        result = self.worker.execute(
            "SELECT * from DISPATCH_LIST_GROUP where dispatch_group_name=? AND hidden=0 LIMIT 1",
            values=(dispatch_group_name,))
        if len(result) != 1:
            rez = None
        else:
            rez = DispatchListGroupItem(*result[0])
        return rez

    def confirmUserById(self, id: int):
        self.worker.execute("UPDATE USERS SET state='" + UserState.CONFIRMED.value + "' where id=?", values=(id,))

    def setStateForUserById(self, id: int, state: UserState):
        self.worker.execute("UPDATE USERS SET state='" + state.value + "' where id=?", values=(id,))

    def getUserByTelegramId(self, telegram_id: str):
        result = self.worker.execute("SELECT * from USERS where telegram_id=?", values=(telegram_id,))
        if len(result) != 1:
            rez = None
        else:
            rez = User(*result[0])
        return rez

    def getAllUsers(self):
        result = self.worker.execute("SELECT * from USERS ORDER BY id DESC")
        if len(result) == 0:
            return []
        else:
            for row in result:
                yield User(*row)

    def getAllStorages(self):
        result = self.worker.execute("SELECT * from STORAGE")
        if len(result) == 0:
            return []
        else:
            for row in result:
                yield Storage(*row)

    def getDispatchListByDispatchGroupId(self, dispatch_group_id: int):
        result = self.worker.execute("SELECT * from DISPATCH_LIST where dispatch_group_id=?",
                                     values=(dispatch_group_id,))
        if len(result) == 0:
            return None
        else:
            for row in result:
                yield DispatchListItem(*row)

    def getAllDispatchGroupNames(self):
        result = self.worker.execute(
            "SELECT id, dispatch_group_name, description, enabled, show_group_only_for FROM DISPATCH_LIST_GROUP WHERE hidden = 0 ORDER BY priority, dispatch_group_name;")
        if len(result) == 0:
            return []
        else:
            for row in result:
                yield DispatchGroupNameInfo(*row)

    def getEnabledDispatchGroupNames(self):
        result = self.worker.execute(
            "SELECT id, dispatch_group_name, description, enabled, show_group_only_for FROM DISPATCH_LIST_GROUP WHERE enabled = 1 ORDER BY priority, dispatch_group_name;")
        if len(result) == 0:
            return []
        else:
            for row in result:
                yield DispatchGroupNameInfo(*row)

    def enableDispatchGroupName(self, dispatch_group_id):
        self.worker.execute("UPDATE DISPATCH_LIST_GROUP SET enabled=1 WHERE id=?",
                            values=(dispatch_group_id,))

    def disableDispatchGroupName(self, dispatch_group_id):
        self.worker.execute("UPDATE DISPATCH_LIST_GROUP SET enabled=0 WHERE id=?",
                            values=(dispatch_group_id,))

    def getValueFromStorage(self, key):
        result = self.worker.execute("SELECT value FROM storage WHERE key=?", values=(key,))
        if len(result) == 0:
            return None
        else:
            return result[0][0]

    def setValueInfoStorage(self, key, value):
        self.worker.execute("UPDATE STORAGE SET value=? WHERE key=?", values=(value, key))

    def getDispatchGroupInfo(self, dispatch_group_id):
        result = self.worker.execute(
            "SELECT dlg.id, dlg.dispatch_group_name,COUNT(dl.id),SUM(dl.is_assigned),dlg.enabled,dlg.description,dlg.priority,dlg.repeat,dlg.show_comment_with_block,dlg.show_count_of_taken_blocks,dlg.show_group_only_for"
            " FROM DISPATCH_LIST dl LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dl.dispatch_group_id=dlg.id) WHERE dl.dispatch_group_id=? GROUP BY dl.dispatch_group_id",
            values=(dispatch_group_id,))
        if len(result) == 0:
            return None
        else:
            row = result[0]
            return DispatchGroupInfo(
                id=row[0],
                dispatch_group_name=row[1],
                count=row[2],
                assigned_count=row[3],
                free_count=row[2] - row[3],
                enabled=bool(row[4]),
                description=row[5],
                priority=row[6],
                repeat=row[7],
                show_comment_with_block=row[8],
                show_count_of_taken_blocks=row[9],
                show_group_only_for=row[10],
            )

    def getCountOfAssignedBlocksForGroupId(self, dispatch_group_id) -> int:
        return self.worker.execute(
            "SELECT count(dla.uuid) as assignedCount FROM DISPATCH_LIST_ASSIGNS dla "
            "LEFT JOIN DISPATCH_LIST dl ON (dl.id = dla.dispatch_list_id ) "
            "LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.id = dl.dispatch_group_id )"
            " WHERE dla.state='assigned' AND DATE(dla.change_date)=DATE('now') AND dlg.id=?",
            values=(dispatch_group_id,))[0]
