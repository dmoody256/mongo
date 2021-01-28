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
Unittests for the graph analyzer.
"""
import unittest
import json
import sys
import networkx
from pathlib import Path

import graph_analyzer

from libdeps_graph_enums import CountTypes, DependsReportTypes, LinterTypes, EdgeProps, NodeProps

sys.path.append(str(Path(__file__).parent.parent))
import scons  # pylint: disable=wrong-import-position

sys.path.append(str(Path(scons.MONGODB_ROOT).joinpath('site_scons')))
from libdeps_next import deptype  # pylint: disable=wrong-import-position

class Tests(unittest.TestCase):

    def get_mock_graph(self):

        graph = networkx.OrderedDiGraph()

        graph.graph['build_dir'] = '.'
        graph.graph['graph_schema_version'] = 1

        # builds a graph of mostly public edges that looks like this:
        #
        #                        /-lib5.so
        #                 /lib3.so
        #                |       \-lib6.so
        # -lib1.so--lib2.so
        #                |       /-lib5.so (private)
        #                 \lib4.so
        #                        \-lib6.so

        self.add_node(graph, 'lib1.so', 'SharedLibrary', False)
        self.add_node(graph, 'lib2.so', 'SharedLibrary', False)
        self.add_node(graph, 'lib3.so', 'SharedLibrary', False)
        self.add_node(graph, 'lib4.so', 'SharedLibrary', False)
        self.add_node(graph, 'lib5.so', 'SharedLibrary', False)
        self.add_node(graph, 'lib6.so', 'SharedLibrary', False)

        self.add_edge(graph, 'lib1.so', 'lib2.so', True, int(deptype.Public))

        self.add_edge(graph, 'lib2.so', 'lib3.so', True, int(deptype.Public))
        self.add_edge(graph, 'lib2.so', 'lib4.so', True, int(deptype.Public))
        self.add_edge(graph, 'lib1.so', 'lib3.so', False, int(deptype.Public))
        self.add_edge(graph, 'lib1.so', 'lib4.so', False, int(deptype.Public))

        self.add_edge(graph, 'lib4.so', 'lib6.so', True, int(deptype.Public))
        self.add_edge(graph, 'lib4.so', 'lib5.so', True, int(deptype.Private))

        self.add_edge(graph, 'lib3.so', 'lib5.so', True, int(deptype.Public))
        self.add_edge(graph, 'lib3.so', 'lib6.so', True, int(deptype.Public))
        self.add_edge(graph, 'lib2.so', 'lib5.so', False, int(deptype.Public))
        self.add_edge(graph, 'lib2.so', 'lib6.so', False, int(deptype.Public))
        self.add_edge(graph, 'lib1.so', 'lib5.so', False, int(deptype.Public))
        self.add_edge(graph, 'lib1.so', 'lib6.so', False, int(deptype.Public))

        return graph


    def add_node(self, graph, node, builder, shim):
            graph.add_nodes_from([(
                node,
                {
                    NodeProps.bin_type.name: builder,
                    NodeProps.shim.name: shim
                }
            )])

    def add_edge(self, graph, dependent_node, dependency_node, direct, visibility):
        graph.add_edges_from([(
            dependency_node,
            dependent_node,
            {
                EdgeProps.direct.name: direct,
                EdgeProps.visibility.name: int(visibility)
            }
        )])

    def test_public_weights(self):

        libdeps = graph_analyzer.LibdepsGraph(self.get_mock_graph())
        analysis = graph_analyzer.linter_factory(libdeps, [LinterTypes.heaviest_pub_dep.name], False)
        ga = graph_analyzer.LibdepsGraphAnalysis(libdeps, analysis)
        printer = graph_analyzer.GaJsonPrinter(ga)

        expected_result={
            "heaviest_pub_dep":
                [
                    [5, ["lib3.so", "lib2.so"]],
                    [5, ["lib2.so", "lib1.so"]],
                    [3, ["lib5.so", "lib3.so"]],
                    [3, ["lib4.so", "lib2.so"]],
                    [2, ["lib6.so", "lib4.so"]],
                    [2, ["lib6.so", "lib3.so"]]
                ]
        }
        self.assertEqual(expected_result, json.loads(printer.get_json()))

    def test_graph_paths(self):

        libdeps = graph_analyzer.LibdepsGraph(self.get_mock_graph())
        analysis = [graph_analyzer.GraphPaths(libdeps, ['lib6.so', 'lib1.so'])]
        ga = graph_analyzer.LibdepsGraphAnalysis(libdeps, analysis)
        printer = graph_analyzer.GaJsonPrinter(ga)

        expected_result = {
            "graph_paths": {
                "('lib6.so', 'lib1.so')": [
                    "lib6.so -> lib3.so -> lib2.so -> lib1.so",
                    "lib6.so -> lib4.so -> lib2.so -> lib1.so"
                ]
            }
        }

        self.assertEqual(expected_result, json.loads(printer.get_json()))

        analysis = [graph_analyzer.GraphPaths(libdeps, ['lib5.so', 'lib4.so'])]
        ga = graph_analyzer.LibdepsGraphAnalysis(libdeps, analysis)
        printer = graph_analyzer.GaJsonPrinter(ga)

        expected_result = {
            "graph_paths": {
                "('lib5.so', 'lib4.so')": [
                ]
            }
        }

        self.assertEqual(expected_result, json.loads(printer.get_json()))

    def test_critical_paths(self):

        libdeps = graph_analyzer.LibdepsGraph(self.get_mock_graph())
        analysis = [graph_analyzer.CriticalEdges(libdeps, ['lib6.so', 'lib1.so'])]
        ga = graph_analyzer.LibdepsGraphAnalysis(libdeps, analysis)
        printer = graph_analyzer.GaJsonPrinter(ga)

        expected_result = {
            "critical_edges": {
                "('lib6.so', 'lib1.so')": [
                    ["lib2.so", "lib1.so"]
                ]
            }
        }

        self.assertEqual(expected_result, json.loads(printer.get_json()))


if __name__ == '__main__':
    unittest.main()