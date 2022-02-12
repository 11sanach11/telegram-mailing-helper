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
import pathlib
from logging import getLogger

from yoyo import get_backend
from yoyo import read_migrations

from telegram_mailing_help.db.utils import getDbFullPath

log = getLogger("migration")


class Migration:
    def __init__(self, config, botName: str):
        self.migrations = read_migrations(str(pathlib.Path(__file__).parent.absolute()) + '/migration')
        self.backend = get_backend("sqlite:///" + getDbFullPath(config, botName))

    def migrate(self):
        log.info("Start migration...")
        with self.backend.lock():
            # Apply any outstanding migrations
            self.backend.apply_migrations(self.backend.to_apply(self.migrations))
        log.info("Migration: success!")

    def rollback(self):
        with self.backend.lock():
            # Rollback all migrations
            self.backend.rollback_migrations(self.backend.to_rollback(self.migrations))
