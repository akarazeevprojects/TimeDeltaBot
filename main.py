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

import numpy as np
import matplotlib.pyplot as plt


class Statistics:
    def __init__(self):
        self.pauses = [0]
        self.total_times = [0]
        self.change_day = False

    def add(self, total, pause):
        if self.change_day:
            self.pauses.append(0)
            self.total_times.append(0)
            self.change_day = False

        self.pauses[-1] += pause
        self.total_times[-1] += total

    def next_day(self):
        self.change_day = True

    def plot(self, n_last_days=7, filename='foo.png'):
        if n_last_days > len(self.pauses):
            n_last_days = len(self.pauses)

        barWidth = 0.25

        total = np.array(self.total_times[-n_last_days:])
        pauses = np.array(self.pauses[-n_last_days:])

        bars1 = total - pauses
        bars2 = pauses

        r1 = np.arange(len(bars1))
        r2 = [x + barWidth for x in r1]

        plt.figure(figsize=(11, 5))

        d = 'day'
        if n_last_days > 1:
            d += 's'
        plt.title("Last {} {}".format(n_last_days, d))
        plt.bar(r1, bars1, color='#557f2d', width=barWidth, edgecolor='white', label='Productivity time')
        plt.bar(r2, bars2, color='#7f6d5f', width=barWidth, edgecolor='white', label='Interruption time')

        plt.xlabel("Effectiveness")
        plt.ylabel("Time in Minutes")
        effects = list(map(lambda x: '{:.1f}%'.format(x), 100 * ((total - pauses) / total)))
        plt.xticks([r + (barWidth / 2) for r in range(len(bars1))], effects)

        plt.legend()

        plt.savefig(filename, bbox_inches='tight')


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
    done_tasks = list(filter(lambda x: tasks[x].done, tasks))
    dends = list(map(lambda x: tasks[x].dend, done_tasks))
    if dends:
        return max(dends)
    else:
        return -1


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
        if self.paused is False:
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


class User:
    def __init__(self, user_id):
        self.tasks_info = dict()
        self.st = Statistics()
        self.important_tasks = list()
        self.listenfortasks = False
        self.user_id = user_id


users = dict()
admin_id = 107183599


def get_token():
    path = os.path.join('res', 'token.json')
    with open(path) as jsn:
        data = json.load(jsn)
    return data['token']


def button(bot, update):
    global users
    query = update.callback_query
    user_id = query.message.chat_id

    occurrences = [m.start() for m in re.finditer('"', query.message['text'])]
    task_text = query.message['text'][occurrences[0]+1:occurrences[-1]]

    #########
    # Start
    #
    if query.data == 'act_start':
        ts = int(time.time())
        users[user_id].tasks_info[task_text] = Task(ts)

        last_time = last_completed_task_time(users[user_id].tasks_info)
        if last_time != -1:
            time_delta = ts - last_time
            time_delta = '{:02d}:{:02d}'.format(time_delta // 60, time_delta % 60)

            bot.edit_message_text('Time since last completed task: {}'.format(time_delta),
                                  chat_id=query.message.chat_id, message_id=query.message.message_id)
        else:
            bot.edit_message_text('I hope you will manage with this task ' +
                                  emoji.emojize(":muscle:", use_aliases=True), chat_id=query.message.chat_id,
                                  message_id=query.message.message_id)

        keyboard = [
            [InlineKeyboardButton(emoji.emojize(":pause_button:", use_aliases=True) + ' - Pause',
                                  callback_data='act_pause'),  # Pause
             InlineKeyboardButton(emoji.emojize(":white_check_mark:", use_aliases=True) + ' - Done',
                                  callback_data='act_done')]  # Done
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.message.reply_text(emoji.emojize(":hourglass_flowing_sand:", use_aliases=True) +
                                 'You #started: "{}"'.format(task_text), reply_markup=reply_markup)
        pickle.dump(users, open("dump.pkl", "wb"))

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
        users[user_id].tasks_info[task_text].fpause(ts)

        keyboard = [
            [InlineKeyboardButton(emoji.emojize(":arrow_forward:", use_aliases=True) + ' - Continue',
                                  callback_data='act_continue'),  # Continue
             InlineKeyboardButton(emoji.emojize(":white_check_mark:", use_aliases=True) + ' - Done',
                                  callback_data='act_done')]  # Done
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        bot.edit_message_text(emoji.emojize(":rotating_light:", use_aliases=True) +
                              '#Paused: "{}"'.format(task_text), chat_id=query.message.chat_id,
                              message_id=query.message.message_id, reply_markup=reply_markup)
        pickle.dump(users, open("dump.pkl", "wb"))

    #########
    # Continue
    #
    elif query.data == 'act_continue':
        ts = int(time.time())
        time_delta = users[user_id].tasks_info[task_text].fcontinue(ts)
        time_delta = '{:02d}:{:02d}'.format(time_delta // 60, time_delta % 60)

        keyboard = [
            [InlineKeyboardButton(emoji.emojize(":pause_button:", use_aliases=True) + ' - Pause',
                                  callback_data='act_pause'),  # Pause
             InlineKeyboardButton(emoji.emojize(":white_check_mark:", use_aliases=True) + ' - Done',
                                  callback_data='act_done')]  # Done
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        bot.edit_message_text(emoji.emojize(":hourglass_flowing_sand:", use_aliases=True) +
                              '#Continued: "{}". It was paused for {}'.format(task_text, time_delta),
                              chat_id=query.message.chat_id, message_id=query.message.message_id,
                              reply_markup=reply_markup)
        pickle.dump(users, open("dump.pkl", "wb"))

    #########
    # Done
    #
    elif query.data == 'act_done':
        ts = int(time.time())
        time_delta = users[user_id].tasks_info[task_text].fdone(ts)
        time_pauses = users[user_id].tasks_info[task_text].ftotallenofpauses()
        effect = users[user_id].tasks_info[task_text].feffect()

        # Record statistics
        users[user_id].st.add(time_delta, time_pauses)

        time_delta = '{:02d}:{:02d}'.format(time_delta // 60, time_delta % 60)
        time_pauses = '{:02d}:{:02d}'.format(time_pauses // 60, time_pauses % 60)

        text_send = list()
        text_send.append(emoji.emojize(":white_check_mark:", use_aliases=True) + ' - "{}"'.format(task_text))
        text_send.append(emoji.emojize(":clock2:", use_aliases=True) + ' - {}'.format(time_delta))
        text_send.append(emoji.emojize(":thumbsup:", use_aliases=True) + ' - {:.1f}%'.format(effect))
        text_send.append(emoji.emojize(":pause_button:", use_aliases=True) + ' - {}'.format(time_pauses))
        text_send = '\n'.join(text_send)

        bot.edit_message_text(text=text_send, chat_id=query.message.chat_id, message_id=query.message.message_id)
        if len(get_running_tasks(users[user_id].tasks_info)) == 0:
            query.message.reply_text('What do you want to do next? ' + emoji.emojize(":blush:", use_aliases=True) +
                                     '\nCheck /day_status')

        pickle.dump(users, open("dump.pkl", "wb"))


def enough(bot, update):
    global users
    user_id = update.message.chat_id

    if users[user_id].listenfortasks:
        text = list()
        t = 'task'
        if len(users[user_id].important_tasks) > 1:
            t += 's'
        text.append('So you have {} {} for today:'.format(len(users[user_id].important_tasks), t))
        for i, task in enumerate(users[user_id].important_tasks):
            if task in get_completed_tasks(users[user_id].tasks_info):  # Task is completed
                text.append(emoji.emojize(":white_check_mark:", use_aliases=True) + ' - "{}"'.format(task))
            elif task in get_running_tasks(users[user_id].tasks_info):  # Task is running
                text.append(emoji.emojize(":hourglass_flowing_sand:", use_aliases=True) + ' - "{}"'.format(task))
            else:
                text.append(emoji.emojize(":radio_button:", use_aliases=True) + ' - "{}"'.format(task) +
                            "(let's do /task_{})".format(i))

        text = '\n'.join(text)
        update.message.reply_text(text)
        users[user_id].listenfortasks = False
    else:
        if len(users[user_id].important_tasks) > 0:
            update.message.reply_text('You already have tasks for today')
        else:
            update.message.reply_text('Press /add_important_tasks please')


def day_status(bot, update):
    global users
    user_id = update.message.chat_id

    text = list()

    ############################
    # No tasks at all
    if len(users[user_id].important_tasks) == 0 and len(get_running_tasks(users[user_id].tasks_info)) == 0 and len(
            get_completed_tasks(users[user_id].tasks_info)) == 0:
        update.message.reply_text('You need to /add_important_tasks for today')
    else:
        notcompleted_important_tasks = list(filter(lambda x: x not in get_completed_tasks(users[user_id].tasks_info),
                                                   users[user_id].important_tasks))
        ##########################
        # All tasks are completed
        if len(get_running_tasks(users[user_id].tasks_info)) == 0 and len(notcompleted_important_tasks) == 0:
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
            text.append('You have no more important tasks for today')

        ##################
        # There are tasks
        else:
            if len(notcompleted_important_tasks) > 0:
                t = 'task'
                if len(notcompleted_important_tasks) > 1:
                    t += 's'
                text.append('You have {} more important {} for today:'.format(len(notcompleted_important_tasks), t))
            elif len(users[user_id].important_tasks) == 0:
                text.append('You have no important tasks for today')
            else:
                text.append('You have no more important tasks for today')

        for i, task in enumerate(users[user_id].important_tasks):
            if task in get_completed_tasks(users[user_id].tasks_info):  # Task is completed
                text.append(emoji.emojize(":white_check_mark:", use_aliases=True) + ' - "{}"'.format(task))
            elif task in get_running_tasks(users[user_id].tasks_info):  # Task is running
                text.append(emoji.emojize(":hourglass_flowing_sand:", use_aliases=True) + ' - "{}"'.format(task))
            else:
                text.append(emoji.emojize(":radio_button:", use_aliases=True) + ' - "{}"'.format(task) +
                            "(let's do /task_{})".format(i))

        all_tasks_wstatus = get_running_tasks(users[user_id].tasks_info)
        all_tasks_wstatus.extend(get_completed_tasks(users[user_id].tasks_info))
        notimportant_tasks = list(filter(lambda x: x not in users[user_id].important_tasks, all_tasks_wstatus))

        if len(notimportant_tasks) > 0:
            text.append('---')

        for task in get_running_tasks(users[user_id].tasks_info):
            if task not in users[user_id].important_tasks:
                text.append(emoji.emojize(":hourglass_flowing_sand:", use_aliases=True) + ' - "{}"'.format(task))

        for task in get_completed_tasks(users[user_id].tasks_info):
            if task not in users[user_id].important_tasks:
                text.append(emoji.emojize(":white_check_mark:", use_aliases=True) + ' - "{}"'.format(task))

        if len(notcompleted_important_tasks) == 0 and len(get_running_tasks(users[user_id].tasks_info)) == 0:
            text.append('Go find something interesting ' + emoji.emojize(":blush:", use_aliases=True))
            text.append('Are you ready for /next_day?')

        text = '\n'.join(text)
        update.message.reply_text(text)


def echo(bot, update):
    global users
    user_id = update.message.chat_id

    if users[user_id].listenfortasks:
        users[user_id].important_tasks.append(update.message.text)
        update.message.reply_text('Ok. Is it /enough?')

    else:
        keyboard = [
            [InlineKeyboardButton(emoji.emojize(":arrow_forward:", use_aliases=True) + ' - Start',
                                  callback_data='act_start'),  # Start
             InlineKeyboardButton(emoji.emojize(":heavy_multiplication_x:", use_aliases=True) + ' - Cancel',
                                  callback_data='act_cancel')]  # Cancel
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text('You want to start: "{}"'.format(update.message.text), reply_markup=reply_markup)


def running_tasks(bot, update):
    global users
    user_id = update.message.chat_id

    tasks_list = get_running_tasks(users[user_id].tasks_info)
    if len(tasks_list) > 0:
        update.message.reply_text('\n'.join(tasks_list))
    else:
        update.message.reply_text('No running tasks')


def completed_tasks(bot, update):
    global users
    user_id = update.message.chat_id

    tasks_list = get_completed_tasks(users[user_id].tasks_info)
    if len(tasks_list) > 0:
        update.message.reply_text('\n'.join(tasks_list))
    else:
        update.message.reply_text('No completed tasks')


def last_completed_task(bot, update):
    global users
    user_id = update.message.chat_id

    update.message.reply_text(last_completed_task_time(users[user_id].tasks_info))


def add_important_tasks(bot, update):
    global users
    user_id = update.message.chat_id

    users[user_id].listenfortasks = True
    update.message.reply_text("Send me most important tasks for today\n({} is good number)".format('3️⃣'))


def start(bot, update):
    global users
    user_id = update.message.chat_id

    if user_id not in users:
        users[user_id] = User(user_id)

    text = list()
    text.append('Inspired by Polly and "The Productivity Project" book')
    text.append('---')
    text.append('This bot helps to track time spent on some task {}'.format(emoji.emojize(":blush:", use_aliases=True)))
    text.append('Also it provides you with statistics:'.format(emoji.emojize(":blush:", use_aliases=True)))
    update.message.reply_text('\n'.join(text))

    bot.send_photo(chat_id=user_id, photo=open('res/demo.png', 'rb'))

    update.message.reply_text("Are you ready to /add_important_tasks for today?")
    # add_important_tasks(bot, update)


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def next_day(bot, update):
    global users
    user_id = update.message.chat_id

    users[user_id].important_tasks = list()
    users[user_id].tasks_info = dict()
    users[user_id].st.next_day()
    update.message.reply_text("Do you want to /get_statistics?\nLet's /add_important_tasks for today")


def get_statistics(bot, update):
    global users
    user_id = update.message.chat_id

    filename = str(user_id) + '.png'
    users[user_id].st.plot(filename=filename)
    bot.send_photo(chat_id=user_id, photo=open(filename, 'rb'))

    if len(users[user_id].important_tasks) == 0:
        update.message.reply_text("Let's /add_important_tasks for today")


def unknown(bot, update):
    global users
    user_id = update.message.chat_id

    cmd = update.message.text

    ###############
    # Task command
    if cmd.startswith('/task'):
        ##################
        # No tasks at all
        if len(users[user_id].important_tasks) == 0:
            update.message.reply_text('Press /add_important_tasks please')

        else:
            num_task = int(cmd.split('_')[-1])

            #########################
            # This task is completed
            if users[user_id].important_tasks[num_task] in get_completed_tasks(users[user_id].tasks_info):
                update.message.reply_text("This task is already completed")

            else:
                keyboard = [
                    [InlineKeyboardButton(emoji.emojize(":arrow_forward:", use_aliases=True) + ' - Start',
                                          callback_data='act_start'),  # Start
                     InlineKeyboardButton(emoji.emojize(":heavy_multiplication_x:", use_aliases=True) + ' - Cancel',
                                          callback_data='act_cancel')]  # Cancel
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                update.message.reply_text('You want to start: "{}"'.format(users[user_id].important_tasks[num_task]),
                                          reply_markup=reply_markup)

    else:
        update.message.reply_text("Sorry, I didn't understand that command.")


def main():
    if 'dump.pkl' in os.listdir('.'):
        global users
        users = pickle.load(open("dump.pkl", "rb"))

    updater = Updater(get_token())

    bot = telegram.Bot(token=get_token())
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("running_tasks", running_tasks))
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("enough", enough))
    dp.add_handler(CommandHandler("next_day", next_day))
    dp.add_handler(CommandHandler("get_statistics", get_statistics))
    dp.add_handler(CommandHandler("add_important_tasks", add_important_tasks))
    dp.add_handler(CommandHandler("day_status", day_status))
    dp.add_handler(CommandHandler("completed_tasks", completed_tasks))
    dp.add_handler(CommandHandler("last_time", last_completed_task))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.command, unknown))
    dp.add_handler(MessageHandler(Filters.text, echo))
    dp.add_handler(CallbackQueryHandler(button))

    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
