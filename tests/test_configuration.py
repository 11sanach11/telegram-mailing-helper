# -*- coding: utf-8 -*-
from json import loads

import pytest
from dacite import from_dict, MissingValueError, WrongTypeError
from pytest import mark

import telegram_mailing_help.telegramMailingHelper as telegramMailingHelper

testConfiguration = '''
{
    "db":{
        "dbFile": "%(dbfile)s"
        },
    "rootConfigDir": "%(rootconfigdir)s",
    "telegramToken": "token"
}
'''


@mark.parametrize("replace", [
    {"dbfile": "some/path/to/file", "rootconfigdir": "aaa"},
    {"dbfile": "путь", "rootconfigdir": "abc"},
    {"dbfile": "kkkk", "rootconfigdir": "/a/b"},
    {"dbfile": "русский/english", "rootconfigdir": "None"},
    {"dbfile": "english/русский", "rootconfigdir": "/A/B/РРР"},
    {"dbfile": "/", "rootconfigdir": "ЛЛЛЛ"}
])
def test_config_db_file(replace):
    configuration = from_dict(telegramMailingHelper.ApplicationConfiguration, loads(testConfiguration % replace))
    assert configuration.db.dbFile == replace["dbfile"]
    assert configuration.rootConfigDir == replace["rootconfigdir"]


def test_rootConfigDir_is_null():
    with pytest.raises(WrongTypeError):
        from_dict(telegramMailingHelper.ApplicationConfiguration,
                  loads('''{"rootConfigDir":null,"telegramToken":"zzz"}''')).rootConfigDir is None
    with pytest.raises(MissingValueError):
        assert from_dict(telegramMailingHelper.ApplicationConfiguration, loads('''{}''')).rootConfigDir is None
