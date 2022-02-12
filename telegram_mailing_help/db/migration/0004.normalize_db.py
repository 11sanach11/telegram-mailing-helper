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
import shutil
from datetime import datetime

from yoyo import step

from telegram_mailing_help import appConfig
from telegram_mailing_help.db import utils


# def copy_database_step(conn):
#     if appConfig._config is not None:
#         dbFile = utils.getDbFullPath(appConfig._config)
#         shutil.copyfile(dbFile, dbFile + "_copy_before_0004_normalize_%s" % datetime.now().isoformat())


steps = [
    # step(copy_database_step),
    step(
        "CREATE TABLE DISPATCH_LIST_GROUP (id INTEGER PRIMARY KEY, dispatch_group_name TEXT NOT NULL, social_network TEXT NULL, description TEXT, enabled BOOLEAN);",
        "DROP TABLE DISPATCH_LIST_GROUP;"),
    step(
        "INSERT INTO DISPATCH_LIST_GROUP (id, dispatch_group_name, social_network, description, enabled) SELECT null,dispatch_group_name,null,description,enabled from DISPATCH_LIST dl GROUP BY dispatch_group_name;",
        "DELETE FROM DISPATCH_LIST_GROUP;"),
    step("ALTER TABLE DISPATCH_LIST ADD COLUMN dispatch_group_id INTEGER;"),
    step(
        "CREATE TABLE DISPATCH_LIST_NEW (id INTEGER PRIMARY KEY, dispatch_group_id INTEGER, links_values_butch TEXT, created TEXT, _check_sum TEXT, _version INTEGER NOT NULL, is_assigned BOOLEAN);",
        "DROP TABLE DISPATCH_LIST_NEW;"),
    step(
        'INSERT INTO DISPATCH_LIST_NEW SELECT dl.id, dlg.id, dl.links_values_butch, dl.created, dl."_check_sum", dl."_version", dl.is_assigned FROM DISPATCH_LIST dl LEFT JOIN DISPATCH_LIST_GROUP dlg ON (dlg.dispatch_group_name = dl.dispatch_group_name )',
        "DELETE FROM DISPATCH_LIST_NEW;"),
    step("DROP TABLE DISPATCH_LIST;"),
    step("ALTER TABLE DISPATCH_LIST_NEW RENAME TO DISPATCH_LIST;"),
    step("CREATE INDEX dispatch_group_id_index on DISPATCH_LIST (dispatch_group_id, created);",
         "DROP INDEX dispatch_group_id_index;"),
    step("CREATE UNIQUE INDEX check_sum_dispatch_list_index on DISPATCH_LIST (_check_sum);",
         "DROP INDEX check_sum_dispatch_list_index;"),
    step("CREATE INDEX dispatch_group_name_index on DISPATCH_LIST_GROUP (dispatch_group_name);",
         "DROP INDEX dispatch_group_name_index;"),
]
