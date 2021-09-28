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
import threading
import time
from datetime import datetime

from telegram import InlineKeyboardMarkup, \
    InlineKeyboardButton, Update, ParseMode
from telegram.ext import CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
from telegram.ext import Updater

from telegram_mailing_help.db.dao import Dao, User, UserState
from telegram_mailing_help.logic.listPreparation import Preparation

log = logging.getLogger("mailingBot")


def timeit(func):
    def timed(*args, **kwargs):
        raisedException = None
        execMessage = "OK"
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            execMessage = "%s" % e
            raisedException = e
        try:
            updateObj = args[1] if len(args) >= 3 else args[0]
            userId = updateObj.effective_user.id
            responseText = updateObj.effective_message.text[0:1000].replace("\n", " ") \
                if updateObj.effective_message.text else "<empty>"
        except Exception as e:
            userId = "<can't get: %s>" % e
            responseText = "<can't get: %s>" % e
        timer = int((time.time() - start_time) * 100000) / 100.0
        log.info(
            'TBOT: %(method)s %(userId)s: %(message)s (exec: %(timer)s ms): response: %(response)s',
            {
                'message': execMessage,
                'userId': userId,
                'timer': timer,
                'method': func.__name__,
                'response': responseText,
            })
        if raisedException:
            raise raisedException
        return result

    return timed


# unicode codes: https://apps.timwhitlock.info/emoji/tables/unicode
class MailingBot:
    def __init__(self, config, db: Dao, preparation: Preparation, ):
        self.db = db
        self.preparation = preparation
        self.daemon = True
        self.updater = Updater(token=config.telegramToken)
        self.dispatcher = self.updater.dispatcher
        self.dispatcher.add_handler(CommandHandler('start', self.commandMain))
        self.dispatcher.add_handler(CommandHandler('info', self.commandInfo))
        self.dispatcher.add_handler(
            CallbackQueryHandler(pattern=r"^get_dispatch_group_names$", callback=self.getDispatchGroupNames))
        self.dispatcher.add_handler(CallbackQueryHandler(pattern=r"^get_links_from: (.+)$", callback=self.getLinksFrom))
        self.dispatcher.add_handler(
            CallbackQueryHandler(pattern=r"^confirm_unassign_link_for: (.+)$", callback=self.confirmUnassignLinksItem))
        self.dispatcher.add_handler(
            CallbackQueryHandler(pattern=r"^unassign_link_for: (.+)$", callback=self.unassignLinksItem))
        self.dispatcher.add_handler(
            CallbackQueryHandler(pattern=r"^get_description_for: (.+)$", callback=self.getDescriptionFor))

        unknown_handler = MessageHandler(Filters.command, self.unknown)
        self.dispatcher.add_handler(unknown_handler)

    @timeit
    def commandInfo(self, update: Update, context):
        message = update.message or update.callback_query.message
        text = self.db.getValueFromStorage("info_message") or "Информация по боту"
        message.reply_text(text, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="Ок, понятно, иду в бой!",
                                   callback_data="get_dispatch_group_names")]]))
        if update.callback_query:
            update.callback_query.answer()

    def sendFreeMessageToRegisteredUser(self, userId, message):
        self.updater.bot.send_message(chat_id=userId,
                                      text=message)

    @timeit
    def commandMain(self, update: Update, context):
        message = update.message or update.callback_query.message
        user = self.db.getUserByTelegramId(str(message.chat.id))
        if user is None or user.state != UserState.CONFIRMED.value:
            text = "Вы не найдены в базе данных бота, добаление требует обращение к куратору, пожалуйста попросите " \
                   "ответственного человека, чтобы вас добавили, до этого времени доступа до бота у вас не будет!"
            if user is None:
                user = User(
                    id=None,
                    telegram_id=str(message.chat.id),
                    name="%s %s (%s)" % (message.chat.first_name, message.chat.last_name, message.chat.username),
                    state=UserState.NEW.value,
                    created=datetime.now().isoformat()
                )
                self.db.saveUser(user)
                telegramUserIdForNotification = self.db.getValueFromStorage(
                    "send_notification_about_new_user_to_telegram_id")
                try:
                    if telegramUserIdForNotification:
                        self.sendFreeMessageToRegisteredUser(
                            int(telegramUserIdForNotification),
                            "Новый пользователь %(user)s добавился в бот, подтвердить его можно здесь: %(admin_url)s" %
                            {"user": user.name,
                             "admin_url": self.db.getValueFromStorage("admin_url") + "/pages/users.html"})
                except Exception:
                    log.exception("Can't send message about new user into %s", telegramUserIdForNotification)
            message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="Попробовать еще раз",
                                       callback_data="get_dispatch_group_names")]]))
        else:
            message.reply_text(text="Инфо по работе бота здесь: /info")
            buttons = [[InlineKeyboardButton(text=groupName.dispatch_group_name,
                                             callback_data="get_links_from: %s" % groupName.id),
                        InlineKeyboardButton(text=self.db.getValueFromStorage("description_button_label"),
                                             callback_data="get_description_for: %s" % groupName.id)]
                       for groupName in self.db.getEnabledDispatchGroupNames()]
            if buttons:
                text = "Выберите рассылку из предложенных, %s:" % user.name
                message.reply_text(text,
                                   reply_markup=InlineKeyboardMarkup(buttons))
            else:
                text = "\U000026A0 На текущий момент нет ни одной активной рассылки, уточните почему, у куратора"
                message.reply_text(text, reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="Попробовать еще раз",
                                           callback_data="get_dispatch_group_names")]]))
        if update.callback_query:
            update.callback_query.answer()

    @timeit
    @staticmethod
    def unknown(update: Update, context: CallbackContext):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Такую команду бот не поддерживает, попробуйте сначала /start")

    def _checkCountOfLeftBlocksAndSendNotification(self, dao: Dao, notifTelegramId, dispatchListGroupId):
        groupInfo = dao.getDispatchGroupInfo(dispatchListGroupId)
        countOfFreeBlocksTrigger = int(dao.getValueFromStorage("count_of_free_blocks_before_notification"))
        if groupInfo.free_count == countOfFreeBlocksTrigger:
            self.sendFreeMessageToRegisteredUser(
                notifTelegramId,
                "\U000026A0 У списка %s осталось %s свободных блоков, может быть пора добавить новые, добавить можно в админке: %s/pages/dispatch_lists.html" %
                (groupInfo.dispatch_group_name, countOfFreeBlocksTrigger, dao.getValueFromStorage("admin_url")))

    @timeit
    def getLinksFrom(self, update: Update, context):
        message = update.message or update.callback_query.message
        user = self.db.getUserByTelegramId(str(message.chat.id))
        if UserState(user.state) == UserState.CONFIRMED:
            dispatchListGroupId = int(update.callback_query.data[len("get_links_from: "):])
            dispatchListGroup = self.db.getDispatchListGroupById(dispatchListGroupId)

            if dispatchListGroup.enabled:

                text, dispatchListId, already_assigned_amount = self.preparation.getAndAssignDispatchList(user,
                                                                                                          dispatchListGroup.id)
                repeatListInfo = ""
                if dispatchListGroup.repeat > 1 and already_assigned_amount is not None:
                    repeatListInfo = " (повторная выдача: %s)" % (already_assigned_amount + 1)
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text="<b style='text-align: center;'>%s%s:</b>"
                                              % (dispatchListGroup.dispatch_group_name, repeatListInfo),
                                         parse_mode=ParseMode.HTML)
                if (dispatchListGroup.show_comment_with_block):
                    context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=" <b style='text-align: center;'>Описание</b>: %s" % dispatchListGroup.description,
                                             parse_mode=ParseMode.HTML)
                notifTelegramId = self.db.getValueFromStorage("send_notification_only_5_blocks_left_to_telegram_id");
                if (notifTelegramId):
                    threading.Thread(target=self._checkCountOfLeftBlocksAndSendNotification,
                                     args=(self.db, notifTelegramId, dispatchListGroup.id)).start()
                secondLineOfKeybord = []
                if dispatchListId:
                    secondLineOfKeybord.append(InlineKeyboardButton(
                        text="\U000021A9 Вернуть",
                        callback_data="confirm_unassign_link_for: %s" % dispatchListId))
                secondLineOfKeybord.append(InlineKeyboardButton(text="\U0001F4C3 Выбрать другой список",
                                                                callback_data="get_dispatch_group_names"))
                update.callback_query.message.reply_text(text,
                                                         reply_markup=InlineKeyboardMarkup(
                                                             [
                                                                 [InlineKeyboardButton(
                                                                     text="\U000027A1 %s: след. блок" % dispatchListGroup.dispatch_group_name,
                                                                     callback_data="get_links_from: %s" % dispatchListGroup.id)],
                                                                 secondLineOfKeybord
                                                             ]))
            else:
                update.callback_query.message.reply_text(
                    "Выбранный список более недоступен",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="\U0001F4C3 Выбрать другой список",
                                               callback_data="get_dispatch_group_names")]]
                    ))
            update.callback_query.answer()
        else:
            message.reply_text("Получить данные не удалось, попробуйте позже или еще раз")

    @timeit
    def confirmUnassignLinksItem(self, update: Update, context):
        message = update.message or update.callback_query.message
        dispatchListGroupId = int(update.callback_query.data[len("confirm_unassign_link_for: "):])
        message.reply_text(
            text="<b>Вы уверены что хотите вернуть блок обратно боту? Нажмите Да, если не обработали его</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="\U00002611 Да",
                                       callback_data="unassign_link_for: %s" % dispatchListGroupId),
                  InlineKeyboardButton(text="\U000026D4 Нет",
                                       callback_data="get_dispatch_group_names")]])
        )
        update.callback_query.answer()

    @timeit
    def unassignLinksItem(self, update: Update, context):
        message = update.message or update.callback_query.message
        user = self.db.getUserByTelegramId(str(message.chat.id))
        if UserState(user.state) == UserState.CONFIRMED:
            dispatchListGroupId = int(update.callback_query.data[len("unassign_link_for: "):])
            unassignedDispatchList = self.preparation.unassignDispatchListFromUser(user, dispatchListGroupId)
            if unassignedDispatchList and not unassignedDispatchList.is_assigned:
                text = "<b>Хорошо, блок вернулся обратно боту, теперь его снова может взять кто-то другой, или вы, если успеете :)</b>"
            else:
                text = "<b>Блок не найден, видимо он уже был возвращен</b>"
            message.reply_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="\U0001F4C3 Выбрать другой список",
                                           callback_data="get_dispatch_group_names")]])
            )
            update.callback_query.answer()
        else:
            message.reply_text("Получить данные не удалось, попробуйте позже или еще раз")

    @timeit
    def getDescriptionFor(self, update: Update, context):
        message = update.message or update.callback_query.message
        user = self.db.getUserByTelegramId(str(message.chat.id))
        if UserState(user.state) == UserState.CONFIRMED:
            dispatchListGroupId = int(update.callback_query.data[len("get_description_for: "):])
            dispatchListGroup = self.db.getDispatchListGroupById(dispatchListGroupId)
            text = dispatchListGroup.description
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Описание для <b style='text-align: center;'>%s</b>: %s" %
                                          (dispatchListGroup.dispatch_group_name, text),
                                     parse_mode=ParseMode.HTML)
            update.callback_query.answer()
        else:
            message.reply_text("Получить данные не удалось, попробуйте позже или еще раз")

    @timeit
    def getDispatchGroupNames(self, update: Update, context):
        self.commandMain(update, context)

    def start(self):
        # self.updater.start_webhook()
        self.updater.start_polling()

    def stop(self):
        self.updater.stop()
