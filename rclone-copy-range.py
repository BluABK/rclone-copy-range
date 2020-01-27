import os
import re
import shlex
import sys
from sys import argv
import subprocess
import threading
import json

config = json.load('config.json')
debug = True if config["debug"] == "True" else False


class DownloadSingleItem(threading.Thread):
    def __init__(self, thread_id, thread_cmd, thread_name):
        super().__init__()
        self.id = thread_id
        self.cmd = thread_cmd
        self.name = thread_name
        self.logfile = '{}/thread-{}-{}.log'.format(config["thread_logdir"], self.id, self.name)
        self.done = False

    def run(self):
        """
        Override threading.Thread.run() with own code
        :return:
        """
        try:
            with open(self.logfile, 'wb') as f:
                process = subprocess.Popen(shlex.split(self.cmd), stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
                sys.stdout.write("Thread {}:\n".format(self.id))
                for line in iter(process.stdout.readline, b''):
                    sys.stdout.write(line.decode(sys.stdout.encoding))
                    f.write(line)
                sys.stdout.write("\n")

        except Exception as e:
            raise e

        self.done = True
        os.remove(self.logfile)


def quote(s):
    return "\"" + s + "\""


def log(s):
    if debug:
        logfile = 'debug.log'
        with open(logfile, 'a') as f:
            f.write(s + '\n')


if __name__ == "__main__":
    if (len(argv)) != 5:
        print("Error! Required parameters: <season_number> <season_directory_absolute_path> <start ep> <end ep>")
        exit(1)

    if not os.path.isdir(config["thread_logdir"]):
        os.mkdir(config["thread_logdir"])

    rclone_bin = config["rclone_bin"]
    rclone_args = config["rclone_args"]
    rclone_site = config["rclone_site"]

    thread_limit = config["thread_limit"]

    season_number = str(argv[1])
    season_dir_abspath = str(argv[2])
    ep_start = int(argv[3])
    ep_end = int(argv[4])
    ep_range = range(ep_start, ep_end + 1)

    # Get list of season episodes/files from rclone:
    rclone_season_dir_abspath = rclone_site + quote(season_dir_abspath)
    cmd = rclone_bin + " " + "ls" + " " + rclone_season_dir_abspath

    log("rclone remote listing cmd: {}".format(cmd))
    # Get list from rclone shellexec, decode UTF-8, split on newlines and strip filesize info from each item:
    print("Getting episode list from rclone remote...")
    episode_list = [" ".join(s.split(' ')[1:]) for s in
                    subprocess.check_output(cmd, shell=True).decode('utf-8').splitlines()]

    log("Episodes found: {}".format(", ".join(episode_list)))

    # Create list of relevant episodes
    relevant_episodes = []
    for ep_number in ep_range:
        regex = '^.*S' + str(season_number) + 'E' + str(ep_number) + '.*$'
        p = re.compile(regex)
        res = filter(p.match, episode_list)
        relevant_episodes.append(list(res)[0])

    log("Relevant episodes: {}".format(", ".join(relevant_episodes)))

    # Download relevant episodes
    thread_id_counter = 0
    thread_list = []
    threads_to_run = []

    # Create threads
    for ep in relevant_episodes:
        season_dir = os.path.split(season_dir_abspath)[-1]
        cmd = rclone_bin + " " + rclone_args + " " + "copy" + " " + \
              os.path.join(rclone_season_dir_abspath, quote(ep)) + " " + quote(season_dir) + os.path.sep

        thread = DownloadSingleItem(thread_id_counter, cmd, ep.replace(' ', '.'))
        thread_list.append(thread)
        threads_to_run.append(thread)
        thread_id_counter += 1

    # Start threads
    running_threads = []
    running = True
    while running:
        # Run threads if not above limit
        if len(running_threads) < thread_limit:
            for t in threads_to_run:
                if len(running_threads) < thread_limit:
                    log("Run thread {}: {}".format(t.id, t.name))
                    t.start()
                    running_threads.append(t)
                    threads_to_run.pop(threads_to_run.index(t))

        # join Threads
        for t in running_threads:
            # Only attempt to join if thread considers itself done (or we'll hang on the same one for ages)
            if t.done:
                log("Attempting to join thread {}: {}".format(t.id, t.name))
                t.join()
                # Pop joined thread
                if not t.is_alive():
                    log("Popping joined thread: {}: {}.".format(t.id, t.name))
                    running_threads.pop(running_threads.index(t))

        if len(threads_to_run) == 0 and len(running_threads) == 0:
            running = False

