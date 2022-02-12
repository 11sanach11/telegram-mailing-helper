import logging
import pathlib
import shutil
import tempfile
import uuid

from telegram_mailing_help import appConfig
from telegram_mailing_help.db.config import Configuration
from telegram_mailing_help.db.dao import Dao
from telegram_mailing_help.db.migration import Migration

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger()


def test_from_version_0002():
    # dbFile = tempfile.gettempdir() + "/test_migration.db"
    dbFile = tempfile.gettempdir() + "/test_migration_%s.db" % uuid.uuid4()
    shutil.copyfile(str(pathlib.Path(__file__).parent.absolute()) + '/resources/db_dump/dump_migration_0002.db', dbFile)
    config = appConfig.ApplicationConfiguration(
        rootConfigDir='',
        telegramToken='empty',
        logFileName='/tmp/log.log',
        db=Configuration(dbFile=dbFile))
    appConfig._config = config
    m = Migration(config, None)
    m.migrate()
    dao = Dao(config, None)
    data = dao.freeQuery("select * from dispatch_list_group")
    assert len(data) == 2
    assert data[0][0] == 1
    assert data[1][0] == 2
    data = dao.freeQuery("select * from dispatch_list limit 1")
    assert len(data[0]) == 7
    data = dao.freeQuery(
        "select dlg.id, dlg.dispatch_group_name from dispatch_list dl left join dispatch_list_group dlg on (dl.dispatch_group_id=dlg.id) limit 1")
    assert data[0][0] is not None
    assert data[0][1] in ["Тестовые данные", "Еще один список хехе"]


def test_from_version_0006():
    dbFile = tempfile.gettempdir() + "/test_migration_%s.db" % uuid.uuid4()
    shutil.copyfile(str(pathlib.Path(__file__).parent.absolute()) + '/resources/db_dump/dump_migration_0006.db', dbFile)
    config = appConfig.ApplicationConfiguration(
        rootConfigDir='',
        telegramToken='empty',
        logFileName='/tmp/log.log',
        db=Configuration(dbFile=dbFile))
    appConfig._config = config
    m = Migration(config, None)
    m.migrate()
    dao = Dao(config, None)
    assert dao.freeQuery("select repeat from dispatch_list_group limit 1")[0][0] == 1
