#!/usr/bin/env python3
#
# Copyright 2020 MongoDB Inc.
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
"""
Libdeps Graph Visualization Tool.

Starts a web service which creates a UI for interacting and examing the libdeps graph.
The web service front end consist of React+Redux for the framework, SocketIO for backend
communication, and Material UI for the GUI. The web service back end use flask and socketio.

This script will automatically install the npm modules, and build and run the production
web service if not debug.
"""

import os
import argparse
import shutil
import subprocess
import platform
import threading
import copy
import textwrap

import flask
from graph_visualizer_web_stack.flask.flask_backend import create_app


def get_args():
    """Create the argparse and return passed args."""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--debug', action='store_true', help=
        'Whether or not to run debug server. Note for non-debug, you must build the production frontend with "npm run build".'
    )
    parser.add_argument(
        '--graphml-dir', type=str, action='store', help=
        "Directory where libdeps graphml files live. The UI will allow selecting different graphs from this location",
        default="build/opt")
    parser.add_argument('--frontend_url', type=str, action='store',
                        help="URL to the frontend for CORS configuration.",
                        default="http://localhost:3000")

    return parser.parse_args()


def execute_and_read_stdout(cmd, cwd):
    """Execute passed command and get realtime output."""

    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, cwd=cwd, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)


def front_end_output(npm_start, cwd):
    """Start the frontend."""

    for output in execute_and_read_stdout(npm_start, cwd=cwd):
        print(output, end="")


def setup_node(node_check, npm_install, cwd):
    """Check node version and install npm packages."""

    status, output = subprocess.getstatusoutput(node_check)
    if status != 0 or not output.split('\n')[-1].startswith('v12'):
        print(
            f"Failed with status {status} to get node version 12 from 'node -v':\noutput: '{output}'"
        )
        exit(1)

    node_modules = os.path.join(
        os.path.dirname(__file__), 'graph_visualizer_web_stack', 'node_modules')
    if not os.path.exists(node_modules):

        print(f"{node_modules} not found, need to run 'npm install'")
        for output in execute_and_read_stdout(npm_install, cwd=cwd):
            print(output, end="")


def start_debug(app, socketio, npm_start, cwd):
    """Start the backend in debug mode."""

    thread = threading.Thread(target=front_end_output, args=(npm_start, cwd))
    thread.start()
    socketio.run(app, debug=True)
    thread.join()


def start_production(app, socketio, npm_build, cwd):
    """Start the backend in production mode."""

    for output in execute_and_read_stdout(npm_build, cwd=cwd):
        print(output, end="")

    env = os.environ.copy()
    env['PATH'] = 'node_modules/.bin:' + env['PATH']
    react_frontend = subprocess.Popen(['serve', '-s', 'build', '-l', '3000', '-n'], env=env,
                                      cwd=cwd)
    socketio.run(app, debug=False)
    stdout, stderr = react_frontend.communicate()
    print(f"{stdout}\nstderr:{stderr}")


def main():
    """Start up the server."""

    args = get_args()
    app, socketio = create_app(graphml_dir=args.graphml_dir, frontend_url=args.frontend_url)
    cwd = os.path.join(os.path.dirname(__file__), 'graph_visualizer_web_stack')

    if platform.system() == 'Linux':
        env_script = os.path.abspath(os.path.join(os.path.dirname(__file__), 'setup_nodejs_env.sh'))
        node_check = f". {env_script}; node -v"
        npm_install = [env_script, 'install']
        npm_start = [env_script, 'start']
        npm_build = [env_script, 'build']
    else:
        node_check = 'node -v'
        npm_install = ['npm', 'install']
        npm_start = ['npm', 'start']
        npm_build = ['npm', 'run', 'build']

    setup_node(node_check, npm_install, cwd)

    if args.debug:
        start_debug(app, socketio, npm_start, cwd)
    else:
        start_production(app, socketio, npm_build, cwd)


if __name__ == "__main__":
    main()
