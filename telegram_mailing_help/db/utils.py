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
from datetime import datetime


def getDbFullPath(config, botName: str):
    db_suffix = "_%s" % botName if botName else ""
    if config.db.dbFile.startswith("/"):
        fullDbFile = config.db.dbFile + db_suffix
    else:
        fullDbFile = config.rootConfigDir + "/" + config.db.dbFile + db_suffix
    return fullDbFile


def dictFactory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def isoDatetimeStringToDatetime(isoDatetimeString: str):
    return datetime.strptime(isoDatetimeString)
