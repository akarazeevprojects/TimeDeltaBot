import numpy as np
import matplotlib.pyplot as plt


class Statistics:
    def __init__(self):
        self.pauses = [0]
        self.total_times = [0]
        self.procr = [0]
        self.change_day = False

    def add(self, total, pause):
        if self.change_day:
            self.pauses.append(0)
            self.total_times.append(0)
            self.procr.append(0)
            self.change_day = False

        self.pauses[-1] += pause
        self.total_times[-1] += total

    def add_procr(self, procr):
        self.procr[-1] += procr

    def next_day(self):
        self.change_day = True

    def plot(self, n_last_days=7, filename='foo.png'):
        if n_last_days > len(self.pauses):
            n_last_days = len(self.pauses)

        barWidth = 0.25

        total = np.array(self.total_times[-n_last_days:])
        pauses = np.array(self.pauses[-n_last_days:])
        procr = np.array(self.procr)

        bars1 = total - pauses
        bars2 = pauses
        bars3 = procr

        r1 = np.arange(len(bars1))
        r2 = [x + barWidth for x in r1]
        r3 = [x + barWidth for x in r2]

        plt.figure(figsize=(11, 5))

        d = 'day'
        if n_last_days > 1:
            d += 's'
        plt.title("Last {} {}".format(n_last_days, d))
        plt.bar(r1, bars1, color='#25e387', width=barWidth, edgecolor='white', label='Productive time')
        plt.bar(r2, bars2, color='#adadad', width=barWidth, edgecolor='white', label='Rest time')
        plt.bar(r3, bars3, color='#f86262', width=barWidth, edgecolor='white', label='Procrastination')

        plt.xlabel("Effectiveness")
        plt.ylabel("Time in Minutes")
        effects = list(map(lambda x: '{:.1f}%'.format(x), 100 * ((total - pauses) / total)))
        plt.xticks([r + (barWidth / 2) for r in range(len(bars1))], effects)

        plt.legend()

        plt.savefig(filename, bbox_inches='tight')


class Procrastination:
    def __init__(self):
        self.dstart = 0
        self.total = 0
        self.done = True

    def start(self, dstart):
        self.dstart = dstart
        self.done = False

    def end(self, dend):
        self.total += dend - self.dstart
        self.dstart = 0
        self.done = True

    def reset(self):
        self.dstart = 0
        self.total = 0
        self.done = True


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
        self.tasks_by_message = dict()
        self.st = Statistics()
        self.procr = Procrastination()
        self.important_tasks = list()
        self.listenfortasks = False
        self.user_id = user_id