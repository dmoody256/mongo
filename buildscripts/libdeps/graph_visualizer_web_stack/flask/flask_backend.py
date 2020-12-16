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
Flask backend web server.

The backend interacts with the graph_analyzer to perform queries on various libdeps graphs.
"""

import os
from pathlib import Path

from flask_socketio import SocketIO, emit
import flask
from flask_cors import CORS
from lxml import etree
import networkx

import graph_analyzer


class BackendServer:
    """Create small class for storing variables and state of the backend."""

    def __init__(self, graphml_dir, frontend_url):
        """Create and setup the state variables."""

        self.current_graph = networkx.DiGraph()
        self.loaded_graphs = {}
        self.current_selected_rows = {}
        self.static_dir = os.path.join(os.path.dirname(__file__), 'static')
        self.graphml_dir = graphml_dir
        self.frontend_url = frontend_url

    @staticmethod
    def get_graph_build_data(graph_file):
        """Fast method for extracting basic build data from the graph file."""

        version = ''
        git_hash = ''
        # pylint: disable=c-extension-no-member
        for _, element in etree.iterparse(graph_file,
                                          tag="{http://graphml.graphdrawing.org/xmlns}data"):
            if element.get('key') == 'graph_schema_version':
                version = element.text
            if element.get('key') == 'git_hash':
                git_hash = element.text
            element.clear()
            if version and git_hash:
                break
        return (version, git_hash)

    def get_graphml_files(self):
        """Find all graphml files in the target graphml dir."""

        for dirpath, _, filenames in os.walk(self.graphml_dir):
            for filename in filenames:
                if os.path.splitext(filename)[1] == '.graphml':
                    yield self.strip_build_dir(
                        Path(self.graphml_dir), Path(os.path.join(dirpath, filename)))

    @staticmethod
    def strip_build_dir(build_dir, node):
        """Small util function for making args match the graph paths."""

        if str(node.absolute()).startswith(str(build_dir.absolute())):
            return str(node.relative_to(build_dir))
        else:
            raise Exception(f"build path not in node path: node: {node} build_dir: {build_dir}")

    def return_graph_files(self):
        """Prepare the list of graph files for the frontend."""

        data = {'graph_files': []}
        for i, graph_file in enumerate(self.get_graphml_files(), start=1):
            version, git_hash = self.get_graph_build_data(
                os.path.join(self.graphml_dir, graph_file))
            data['graph_files'].append(
                {'id': i, 'value': graph_file, 'version': version, 'git': git_hash[:7]})
        return data

    def get_selected_nodes(self):
        """Return the state of the currently sellected nodes."""

        return {'selectedNodes': list(self.current_selected_rows.keys())}

    def cell_selected(self, message, app, socketio):
        """Construct the new graphData nodeInfo when a cell is selected."""

        print(f"Got row {message}!")

        if message['isSelected'] == 'flip':
            if message['data']['node'] in self.current_selected_rows:
                self.current_selected_rows.pop(message['data']['node'])
            else:
                self.current_selected_rows[message['data']['node']] = message['data']
        else:
            if message['isSelected'] and message:
                self.current_selected_rows[message['data']['node']] = message['data']
            else:
                self.current_selected_rows.pop(message['data']['node'])

        def send_graph_data():
            with app.test_request_context():

                nodes = set()
                links = set()
                nodeinfo_data = {'nodeInfos': []}

                for node, _ in self.current_selected_rows.items():
                    nodes.add(
                        tuple({
                            'id': str(node), 'name': os.path.basename(str(node)),
                            'type': self.current_graph.nodes()[node]['bin_type']
                        }.items()))
                    nodeinfo_data['nodeInfos'].append({
                        'id':
                            len(nodeinfo_data['nodeInfos']),
                        'node':
                            node,
                        'name':
                            os.path.basename(str(node)),
                        'attribs':
                            [{'name': key, 'value': value}
                             for key, value in self.current_graph.nodes(data=True)[node].items()],
                        'dependers': [{
                            'node':
                                depender, 'symbols':
                                    self.current_graph[node][depender].get('symbols', '').split(' ')
                        } for depender in self.current_graph[node]],
                        'dependencies': [{
                            'node':
                                dependency, 'symbols':
                                    self.current_graph[dependency][node].get('symbols',
                                                                             '').split(' ')
                        } for dependency in self.current_graph.rgraph[node]],
                    })
                    for depender in self.current_graph.rgraph[node]:
                        if self.current_graph[depender][node].get('direct'):
                            nodes.add(
                                tuple({
                                    'id': str(depender), 'name': os.path.basename(str(depender)),
                                    'type': self.current_graph.nodes()[depender]['bin_type']
                                }.items()))
                            links.add(tuple({'source': node, 'target': depender}.items()))
                socketio.emit("node_infos", nodeinfo_data)

                node_data = {
                    'graphData': {
                        'nodes': [dict(node) for node in nodes],
                        'links': [dict(link) for link in links],
                    }, 'selectedNodes': list(self.current_selected_rows.keys())
                }
                socketio.emit("graph_data", node_data)

        socketio.start_background_task(send_graph_data)

    def graph_file_selected(self, message, app, socketio):
        """Load the new graph and perform queries on it."""

        print(f"Got requests2 {message}!")

        emit("other_hash_selected", message, broadcast=True)
        self.current_selected_rows = {}

        def analyze_graph(graph):
            with app.test_request_context():

                current_hash = self.current_graph.graph.get('git_hash', 'N0_HASH_SELECTED')[:7]
                if current_hash != message['hash']:
                    self.current_selected_rows = {}
                    if message['hash'] in self.loaded_graphs:
                        self.current_graph = self.loaded_graphs[message['hash']]
                    else:
                        print(
                            f'loading new graph {current_hash} because different than {message["hash"]}'
                        )

                        graph = networkx.read_graphml(graph)

                        self.current_graph = graph_analyzer.LibdepsGraph(graph)
                        self.loaded_graphs[message['hash']] = self.current_graph

                analysis = graph_analyzer.counter_factory(
                    self.current_graph,
                    [name[0] for name in graph_analyzer.CountTypes.__members__.items()])
                ga = graph_analyzer.LibdepsGraphAnalysis(libdeps_graph=self.current_graph,
                                                         analysis=analysis)
                results = ga.get_results()

                graph_data = []
                for i, data in enumerate(results):
                    graph_data.append({'id': i, 'type': data, 'value': results[data]})
                socketio.emit("graph_results", graph_data, broadcast=True)

                node_data = {
                    'graphData': {'nodes': [], 'links': []},
                    "selectedNodes": list(self.current_selected_rows.keys())
                }
                socketio.emit("graph_data", {'graphData': {'nodes': [], 'links': []}})

                for node in self.current_graph.nodes():
                    node_data['graphData']['nodes'].append(
                        {'id': str(node), 'name': os.path.basename(str(node))})
                socketio.emit("graph_nodes", node_data)

        socketio.start_background_task(analyze_graph, os.path.join(self.graphml_dir,
                                                                   message['file']))


def create_app(graphml_dir, frontend_url):
    """Create the Flask app and configure socketio, then setup routes and messages."""

    server = BackendServer(graphml_dir, frontend_url)
    app = flask.Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins=frontend_url)
    app.config['SECRET_KEY'] = 'secret!'
    app.config['CORS_HEADERS'] = 'Content-Type'
    CORS(app, resources={r"/*": {"origins": frontend_url}})

    #pylint: disable=too-many-function-args
    #pylint: disable=unused-variable
    @app.route("/graph_files")
    def return_graph_files_route():
        return server.return_graph_files()

    @app.route("/get_selected_nodes")
    def get_selected_nodes_io():
        return server.get_selected_nodes()

    @socketio.on('row_selected')
    def cell_selected_io(message):
        return server.cell_selected(message, app, socketio)

    @socketio.on('git_hash_selected')
    def graph_file_selected_io(message):
        return server.graph_file_selected(message, app, socketio)

    #pylint: enable=too-many-function-args
    #pylint: enable=unused-variable

    return app, socketio
