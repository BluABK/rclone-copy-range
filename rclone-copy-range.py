import os
import re
import time
from sys import argv
import subprocess
import threading


class DownloadSingleItem(threading.Thread):
    def __init__(self, thread_id, thread_cmd):
        super().__init__()
        self.id = thread_id
        self.cmd = thread_cmd

    def run(self):
        """
        Override threading.Thread.run() with own code
        :return:
        """
        try:
            # print("Thread {}:".format(self.id))
            # print("\t{}".format(self.cmd))
            print("Thread {}:\t{}".format(self.id, self.cmd))
            time.sleep(5)
        except Exception as e:
            raise e


def quote(s):
    return "\"" + s + "\""


if __name__ == "__main__":
    if (len(argv)) != 5:
        print("Error! Required parameters: <season_number> <season_directory_absolute_path> <start ep> <end ep>")
        exit(1)

    rclone_bin = "/usr/bin/rclone -v"
    rclone_site = "tohru:"

    thread_limit = 3

    season = argv[1]
    season_dir_abspath = str(argv[2])
    ep_start = int(argv[3])
    ep_end = int(argv[4])
    ep_range = range(ep_start, ep_end + 1)

    # Get list of season episodes/files from rclone:
    rclone_season_dir = rclone_site + quote(season_dir_abspath)
    cmd = rclone_bin + " " + "ls" + " " + rclone_season_dir
    # Get list from rclone shellexec, decode UTF-8, split on newlines and strip filesize info from each item:
    episode_list = [" ".join(s.split(' ')[1:]) for s in
                    subprocess.check_output(cmd, shell=True).decode('utf-8').splitlines()]

    # print(episode_list)

    # Create list of relevant episodes
    relevant_episodes = []
    for ep_number in ep_range:
        regex = '^.*S01E' + str(ep_number) + '.*$'
        p = re.compile(regex)
        res = filter(p.match, episode_list)
        relevant_episodes.append(list(res)[0])

    print(relevant_episodes)

    # Download relevant episodes
    thread_id_counter = 0
    thread_list = []
    threads_to_run = []

    # Create threads
    for ep in relevant_episodes:
        season_dir = os.path.split(season_dir_abspath)[-1]
        cmd = rclone_bin + " " + "copy" + " " + rclone_season_dir + " " + quote(season_dir)

        thread = DownloadSingleItem(thread_id_counter, cmd)
        thread_list.append(thread)
        threads_to_run.append(thread)
        thread_id_counter += 1

    # Start threads
    running_thread_counter = 0
    running_threads = []
    running = True
    while running:
        # Run threads if not above limit
        if running_thread_counter < thread_limit:
            for t in threads_to_run:
                if running_thread_counter < thread_limit:
                    print("Run thread {}".format(t.id))
                    t.start()
                    threads_to_run.pop(threads_to_run.index(t))
                    running_threads.append(t)
                    running_thread_counter += 1

        # join Threads
        for t in running_threads:
            print("Attempting to join thread {}".format(t.id))
            t.join()
            # Pop joined thread
            if not t.is_alive():
                print("Popping joined thread: {}.".format(t.id))
                running_threads.pop(running_threads.index(t))
                running_thread_counter -= 1

        if len(threads_to_run) == 0 and len(running_threads) == 0:
            running = False

    # # join remaining Threads
    # for t in running_threads:
    #     print("Attempting to join remaining thread {}".format(t.id))
    #     t.join()
    #     # Pop joined thread
    #     if not t.is_alive():
    #         running_threads.pop(running_threads.index(t))
