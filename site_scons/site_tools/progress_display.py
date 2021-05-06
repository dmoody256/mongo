# Copyright 2021 MongoDB Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

"""SCons Tool for advanced progress output."""

import sys
import time
import hashlib
import pathlib
import os
import gzip
import subprocess
from timeit import default_timer as timer

import SCons

from SCons.Script.Main import Progress
from SCons.Script import COMMAND_LINE_TARGETS

from datetime import timedelta
import threading, queue

# some printing friendly conversions of the state
state_map = {
    SCons.Node.executing:  "executing",
    SCons.Node.up_to_date: "up-to-date"
}

# why doesn't timedelta work with strftime? I like time delta because it
# easily handles and converts elapsed time, but its not the best for
# formating. This function does some basic formating for decimal places
# but theres probably some issues here.
def time_string(seconds):
    tstring = str(timedelta(seconds=seconds))
    times = tstring.split('.')
    if len(times) == 2:
        tstring = times[0] + '{:.2f}'.format(round(float('0.'+times[1]), 2))[1:]
    else:
        tstring = times[0] + '.00'
    return tstring

class ProgressCounter:

    # wow that is a lot of globals, what a mess

    # targets waiting to be built
    targets_list = set()

    # original copy of targets list
    original_list = set()

    # targets that we have built used for verbose
    targets_built = []

    # scons output of commands used for verbose
    build_commands = {}

    # print the build commands
    verbose = False

    # the previous output used for printing time updates
    prev = ''

    # flag to make sure no more printing occurs
    build_complete=False

    # thread for printing progress
    thread = None

    # count of total build nodes
    total = 0

    # current count of how many nodes we have built
    current = 0

    # a format string for customizing the message
    progress_format_string = ""

    # start time of the build
    build_start_time = None

    # queue for passing messages around for printing in order
    q = queue.Queue()

    # the build was interrupted
    stopped = False

    # last message we printed used for length calculation
    last_msg = ''

    @staticmethod
    def print_output(output):
        """
        takes in a dictionary like:
        {
            "command": the build command for verbose
            "node": the node path
            "state": the state of the node
            "current": the current when this message was created
            "total": the total count when this message was created (Probably not needed)
        }

        and formats a string to print over the last message, using spaces to cover up anything.
        """

        # take the current time and passed message data and create the message to print
        elapsed = timer() - ProgressCounter.build_start_time
        format_string = '\r' + ProgressCounter.progress_format_string.format(
            time=time_string(elapsed),
            finished=output['current'],
            total=output['total'],
            state=state_map.get(output['state'], '')
        )
        msg = f"{format_string}{output['node']}"

        # use the last message printed and add spaces to make sure
        # it is completely covered.
        extra_space = len(ProgressCounter.last_msg) - len(msg)
        if extra_space < 0:
            extra_space = 0
        clear = ' ' * extra_space
        msg += clear

        # write the message
        sys.stdout.write(output['command'])
        sys.stdout.write(msg)
        sys.stdout.flush()

        ProgressCounter.last_msg = msg

    @staticmethod
    def output_thread():
        """
        Thread for printing the messages to make sure they are in order and also
        so that the command output when in verbose mode is printed correctly
        without flushing the terminal.
        """

        while ProgressCounter.current < ProgressCounter.total or not ProgressCounter.q.empty():

            # this sleep helps to keep this thread from monopolizing the queue
            # and leads to smooth time updates.
            time.sleep(0.001)

            # check if there is a message, if not just print the last message again with
            # a time update, and make sure not to reprint the command
            try:
                output = ProgressCounter.q.get(block=False)
            except queue.Empty:
                if not ProgressCounter.prev:
                    continue
                output = ProgressCounter.prev
                output['command'] = ''

            # if we got interrupted, make sure not to print anything else, as it could
            # get mixed in with scons or some other output on the terminal
            if ProgressCounter.stopped:
                break

            ProgressCounter.print_output(output)

    def __call__(self, node):
        """
        The main callback from scons letting us know when its processing a node.
        """

        # once the build start a few then we need to do the first time like start the
        # clock and start output thread
        if self.__class__.build_start_time is None:
            self.__class__.build_start_time = timer()
            self.__class__.thread = threading.Thread(target=self.__class__.output_thread, daemon=False)
            self.__class__.thread.start()

        # we plan to only put file nodes in our list, so we can do the same check here
        # and also check its a node we care about.
        if isinstance(node, SCons.Node.FS.File) and node.abspath in self.__class__.targets_list:

            # in order to maintain the cache file
            # we pull nodes off our target list so at the end we can know
            # to remove them if the build no longer uses that node
            self.__class__.targets_list.remove(node.abspath)
            self.__class__.current += 1

            # setup the message data we will pass to the output thread
            output_msg = {}
            output_msg['node'] = str(node)
            output_msg['state'] = node.get_state()
            output_msg['current'] = self.__class__.current
            output_msg['total'] = self.__class__.total
            output_msg['command'] = ''

            # if we are in verbose mode we need to search though old build commands
            # which were picked up by the buffered_output function. First we print
            # any commands that may have finished since the last time we came
            # through here, then we add the current target to the list so
            # the next time we come through it would be checked.
            if self.__class__.verbose:
                for target in self.__class__.targets_built:
                    if str(target) in self.__class__.build_commands:
                        output_msg['command'] += '\r'
                        output_msg['command'] += self.__class__.build_commands[str(target)]
                        output_msg['command'] += '\n'
                        self.__class__.targets_built.remove(target)

                self.__class__.targets_built.append(str(node))

            # On the final print we will wait for the output thread to finish up
            # so we can print in the main thread. This will hold up scons to ensure that scons
            # doesn't print inbetween our carriage returns
            if self.__class__.current == self.__class__.total:
                self.__class__.thread.join()
                self.__class__.print_output(output_msg)
                print("")
            elif self.__class__.current < self.__class__.total:
                # if we are not in verbose mode we can clear out some messages which may
                # have not been printed yet, this will in general speeds things up and make the
                # progress printing smoother. However we should print every message in verbose
                # mode since there will be useful data printed for logs or similar.
                if not self.__class__.verbose and self.__class__.current < self.__class__.total-1:
                    with self.__class__.q.mutex:
                        self.__class__.q.queue.clear()
                self.__class__.q.put(output_msg)
                self.__class__.prev = output_msg

def buffered_output(self, s, target, source, env):
    """
    Prevent scons from printing anything and instead we capture the data so
    we can print it at the appropriate time.
    """
    # if we are not in verbose mode we can drop all the output data
    # for a small speed improvement.
    if ProgressCounter.verbose:
        for t in target:
            ProgressCounter.build_commands[str(t)] = s
    return None

visited = set()
def get_all_dependencies(node, deps, count_q):
    """
    This is a walk of the dag, finding all derived children of the target nodes.
    It will print its messages in a separate thread so we can have continous timing
    updates.
    """

    global visited
    visited.add(node)
    for child in node.all_children():
        if child not in visited:

            if isinstance(child, SCons.Node.FS.File) and child.has_builder():
                deps.add(child.abspath)

                with count_q.mutex:
                    count_q.queue.clear()
                count_q.put(str(len(deps)))

            get_all_dependencies(child, deps, count_q)

def generate(env):

    # progress tool configuration variables, the main external user interface.
    #
    # PROGRESS_FORMAT_STR: a customizable format string for custom outputs
    # PROGRESS_VERBOSE: if build commands should be printed
    # PROGRESS_CACHE: the location to keep cachefiles
    # PROGRESS_CACHE_EXTRA: possible extra files to use identify a unique build
    # PROGESS_PRUNE: size in MB the progress is allowed to keep
    ProgressCounter.progress_format_string = env.get("PROGRESS_FORMAT_STR", "({time}) [{finished}/{total}]: {state} ")
    ProgressCounter.verbose = env.get("PROGRESS_VERBOSE", False)
    node_count_cache = env.get("PROGRESS_CACHE", ".progress")
    extra_files_for_hash = env.get("PROGRESS_CACHE_EXTRA", [])
    progress_prune_size = env.get("PROGESS_PRUNE", 10)

    if not os.path.exists(node_count_cache):
        env.Execute(SCons.Defaults.Mkdir(node_count_cache))

    # here we swap out scons usual printing methods so we can control the output
    SCons.Action._ActionAction.print_cmd_line = buffered_output
    SCons.Platform.TempFileMunge._print_cmd_str = buffered_output

    # we want to know when the build is interupted so we can cleanly exit
    # the thread and makes sure scons doesn't print error messages in between
    # our output, so we put a small hook in scons internal method
    old_stop = SCons.Taskmaster.Taskmaster.stop
    def taskmaster_stop(self):
        ProgressCounter.stopped = True
        old_stop(self)
    SCons.Taskmaster.Taskmaster.stop = taskmaster_stop

    # now we calculate the hashes for our cachefile to see if we need to create a new one
    extra_hashes = ''
    for extra_file in extra_files_for_hash:
        with open(extra_file, 'rb') as f:
            extra_hashes += hashlib.md5(f.read()).hexdigest()

    targets_string = env.Dir('.').abspath + " ".join([env['ESCAPE'](str(sys.executable))] + [env['ESCAPE'](arg) for arg in sys.argv]) + extra_hashes
    targets_hash = hashlib.md5(targets_string.encode()).hexdigest()


    if (pathlib.Path(node_count_cache) / targets_hash).exists():
        # there is an existing hashfile, extract the node list, and touch it to push off its prune date
        print(f"Extracting node list from cache {pathlib.Path(node_count_cache) / targets_hash}")

        with gzip.open(pathlib.Path(node_count_cache) / targets_hash, 'rt') as f:
            for line in f.readlines():
                ProgressCounter.targets_list.add(line.strip())
        (pathlib.Path(node_count_cache) / targets_hash).touch()

    else:
        # if there was not an existing cache file we need to walk the dag and get a new list
        # walking the dag does take some time so we will lose a couple of seconds depending on the
        # size of the build, but the scanning only needs to happen once, so when taskmaster really
        # does go walk the dag to build it will be faster because we finished all the scanning up front.
        print("Pre-running scanners on command line targets...")

        # we setup the node count output thread which will receive messages from the dependency walk
        # and print out the messages and keep updating the time.
        start = timer()
        count_q = queue.Queue()
        counting = True
        prev_count = ''

        def node_count_thread():
            nonlocal prev_count
            while counting or not count_q.empty():
                if ProgressCounter.stopped:
                    break
                time.sleep(0.001)
                try:
                    output = count_q.get(block=False)
                except queue.Empty:
                    if not prev_count:
                        continue
                    output = prev_count

                elapsed = timer() - start
                msg = f"\r({time_string(elapsed)}) Target Nodes: {output}"

                extra_space = len(prev_count) - len(msg)
                if extra_space < 0:
                    extra_space = 0
                clear = ' ' * extra_space
                msg += clear
                sys.stdout.write(msg)
                sys.stdout.flush()
                prev_count = output

        command_line_nodes = []
        for target in COMMAND_LINE_TARGETS:
            try:
                command_line_nodes += env.arg2nodes([target])
            except TypeError:
                command_line_nodes += [env.Dir(target)]

        # We need to make sure to tell our thread we are exiting if there is a keyboard interupt
        # scenario otherwise the output thread is likely to being doing io which cause python to
        # crash on exit: https://bugs.python.org/issue42717, there may be other abrupt exits
        # we need to handle here but SIGINT is most likely
        try:
            thread = threading.Thread(target=node_count_thread, daemon=False)
            thread.start()
            for target in env.arg2nodes(command_line_nodes):
                get_all_dependencies(target, ProgressCounter.targets_list, count_q)

        except KeyboardInterrupt:
            counting = False
            thread.join()
            sys.exit(1)

        # once we are done walking the dag to get the node list, lets write it down so
        # we don't have to do it again, and we can make minor updates to the cachefile if the build
        # changes a bit
        counting = False
        thread.join()
        print('')
        with gzip.open(pathlib.Path(node_count_cache) / targets_hash, 'wt') as f:
            for node in ProgressCounter.targets_list:
                f.write(node + os.linesep)

    ProgressCounter.total = len(ProgressCounter.targets_list)
    ProgressCounter.original_list = ProgressCounter.targets_list.copy()

    # setup and run the prune thread, this could affect build performance if the number
    # of files gets to large.
    def prune_thread():
        mtime = lambda f: os.stat(os.path.join(node_count_cache, f)).st_mtime
        cache_files = list(reversed(sorted(os.listdir(node_count_cache), key=mtime)))
        size = 0
        max_size = progress_prune_size * 1024.0 * 1024.0
        for cache_file in cache_files:
            cache_file = os.path.join(node_count_cache, cache_file)
            size += os.stat(cache_file).st_size
            if size > max_size and not cache_file.endswith(targets_hash):
                os.remove(cache_file)
    threading.Thread(target=prune_thread, daemon=True).start()

    # now we will set a hook into scons internal so we can see if the taskmaster finds any new nodes
    # we did not know about, for example if the build changes.
    nodes_to_add = set()
    old_candidate = SCons.Taskmaster.Taskmaster.find_next_candidate
    def taskmaster_find_next_candidate(self):
        node = old_candidate(self)
        if isinstance(node, SCons.Node.FS.File) and node.has_builder() and node.abspath not in ProgressCounter.original_list:
            nodes_to_add.add(node.abspath)
        return node
    SCons.Taskmaster.Taskmaster.find_next_candidate = taskmaster_find_next_candidate

    # In order to capture error output and make sure its not printed in between our progress
    # printing we can take hold of scons internal process launcher and make sure to stop
    # the progress printing on error.
    def progress_spawn(l, env):

        # on windows the popen command below runs into this: https://bugs.python.org/issue9699
        # using a shell=True can work around this
        if sys.platform.lower() == 'win32':
            proc = subprocess.Popen(l[2][1:-1], env = env, close_fds = True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            proc = subprocess.Popen(l, env = env, close_fds = True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        output, err = proc.communicate()
        if proc.returncode != 0:
            ProgressCounter.stopped = True
            err_out = err.decode().strip()
            if err_out:
                print(os.linesep + err_out)
        return proc.returncode

    if env['PLATFORM'] == 'win32':
        SCons.Platform.win32.exec_spawn = progress_spawn
    else:
        SCons.Platform.posix.exec_subprocess = progress_spawn

    # configure scons to use our progress class
    Progress(ProgressCounter())

    # when the build is finished, we can check to see if we have any new information about the build
    # and then update the cachefile.
    import atexit
    def update_cache():
        if ProgressCounter.build_complete and (nodes_to_add or ProgressCounter.targets_list):

            print(f"Updating progress cache for {pathlib.Path(node_count_cache) / targets_hash}")
            with gzip.open(pathlib.Path(node_count_cache) / targets_hash, 'wt') as f:
                for node in list(nodes_to_add | node not in ProgressCounter.original_list.difference(ProgressCounter.targets_list)):
                    f.write(node + os.linesep)

    atexit.register(update_cache)

def exists(env):
    return True
