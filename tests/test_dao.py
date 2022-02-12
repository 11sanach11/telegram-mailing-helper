import logging
import tempfile
import threading
import uuid
from datetime import datetime

from telegram_mailing_help.appConfig import ApplicationConfiguration
from telegram_mailing_help.db.config import Configuration
from telegram_mailing_help.db.dao import Dao, UserState, DispatchGroupInfo, DispatchListGroupItem, Storage
from telegram_mailing_help.db.dao import DispatchListItem
from telegram_mailing_help.db.dao import User
from telegram_mailing_help.db.migration import Migration
from tests.test_utils import CountDownLatch

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

log = logging.getLogger()

config = ApplicationConfiguration(
    rootConfigDir='',
    telegramToken='empty',
    logFileName='/tmp/log.log',
    db=Configuration(dbFile=tempfile.gettempdir() + "/test_migration_%s.db" % uuid.uuid4()))
m = Migration(config, None)
m.migrate()

dao = Dao(config, None)


def test_save_dispatch_list_item():
    item = DispatchListItem(
        id=None,
        dispatch_group_id=777,
        links_values_butch="l1\nl3",
        created=datetime.now().isoformat())
    item = dao.saveDispatchList(item)
    assert item.id != 0
    rezFromDaoById = dao.getDispatchListById(item.id)
    assert item == rezFromDaoById

    item = DispatchListItem(
        id=None,
        dispatch_group_id=777,
        links_values_butch="l1\nl2",
        created=datetime.now().isoformat())
    item = dao.saveDispatchList(item)
    rezFromDaoById = dao.getDispatchListById(item.id)
    assert item == rezFromDaoById
    assert len(list(dao.getDispatchListByDispatchGroupId(item.dispatch_group_id))) == 2

    item.is_assigned = True
    currentId = item.id
    item = dao.saveDispatchList(item)
    rezFromDaoById = dao.getDispatchListById(currentId)
    assert rezFromDaoById.is_assigned == True
    assert item.id == currentId
    assert rezFromDaoById.id == currentId


def test_get_dispatch_groups():
    dao.freeQuery("delete from DISPATCH_LIST_GROUP;")
    item1 = DispatchListGroupItem(
        id=None,
        dispatch_group_name="gr1",
        social_network="soc_net",
        description="descr")
    item2 = DispatchListGroupItem(
        id=None,
        dispatch_group_name="gr3",
        social_network="soc_net",
        description="descr")
    item3 = DispatchListGroupItem(
        id=None,
        dispatch_group_name="gr2",
        social_network="soc_net",
        description="descr")
    for item in [item1, item2, item3]:
        dao.saveDispatchListGroup(item)

    assert dao.freeQuery("select count(*) from DISPATCH_LIST_GROUP")[0][0] == 3
    assert sorted(map(lambda x: x.dispatch_group_name, list(dao.getAllDispatchGroupNames()))) == ["gr1", "gr2", "gr3"]

    item3.description = "new description"
    dao.saveDispatchListGroup(item3)

    item3FromBase = dao.getDispatchListGroupById(item3.id)
    assert item3FromBase.description == "new description"
    assert dao.freeQuery("select count(*) from DISPATCH_LIST_GROUP")[0][0] == 3


def test_get_info_about_dispatch_group():
    gr_name = "test_gr_name_%s" % uuid.uuid4()

    dispatchListGroupItem = DispatchListGroupItem(
        id=None,
        dispatch_group_name=gr_name,
        description="test_data",
        social_network="VK"
    )

    dispatchListGroupItem = dao.saveDispatchListGroup(dispatchListGroupItem)

    item1 = DispatchListItem(
        id=None,
        dispatch_group_id=dispatchListGroupItem.id,
        links_values_butch="l1\nl2\n%s" % uuid.uuid4(),
        created=datetime.now().isoformat(),
        is_assigned=True)
    item2 = DispatchListItem(
        id=None,
        dispatch_group_id=dispatchListGroupItem.id,
        links_values_butch="l1\nl2\n%s" % uuid.uuid4(),
        created=datetime.now().isoformat())
    item3 = DispatchListItem(
        id=None,
        dispatch_group_id=dispatchListGroupItem.id,
        links_values_butch="l1\nl2\n%s" % uuid.uuid4(),
        created=datetime.now().isoformat())
    for item in [item1, item2, item3]:
        dao.saveDispatchList(item)
    assert dao.getDispatchGroupInfo(dispatchListGroupItem.id) == \
           DispatchGroupInfo(id=dispatchListGroupItem.id,
                             dispatch_group_name=gr_name,
                             description="test_data",
                             count=3,
                             assigned_count=1,
                             free_count=2,
                             enabled=True)
    assert dao.getDispatchGroupInfo(gr_name + "_failed") is None


def multi_thread(index, counter, net_name):
    item = DispatchListItem(
        id=None,
        dispatch_group_id=877,
        links_values_butch="l1\nl2\nuser_%s" % uuid.uuid4(),
        created=datetime.now().isoformat())
    log.info("test_net_id: %s", dao.saveDispatchList(item).id)
    counter.count_down()


def test_multi_threading_add_dispatch_list():
    net_name = "test_net_%s" % uuid.uuid4()
    attempts = 100
    counter = CountDownLatch(attempts)
    for i in range(attempts):
        threading.Thread(target=multi_thread, args=(i, counter, net_name)).start()

    counter.wait(timeout=5)
    rez = list(dao.getDispatchListByDispatchGroupId(877))
    assert len(rez) == attempts, "wrong records count, should be %s" % attempts


def test_save_user():
    user = User(
        id=None,
        telegram_id="tel_id_333",
        name="telegram_name",
        state=UserState.NEW.value,
        created=datetime.now().isoformat()
    )
    user = dao.saveUser(user)
    assert user.id is not None, "User id should be set after save"
    userFromBaseById = dao.getUserById(user.id)
    userFromBaseByTelegramId = dao.getUserByTelegramId(user.telegram_id)
    assert user == userFromBaseById
    assert user == userFromBaseByTelegramId


def test_user_telegram_id_unique_index():
    test_user_name = "name_%s" % uuid.uuid4()
    user1 = User(
        id=None,
        telegram_id="tel_id_1",
        name=test_user_name,
        state=UserState.NEW.value,
        created=datetime.now().isoformat()
    )
    user2 = User(
        id=None,
        telegram_id="tel_id_2",
        name=test_user_name,
        state=UserState.NEW.value,
        created=datetime.now().isoformat()
    )
    user1 = dao.saveUser(user1)
    user2 = dao.saveUser(user2)
    testUsersCount = dao.freeQuery("select count(*) from users where name='%s'" % test_user_name)[0][0]
    assert testUsersCount == 2
    assert user1.id is not None
    assert user2.id is not None


def test_check_storage():
    dao.freeQuery("INSERT INTO STORAGE VALUES ('key','value','description')")
    assert dao.getValueFromStorage("key") == "value"
    dao.setValueInfoStorage("key", "другое value")
    assert dao.getValueFromStorage("key") == "другое value"
    assert dao.getValueFromStorage("unavailable") is None


def test_assign_and_free_block():
    dispatchGroup = dao.saveDispatchListGroup(
        DispatchListGroupItem(
            id=None,
            dispatch_group_name="kkkzaanaonostra",
            social_network="test",
            description="description"
        )
    )
    dispatchList = dao.saveDispatchList(DispatchListItem(
        id=None,
        dispatch_group_id=dispatchGroup.id,
        links_values_butch="123_%s" % uuid.uuid4(),
        created=datetime.now().isoformat()
    ))
    user = dao.saveUser(User(
        id=None,
        telegram_id="tg_id_%s" % uuid.uuid4(),
        name="test Юзер name",
        state=UserState.CONFIRMED.value,
        created=datetime.now().isoformat()
    ))
    assert dao.getDispatchGroupInfo(dispatchGroup.id).free_count == 1
    dao.assignBlockIntoUser(user, dispatchList, True)
    assert dao.getDispatchGroupInfo(dispatchGroup.id).free_count == 0
    dao.freeAssignedBlockFromUser(user, dispatchList)
    assert dao.getDispatchGroupInfo(dispatchGroup.id).free_count == 1
    user2 = dao.saveUser(User(
        id=None,
        telegram_id="tg_id_%s" % uuid.uuid4(),
        name="test Юзер name",
        state=UserState.CONFIRMED.value,
        created=datetime.now().isoformat()
    ))
    dispatchList = dao.getDispatchListById(dispatchList.id)
    dao.assignBlockIntoUser(user2, dispatchList, True)
    assert dao.getDispatchGroupInfo(dispatchGroup.id).free_count == 0
    assignsForTestedDispatchList = dao.freeQuery(
        "Select * from dispatch_list_assigns where dispatch_list_id=%s" % dispatchList.id)
    assert len(assignsForTestedDispatchList) == 2
    assert assignsForTestedDispatchList[0][3] == "rollback"
    assert assignsForTestedDispatchList[1][3] == "assigned"
