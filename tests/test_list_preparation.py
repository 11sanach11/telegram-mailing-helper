# -*- coding: utf-8 -*-
import logging
import random
import tempfile
import threading
import time
import uuid
from datetime import datetime
from time import sleep

from tests.test_utils import CountDownLatch

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from telegram_mailing_help.db.config import Configuration
from telegram_mailing_help.db.dao import Dao, User, UserState, DispatchListItem, DispatchListGroupItem
from telegram_mailing_help.db.migration import Migration
from telegram_mailing_help.logic.listPreparation import Preparation
from telegram_mailing_help.appConfig import ApplicationConfiguration

log = logging.getLogger()

config = ApplicationConfiguration(
    rootConfigDir='',
    telegramToken='empty',
    logFileName='/tmp/test_log.log',
    db=Configuration(dbFile=tempfile.gettempdir() + "/test_migration_%s.db" % uuid.uuid4()))
m = Migration(config)
m.migrate()

dao = Dao(config)
preparation = Preparation(config, dao)


def test_small_count_of_data():
    dispatch_group_name = "VK bla bla идт ид тп ъъъъопа %s" % uuid.uuid4()
    result = preparation.addDispatchList(
        dispatch_group_name,
        "описание",
        ["only you"],
        10,
        True,
        False,
        False,
        "",
    )
    while result["state"] != "finished":
        time.sleep(0.05)
        result = preparation.getPreparationState(result["id"])
    assert result["processed"] == 1
    assert dao.getDispatchGroupInfo(dao.getDispatchListGroupByName(dispatch_group_name).id).count == 1


def test_enough_data():
    links_count = 1200
    group_size = 103
    dispatch_group_name = "ОК за свободу прав белых женщин %s" % uuid.uuid4()
    result = preparation.addDispatchList(
        dispatch_group_name,
        "вот какое-то такое описание",
        ["@tralivali_%s" % i for i in range(links_count)],
        group_size,
        False,
        True,
        False,
        "")
    while result["state"] != "finished":
        time.sleep(0.05)
        result = preparation.getPreparationState(result["id"])
    common_count_of_rows = links_count // group_size + (bool(links_count % group_size) * 1)
    assert result["processed"] == common_count_of_rows
    assert dao.getDispatchGroupInfo(
        dao.getDispatchListGroupByName(dispatch_group_name).id).free_count == common_count_of_rows
    assert dispatch_group_name in map(lambda x: x.dispatch_group_name, list(dao.getAllDispatchGroupNames()))


def test_assign_dispatch_lists():
    count_of_disp_list = 100
    count_of_users = 24

    def assign_free_dispatch_list_item(userObj: User, dispatch_group_id: int, counter: CountDownLatch):
        sleep(0.001 * random.randint(1, 50))
        preparation.getAndAssignDispatchList(userObj, dispatch_group_id)
        counter.count_down()

    unique_id = str(uuid.uuid4())
    users = [User(id=None,
                  telegram_id="tid_%s_%s" % (unique_id, i),
                  name="test_name_%s" % i,
                  state=UserState.CONFIRMED.value,
                  created=datetime.now().isoformat())
             for i in range(0, count_of_users)]
    for user in users:
        dao.saveUser(user)

    gr_name = "gr_name_%s" % unique_id

    dispatchListGroup = dao.saveDispatchListGroup(DispatchListGroupItem(
        id=None,
        dispatch_group_name=gr_name,
        description="just description",
        social_network="zzz"
    ))

    dispatchLists = [DispatchListItem(id=None,
                                      dispatch_group_id=dispatchListGroup.id,
                                      links_values_butch="links_%s" % i,
                                      is_assigned=False,
                                      created=datetime.now().isoformat())
                     for i in range(0, count_of_disp_list)]
    for item in dispatchLists:
        dao.saveDispatchList(item)

    assert dao.getDispatchGroupInfo(dispatchListGroup.id).count == count_of_disp_list

    counter = CountDownLatch(count_of_disp_list)
    for i in range(0, count_of_disp_list):
        threading.Thread(target=assign_free_dispatch_list_item,
                         args=(users[i % len(users)], dispatchListGroup.id, counter)).start()
    # for i in range(0, count_of_disp_list):
    #     assign_free_dispatch_list_item(users[i % len(users)], gr_name, counter)

    counter.wait(timeout=15)

    dispatchGroupInfo = dao.getDispatchGroupInfo(dispatchListGroup.id)
    assert dispatchGroupInfo.count == count_of_disp_list, "wrong full value of records"
    assert dispatchGroupInfo.free_count == 0, "there is no free butches should be available"
    assert dispatchGroupInfo.assigned_count == count_of_disp_list, "all butches should be assigned"


def test_repeat_block_assigns():
    user_uniq_id = str(uuid.uuid4())
    users = [User(id=None,
                  telegram_id="tid_%s_%s" % (user_uniq_id, i),
                  name="test_name_%s" % i,
                  state=UserState.CONFIRMED.value,
                  created=datetime.now().isoformat())
             for i in range(0, 5)]
    for user in users:
        dao.saveUser(user)

    groups = [DispatchListGroupItem(
        id=None,
        dispatch_group_name="gr_%s" % i,
        description="just description",
        social_network="zzz",
        repeat=i
    ) for i in range(1, 5)]

    for group in groups:
        dao.saveDispatchListGroup(group)
        dispatchLists = [DispatchListItem(id=None,
                                          dispatch_group_id=group.id,
                                          links_values_butch="%s_%s" % (group.id, i),
                                          created=datetime.now().isoformat()
                                          ) for i in range(0, 5)]
        for dispatchList in dispatchLists:
            dao.saveDispatchList(dispatchList)

    text1, did1, assingedAmount1 = preparation.getAndAssignDispatchList(users[0], groups[0].id)
    text2, did2, assingedAmount2 = preparation.getAndAssignDispatchList(users[1], groups[0].id)
    assert text1 != text2, "should return different items for different users too"
    assert did1 != did2, "should return different items for different users too"
    text1, did1, assingedAmount1 = preparation.getAndAssignDispatchList(users[0], groups[1].id)
    text2, did2, assingedAmount2 = preparation.getAndAssignDispatchList(users[1], groups[1].id)
    text3, did3, assingedAmount3 = preparation.getAndAssignDispatchList(users[2], groups[1].id)
    assert text1 == text2, "should return the same items for different users too because repeat is 2"
    assert did1 == did2, "should return the same items for different users too because repeat is 2"
    assert text2 != text3, "should return different items because the amount of repeat had filled"
    text1, did1, assingedAmount1 = preparation.getAndAssignDispatchList(users[0], groups[2].id)
    text2, did2, assingedAmount2 = preparation.getAndAssignDispatchList(users[0], groups[2].id)
    text3, did3, assingedAmount3 = preparation.getAndAssignDispatchList(users[0], groups[2].id)
    text4, did4, assingedAmount4 = preparation.getAndAssignDispatchList(users[0], groups[2].id)
    text5, did5, assingedAmount5 = preparation.getAndAssignDispatchList(users[0], groups[2].id)
    text6, did6, assingedAmount6 = preparation.getAndAssignDispatchList(users[0], groups[2].id)
    assert text1 != text2, "should return different items because for one user must be different blocks"
    assert len(text6) > 10, "should be message about not-available blocks"
    text7, did7, assingedAmount7 = preparation.getAndAssignDispatchList(users[1], groups[2].id)
    assert len(text7) < 10, "for another user should be free blocks because repeat=3"
    text8, did8, assingedAmount8 = preparation.getAndAssignDispatchList(users[2], groups[2].id)
    assert text7 == text8, "messages for diff user with repeat=3"
    preparation.unassignDispatchListFromUser(users[0], did5)
    text9, did9, assingedAmount9 = preparation.getAndAssignDispatchList(users[0], groups[2].id)
    assert text9 == text5, "block was returned, and now busied back"
    assert did9 == did5, "block was returned, and now busied back"

    textData = []

    for r in range(0, 6):
        for u in range(0, 2):
            textData.append(preparation.getAndAssignDispatchList(users[u], groups[3].id))
    preparation.unassignDispatchListFromUser(users[0], textData[0][1])
    preparation.unassignDispatchListFromUser(users[1], textData[3][1])
    text10, did10, assingedAmount10 = preparation.getAndAssignDispatchList(users[0], groups[3].id)
    text11, did11, assingedAmount11 = preparation.getAndAssignDispatchList(users[1], groups[3].id)
    assert text10 == textData[0][0]
    assert text11 == textData[3][0]
