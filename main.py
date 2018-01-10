#!/usr/bin/env python
# -*- coding: utf-8 -*-

from telegram.ext import Updater, CommandHandler, Job, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import pickle
import subprocess
import textwrap
import time
import telegram
import datetime
import logging
import typing
import emoji
import random
import json
import re
import os


# import threading
# import time
#
#
# class ThreadingExample(object):
#     """ Threading example class
#     The run() method will be started and it will run in the background
#     until the application exits.
#     """
#
#     def __init__(self, interval=1):
#         """ Constructor
#         :type interval: int
#         :param interval: Check interval, in seconds
#         """
#         self.interval = interval
#
#         thread = threading.Thread(target=self.run, args=())
#         thread.daemon = True                            # Daemonize thread
#         thread.start()                                  # Start the execution
#
#     def run(self):
#         """ Method that runs forever """
#         while True:
#             # Do something
#             print('Doing something imporant in the background')
#
#             time.sleep(self.interval)
#
# example = ThreadingExample()


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - \
                            %(message)s', level=logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def last_completed_task_time(tasks: dict):
    return max(list(map(lambda x: tasks[x].dend, list(filter(lambda x: tasks[x].done, tasks)))))


def get_completed_tasks(tasks: dict):
    task_texts = []
    for task in tasks:
        if tasks[task].done is True:
            task_texts.append(task)
    return task_texts


def get_running_tasks(tasks: dict):
    task_texts = []
    for task in tasks:
        if tasks[task].done is False:
            task_texts.append(task)
    return task_texts


class Task:
    def __init__(self, dstart: int):
        self.dstart = dstart
        self.dend = None
        self.done = False
        self.paused = False
        self.pauses = []

    def fdone(self, dend: int) -> int:
        if self.paused:
            self.fcontinue(dend)
        self.dend = dend
        self.done = True
        return self.dend - self.dstart

    def fpause(self, ts: int):
        self.pauses.append([ts])
        self.paused = True

    def ftotallenofpauses(self):
        total = 0
        for pause in self.pauses:
            total += pause[1]
            total -= pause[0]
        return total

    def fnumofpauses(self):
        return len(self.pauses)

    def fcontinue(self, ts: int) -> int:
        self.pauses[-1].append(ts)
        self.paused = False
        time_delta = self.pauses[-1][1] - self.pauses[-1][0]
        return time_delta

    def feffect(self) -> float:
        if self.done:
            total_time = self.dend - self.dstart
            return 100 * (total_time - self.ftotallenofpauses()) / total_time
        else:
            return -1


users = dict()
tasks_info = dict()
admin_id = 107183599

listenfortasks = False
important_tasks = list()
important_tasks_status = list()


def get_token():
    path = os.path.join('res', 'token.json')
    with open(path) as jsn:
        data = json.load(jsn)
    return data['token']


def button(bot, update):
    query = update.callback_query

    occurrences = [m.start() for m in re.finditer('"', query.message['text'])]
    task_text = query.message['text'][occurrences[0]+1:occurrences[-1]]

    #########
    # Start
    #
    if query.data == 'act_start':
        ts = int(time.time())
        tasks_info[task_text] = Task(ts)

        time_delta = ts - last_completed_task_time(tasks_info)
        time_delta = '{:02d}:{:02d}'.format(time_delta // 60, time_delta % 60)

        bot.edit_message_text('Time since last completed task: {}'.format(time_delta), chat_id=query.message.chat_id,
                              message_id=query.message.message_id)

        keyboard = [
            [InlineKeyboardButton(emoji.emojize(":repeat:", use_aliases=True), callback_data='act_pause'),  # Pause
             InlineKeyboardButton(emoji.emojize(":white_check_mark:", use_aliases=True),
                                  callback_data='act_done')]  # Done
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.message.reply_text(emoji.emojize(":hourglass_flowing_sand:", use_aliases=True) +
                                  'You #started: "{}"'.format(task_text), reply_markup=reply_markup)

        # bot.edit_message_text(emoji.emojize(":hourglass_flowing_sand:", use_aliases=True) +
        #                       'You #started: "{}"'.format(task_text), chat_id=query.message.chat_id,
        #                       message_id=query.message.message_id, reply_markup=reply_markup)

    #########
    # Cancel
    #
    elif query.data == 'act_cancel':
        bot.edit_message_text('Ok. You canceled: "{}"'.format(task_text), chat_id=query.message.chat_id,
                              message_id=query.message.message_id)
    #########
    # Pause
    #
    elif query.data == 'act_pause':
        ts = int(time.time())
        tasks_info[task_text].fpause(ts)

        keyboard = [
            [InlineKeyboardButton(emoji.emojize(":arrow_forward:", use_aliases=True),
                                  callback_data='act_continue'),  # Continue
             InlineKeyboardButton(emoji.emojize(":white_check_mark:", use_aliases=True),
                                  callback_data='act_done')]  # Done
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        bot.edit_message_text(emoji.emojize(":rotating_light:", use_aliases=True) +
                              '#Paused: "{}"'.format(task_text), chat_id=query.message.chat_id,
                              message_id=query.message.message_id, reply_markup=reply_markup)
    #########
    # Continue
    #
    elif query.data == 'act_continue':
        ts = int(time.time())
        time_delta = tasks_info[task_text].fcontinue(ts)
        time_delta = '{:02d}:{:02d}'.format(time_delta // 60, time_delta % 60)

        keyboard = [
            [InlineKeyboardButton(emoji.emojize(":repeat:", use_aliases=True), callback_data='act_pause'),  # Pause
             InlineKeyboardButton(emoji.emojize(":white_check_mark:", use_aliases=True),
                                  callback_data='act_done')]  # Done
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        bot.edit_message_text(emoji.emojize(":hourglass_flowing_sand:", use_aliases=True) +
                              '#Continued: "{}". It was paused for {}'.format(task_text, time_delta),
                              chat_id=query.message.chat_id, message_id=query.message.message_id,
                              reply_markup=reply_markup)

    #########
    # Done
    #
    elif query.data == 'act_done':
        pickle.dump(tasks_info, open("dump.pkl", "wb"))

        if task_text in important_tasks:
            important_tasks_status[important_tasks.index(task_text)] = True

        ts = int(time.time())
        time_delta = tasks_info[task_text].fdone(ts)
        time_pauses = tasks_info[task_text].ftotallenofpauses()
        num_pauses = tasks_info[task_text].fnumofpauses()
        effect = tasks_info[task_text].feffect()

        time_delta = '{:02d}:{:02d}'.format(time_delta // 60, time_delta % 60)
        time_pauses = '{:02d}:{:02d}'.format(time_pauses // 60, time_pauses % 60)

        text_send = list()
        text_send.append(emoji.emojize(":white_check_mark:", use_aliases=True) + ' - "{}"'.format(task_text))
        text_send.append(emoji.emojize(":clock2:", use_aliases=True) + ' - {}'.format(time_delta))
        text_send.append(emoji.emojize(":thumbsup:", use_aliases=True) + ' - {:.1f}%'.format(effect))
        text_send.append("Time of pauses: {}".format(time_pauses))
        text_send.append("Number of pauses: {}".format(num_pauses))
        text_send = '\n'.join(text_send)

        bot.edit_message_text(text=text_send, chat_id=query.message.chat_id, message_id=query.message.message_id)
        query.message.reply_text('What do you want to do next? ' + emoji.emojize(":blush:", use_aliases=True) +
                                 '\nCheck status of today /day_status')


def done(bot, update):
    global listenfortasks
    global important_tasks_status

    if listenfortasks:
        text = list()
        text.append('So you have {} tasks for today:'.format(len(important_tasks)))
        important_tasks_status = [False] * len(important_tasks)
        for i, task in enumerate(important_tasks):
            text.append(emoji.emojize(":radio_button:", use_aliases=True) +
                        ' - "{}"'.format(task) +
                        "(let's do /task_{})".format(i))

        text = '\n'.join(text)
        update.message.reply_text(text)
        listenfortasks = False
    else:
        if len(important_tasks) > 0:
            update.message.reply_text('You already have tasks for today')
        else:
            update.message.reply_text('Press /start please')


def day_status(bot, update):
    text = list()

    ##########################
    # All tasks are completed
    if important_tasks_status.count(False) == 0:
        info = bot.getChat(update.message.chat_id)

        user = ''
        if info['first_name']:
            user += info['first_name']
        if info['last_name']:
            if user:
                user += ' '
            user += info['last_name']
        if not user:
            user = 'user'
        text.append('Congratulations, {}! {}'.format(user, emoji.emojize(":tada:", use_aliases=True)))

    ##################
    # There are tasks
    else:
        t = 'task'
        if important_tasks_status.count(False) > 1:
            t += 's'
        text.append('You have {} more {} for today:'.format(important_tasks_status.count(False), t))

    for i, task in enumerate(important_tasks):
        if important_tasks_status[i]:  # Task is completed
            text.append(emoji.emojize(":white_check_mark:", use_aliases=True) + ' - "{}"'.format(task))
        else:
            text.append(emoji.emojize(":radio_button:", use_aliases=True) + ' - "{}"'.format(task) +
                        "(let's do /task_{})".format(i))

    if important_tasks_status.count(False) == 0:
        text.append('Go find something interesting ' + emoji.emojize(":blush:", use_aliases=True))

    text = '\n'.join(text)
    update.message.reply_text(text)


def echo(bot, update):
    if listenfortasks:
        important_tasks.append(update.message.text)
        update.message.reply_text('Ok. Send /done when you are done with it')

    else:
        keyboard = [
            [InlineKeyboardButton(emoji.emojize(":arrow_forward:", use_aliases=True), callback_data='act_start'),  # Start
             InlineKeyboardButton(emoji.emojize(":heavy_multiplication_x:", use_aliases=True),
                                  callback_data='act_cancel')]  # Cancel
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text('You want to start: "{}"'.format(update.message.text), reply_markup=reply_markup)


def running_tasks(bot, update):
    tasks_list = get_running_tasks(tasks_info)
    update.message.reply_text('\n'.join(tasks_list))


def completed_tasks(bot, update):
    tasks_list = get_completed_tasks(tasks_info)
    update.message.reply_text('\n'.join(tasks_list))


def last_completed_task(bot, update):
    update.message.reply_text(last_completed_task_time(tasks_info))


def start(bot, update):
    global listenfortasks
    listenfortasks = True
    update.message.reply_text("Send me most important tasks for today ({} is good number)".format('3️⃣'))


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def unknown(bot, update):
    cmd = update.message.text

    ########
    # Task
    if cmd.startswith('/task'):
        ##################
        # No tasks at all
        if len(important_tasks) == 0:
            update.message.reply_text('Press /start please')

        else:
            num_task = int(cmd.split('_')[-1])

            #########################
            # This task is completed
            if important_tasks_status[num_task]:
                update.message.reply_text("This task is already completed")

            else:
                keyboard = [
                    [InlineKeyboardButton(emoji.emojize(":arrow_forward:", use_aliases=True),
                                          callback_data='act_start'),  # Start
                     InlineKeyboardButton(emoji.emojize(":heavy_multiplication_x:", use_aliases=True),
                                          callback_data='act_cancel')]  # Cancel
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                update.message.reply_text('You want to start: "{}"'.format(important_tasks[num_task]), reply_markup=reply_markup)

    else:
        update.message.reply_text("Sorry, I didn't understand that command.")


def main():
    if 'dump.pkl' in os.listdir('.'):
        global tasks_info
        tasks_info = pickle.load(open("dump.pkl", "rb"))

    updater = Updater(get_token())

    bot = telegram.Bot(token=get_token())
    bot.sendMessage(chat_id=admin_id, text='I am back')
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("running_tasks", running_tasks))
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("done", done))
    dp.add_handler(CommandHandler("day_status", day_status))
    dp.add_handler(CommandHandler("completed_tasks", completed_tasks))
    dp.add_handler(CommandHandler("last_time", last_completed_task))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, echo))
    dp.add_handler(MessageHandler(Filters.command, unknown))
    dp.add_handler(CallbackQueryHandler(button))

    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
