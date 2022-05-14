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
import logging
import numbers
import threading
import time
import uuid
from datetime import datetime

from tabulate import tabulate

from telegram_mailing_help.db.dao import Dao, DispatchListItem, User, DispatchListGroupItem
from telegram_mailing_help.db.daoExp import OptimisticLockException

log = logging.getLogger("helperLogic")


class Preparation:

    def __init__(self, config, dao: Dao):
        self.dao = dao
        self.config = config
        self._assignLock = threading.Lock()
        self.listPreparationProcessingState = {}

    @staticmethod
    def _chunks(lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def _addChunksOfDispatchList(self, dispatchTemplate: DispatchListItem, links, devideBy, stateUuid: str):
        start_time = time.time()
        log.debug("Start preparation for uuid: %s", stateUuid)
        countOfAdded = 0
        totalCount = int(len(links) / devideBy)
        for chunk in self._chunks(links, devideBy):
            dispatchTemplate.id = None
            dispatchTemplate.links_values_butch = "\n".join(chunk)
            self.dao.saveDispatchList(dispatchTemplate)
            countOfAdded += 1
            self.listPreparationProcessingState[stateUuid] = \
                {"id": stateUuid, "state": "inProcess", "totalCount": totalCount, "processed": countOfAdded}
        self.listPreparationProcessingState[stateUuid] = \
            {"id": stateUuid, "state": "finished", "totalCount": totalCount, "processed": countOfAdded}
        timer = int((time.time() - start_time) * 100000) / 100.0
        log.debug("Finish preparation for %s, exec time: %s ms, wait 25 sec before remove record", stateUuid, timer)
        time.sleep(25)
        del self.listPreparationProcessingState[stateUuid]
        log.debug("Record about preparation %s must be removed", stateUuid)

    def getPreparationState(self, stateUuid: str):
        return self.listPreparationProcessingState.get(stateUuid, {"id": stateUuid, "state": "UNKNOWN"})

    def addDispatchList(self, dispatch_group_name: str, description: str, links: list, devideBy: int,
                        disableByDefault: bool, showCommentWithBlock: bool, showCountOfTakenBlocks: bool,
                        showGroupOnlyFor: str,
                        dispatch_group_id: int = None,
                        repeatTimes: int = 1, ):
        stateUuid = str(uuid.uuid4())
        self.listPreparationProcessingState[stateUuid] = \
            {"id": stateUuid, "state": "starting", "totalCount": int(len(links) / devideBy), "processed": 0}
        dispatchListGroup = self.dao.getDispatchListGroupById(dispatch_group_id) if dispatch_group_id \
            else self.dao.getDispatchListGroupByName(dispatch_group_name)
        if not dispatchListGroup:
            dispatchListGroup = DispatchListGroupItem(
                id=None,
                dispatch_group_name=dispatch_group_name,
                social_network=None,
                description=description,
                enabled=not disableByDefault,
                show_comment_with_block=showCommentWithBlock,
                show_count_of_taken_blocks=showCountOfTakenBlocks,
                show_group_only_for=showGroupOnlyFor,
                repeat=repeatTimes
            )
            dispatchListGroup = self.dao.saveDispatchListGroup(dispatchListGroup)

        dispatchTemplate = DispatchListItem(
            id=None,
            dispatch_group_id=dispatchListGroup.id,
            links_values_butch=None,
            is_assigned=False,
            created=datetime.now().isoformat()
        )

        threading.Thread(daemon=True, target=self._addChunksOfDispatchList,
                         args=(dispatchTemplate, links, devideBy, stateUuid)).start()

        return self.listPreparationProcessingState.get(stateUuid, {})

    def unassignDispatchListFromUser(self, user: User, dispatch_list_id: int):
        with self._assignLock:
            dispatchList = self.dao.getDispatchListById(dispatch_list_id)
            if dispatchList:
                dispatchList = self.dao.freeAssignedBlockFromUser(user, dispatchList)
        return dispatchList

    def getAndAssignDispatchList(self, user: User, dispatch_group_id: int):
        with self._assignLock:
            attempt = 1
            item = None
            while attempt < 5:
                try:
                    item, setIs_assigned, already_assigned_amount = self.dao.getFreeDispatchListItem(dispatch_group_id,
                                                                                                     user)
                    if item:
                        self.dao.assignBlockIntoUser(user, item, setIs_assigned)
                    break
                except OptimisticLockException:
                    log.warning("Can't assign dispatchList with id: %s optimistic lock, attempt: %s", item.id, attempt)
                    item = None
                attempt += 1

            if item:
                return (item.links_values_butch, item.id, already_assigned_amount)
            else:
                return ("Свободных блоков для данного списка больше нет," \
                        " пожалуйста обратитесь к куратору для их добавления или для скрытия данного списка", None,
                        None)

    def prepareReport(self, sqlQuery: str, columns: list):
        result = []
        totalSums = {}
        for s in self.dao.freeQuery(sqlQuery):
            for col in range(1, len(s)):
                if not totalSums.get(col):
                    totalSums[col] = 0
                if s[col] is not None and isinstance(s[col],numbers.Number):
                    totalSums[col]=totalSums[col]+s[col]
            result.append(list(s))
        result.append(["Итого"]+list(totalSums.values()))
        return tabulate(result, headers=columns, tablefmt='grid')
