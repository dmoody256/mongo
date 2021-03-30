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
"""Unittests for the graph analyzer."""

import json
from pathlib import Path
import sys
import unittest

import networkx

import libdeps.analyzer
from libdeps.graph import LibdepsGraph, EdgeProps, NodeProps


def add_node(graph, node, builder, shim):
    """Add a node to the graph."""

    graph.add_nodes_from([(node, {NodeProps.bin_type.name: builder, NodeProps.shim.name: shim})])


def add_edge(graph, target, source, transitive_redundancy=1, **kwargs):
    """Add an edge to the graph."""

    edge_props = {
        EdgeProps.direct.name: kwargs[EdgeProps.direct.name],
        EdgeProps.visibility.name: int(kwargs[EdgeProps.visibility.name]),
    }

    if not kwargs[EdgeProps.direct.name]:
        edge_props[EdgeProps.transitive_redundancy.name] = transitive_redundancy
    graph.add_edges_from([(source, target, edge_props)])


def get_mock_graph():
    """Construct a mock graph which covers most cases and is easy to understand."""

    graph = LibdepsGraph()
    graph.graph['build_dir'] = '.'
    graph.graph['graph_schema_version'] = 2
    graph.graph['deptypes'] ='''{
        "Global": 0,
        "Public": 1,
        "Private": 2,
        "Interface": 3,
        "Typeinfo": 4
    }'''

    # builds a graph of mostly public edges that looks like this:
    #
    #                        /-lib5.so
    #                 /lib3.so
    #                |       \-lib6.so
    # -lib1.so--lib2.so
    #                |       /-lib5.so (private)
    #                 \lib4.so
    #                        \-lib6.so

    add_node(graph, 'lib1.so', 'SharedLibrary', False)
    add_node(graph, 'lib2.so', 'SharedLibrary', False)
    add_node(graph, 'lib3.so', 'SharedLibrary', False)
    add_node(graph, 'lib4.so', 'SharedLibrary', False)
    add_node(graph, 'lib5.so', 'SharedLibrary', False)
    add_node(graph, 'lib6.so', 'SharedLibrary', False)

    add_edge(graph, 'lib1.so', 'lib2.so', direct=True, visibility=graph.get_deptype('Public'))

    add_edge(graph, 'lib2.so', 'lib3.so', direct=True, visibility=graph.get_deptype('Public'))
    add_edge(graph, 'lib2.so', 'lib4.so', direct=True, visibility=graph.get_deptype('Public'))
    add_edge(graph, 'lib1.so', 'lib3.so', direct=False, visibility=graph.get_deptype('Public'))
    add_edge(graph, 'lib1.so', 'lib4.so', direct=False, visibility=graph.get_deptype('Public'))

    add_edge(graph, 'lib4.so', 'lib6.so', direct=True, visibility=graph.get_deptype('Public'))
    add_edge(graph, 'lib4.so', 'lib5.so', direct=True, visibility=graph.get_deptype('Private'))

    add_edge(graph, 'lib3.so', 'lib5.so', direct=True, visibility=graph.get_deptype('Public'))
    add_edge(graph, 'lib3.so', 'lib6.so', direct=True, visibility=graph.get_deptype('Public'))
    add_edge(graph, 'lib2.so', 'lib5.so', direct=False, visibility=graph.get_deptype('Public'))
    add_edge(graph, 'lib2.so', 'lib6.so', direct=False, visibility=graph.get_deptype('Public'),
             transitive_redundancy=2)
    add_edge(graph, 'lib1.so', 'lib5.so', direct=False, visibility=graph.get_deptype('Public'))
    add_edge(graph, 'lib1.so', 'lib6.so', direct=False, visibility=graph.get_deptype('Public'),
             transitive_redundancy=2)

    return graph


class Tests(unittest.TestCase):
    """Common unittest for the libdeps graph analyzer module."""

    def test_public_weights(self):
        """Test for the PublicWeights analyzer."""

        libdeps_graph = LibdepsGraph(get_mock_graph())
        analysis = [libdeps.analyzer.PublicWeights(libdeps_graph, [])]
        ga = libdeps.analyzer.LibdepsGraphAnalysis(libdeps_graph, analysis)
        printer = libdeps.analyzer.GaJsonPrinter(ga)

        expected_result = {
            "PUBLIC_WEIGHT": {
                "all_edges": [[3, ["lib3.so", "lib2.so"]], [3, ["lib2.so", "lib1.so"]],
                              [2, ["lib5.so", "lib3.so"]], [1, ["lib4.so", "lib2.so"]],
                              [0, ["lib6.so", "lib4.so"]], [0, ["lib6.so", "lib3.so"]]]
            }
        }
        self.assertEqual(expected_result, json.loads(printer.get_json()))

    def test_graph_paths(self):
        """Test for the GraphPaths analyzer."""

        libdeps_graph = LibdepsGraph(get_mock_graph())
        analysis = [libdeps.analyzer.GraphPaths(libdeps_graph, 'lib6.so', 'lib1.so')]
        ga = libdeps.analyzer.LibdepsGraphAnalysis(libdeps_graph, analysis)
        printer = libdeps.analyzer.GaJsonPrinter(ga)

        expected_result = {
            "GRAPH_PATHS": {
                "('lib6.so', 'lib1.so')": [
                    ['lib6.so', 'lib4.so', 'lib2.so', 'lib1.so'],
                    ['lib6.so', 'lib3.so', 'lib2.so', 'lib1.so']
                ]
            }
        }

        self.assertEqual(expected_result, json.loads(printer.get_json()))

        analysis = [libdeps.analyzer.GraphPaths(libdeps_graph, 'lib5.so', 'lib4.so')]
        ga = libdeps.analyzer.LibdepsGraphAnalysis(libdeps_graph, analysis)
        printer = libdeps.analyzer.GaJsonPrinter(ga)

        expected_result = {"GRAPH_PATHS": {"('lib5.so', 'lib4.so')": []}}

        self.assertEqual(expected_result, json.loads(printer.get_json()))

        analysis = [libdeps.analyzer.GraphPaths(libdeps_graph, 'lib5.so', 'lib2.so')]
        ga = libdeps.analyzer.LibdepsGraphAnalysis(libdeps_graph, analysis)
        printer = libdeps.analyzer.GaJsonPrinter(ga)

        expected_result = {
            "GRAPH_PATHS": {
                "('lib5.so', 'lib2.so')": [
                    ['lib5.so', 'lib3.so', 'lib2.so']
                ]
            }
        }

        self.assertEqual(expected_result, json.loads(printer.get_json()))

    def test_critical_paths(self):
        """Test for the CriticalPaths analyzer."""

        libdeps_graph = LibdepsGraph(get_mock_graph())
        analysis = [libdeps.analyzer.CriticalEdges(libdeps_graph, 'lib6.so', 'lib1.so')]
        ga = libdeps.analyzer.LibdepsGraphAnalysis(libdeps_graph, analysis)
        printer = libdeps.analyzer.GaJsonPrinter(ga)

        expected_result = {"CRITICAL_EDGES": {"('lib6.so', 'lib1.so')": [["lib2.so", "lib1.so"]]}}

        self.assertEqual(expected_result, json.loads(printer.get_json()))


if __name__ == '__main__':
    unittest.main()
