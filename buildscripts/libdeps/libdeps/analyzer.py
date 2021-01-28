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
Libdeps Graph Analysis Tool.

This will perform various metric's gathering and linting on the
graph generated from SCons generate-libdeps-graph target. The graph
represents the dependency information between all binaries from the build.
"""

import sys
import textwrap
import copy
import json
from pathlib import Path
import progressbar

from libdeps.graph import CountTypes, DependsReportTypes, LinterTypes, EdgeProps, NodeProps

sys.path.append(str(Path(__file__).parent.parent.parent))
import scons  # pylint: disable=wrong-import-position

sys.path.append(str(Path(scons.MONGODB_ROOT).joinpath('site_scons')))
from libdeps_next import deptype  # pylint: disable=wrong-import-position


# newer pylints contain the fix: https://github.com/PyCQA/pylint/pull/2926/commits/35e1c61026eab90af504806ef9da6241b096e659
#signature-mutators=buildscripts.libdeps.graph_analyzer.schema_check
# pylint: disable=no-value-for-parameter
def parametrized(dec):
    """Allow parameters passed to the decorator."""

    def layer(*args, **kwargs):
        def repl(func):
            return dec(func, *args, **kwargs)

        return repl

    return layer


@parametrized
def schema_check(func, schema_version):
    """Check the version for a function against the graph."""

    def check(*args, **kwargs):
        # pylint: disable=protected-access
        if schema_version <= args[0]._dependency_graph.graph.get('graph_schema_version'):
            return func(*args, **kwargs)
        else:
            sys.stderr.write(
                f"WARNING: analysis for '{func.__name__}' requires graph schema version '{schema_version}'\n"
                +
                f"but detected graph schema version '{args[0]._dependency_graph.graph.get('graph_schema_version')}'\n"
                + f"Not running analysis for  {func.__name__}\n\n")
            return "GRAPH_SCHEMA_VERSION_ERR"

    return check


class Analyzer:
    """Base class for different types of analyzers."""

    @staticmethod
    def progressbar(items):
        for item in items:
            yield item

    def __init__(self, graph, progress=True):
        """Store the graph and extract the build_dir from the graph."""

        self._dependents_graph = graph
        self._dependency_graph = graph.get_reverse_graph()
        self._build_dir = Path(graph.graph['build_dir'])
        self.set_progress(progress)


    def _strip_build_dir(self, node):
        """Small util function for making args match the graph paths."""

        return str(Path(node).relative_to(self._build_dir))


    def _strip_build_dirs(self, nodes):
        """Small util function for making a list of nodes match graph paths."""

        return [self._strip_build_dir(node) for node in nodes]

    def set_progress(self, value):
        if value:
            self._progressbar = progressbar.progressbar
        else:
            self._progressbar = Analyzer.progressbar


class Counter(Analyzer):
    """Base Counter Analyzer class for various counters."""

    def number_of_edge_types(self, edge_type, value):
        """Count the graphs edges based on type."""

        return len([
            edge for edge in self._dependents_graph.edges(data=True)
            if edge[2].get(edge_type) == value
        ])

    def node_type_count(self, node_type, value):
        """Count the graphs nodes based on type."""

        return len([
            node for node in self._dependents_graph.nodes(data=True)
            if node[1].get(node_type) == value
        ])

    def report(self, report):
        """Report the results for the current type."""

        report[self._count_type] = self.run()


class NodeCounter(Counter):
    """Counts and reports number of nodes in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.node.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs nodes."""

        return self._dependents_graph.number_of_nodes()


class EdgeCounter(Counter):
    """Counts and reports number of edges in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.edge.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs edges."""

        return self._dependents_graph.number_of_edges()


class DirectEdgeCounter(Counter):
    """Counts and reports number of direct edges in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.dir_edge.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs direct edges."""

        return self.number_of_edge_types(EdgeProps.direct.name, True)


class TransEdgeCounter(Counter):
    """Counts and reports number of transitive edges in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.trans_edge.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs transitive edges."""

        return self.number_of_edge_types(EdgeProps.direct.name, False)


class DirectPubEdgeCounter(Counter):
    """Counts and reports number of direct public edges in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.dir_pub_edge.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs direct public edges."""

        return len([
            edge for edge in self._dependents_graph.edges(data=True)
            if edge[2].get(EdgeProps.direct.name)
            and edge[2].get(EdgeProps.visibility.name) == int(deptype.Public)
        ])


class PublicEdgeCounter(Counter):
    """Counts and reports number of public edges in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.pub_edge.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs public edges."""

        return self.number_of_edge_types(EdgeProps.visibility.name, int(deptype.Public))


class PrivateEdgeCounter(Counter):
    """Counts and reports number of private edges in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.priv_edge.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs private edges."""

        return self.number_of_edge_types(EdgeProps.visibility.name, int(deptype.Private))


class InterfaceEdgeCounter(Counter):
    """Counts and reports number of interface edges in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.if_edge.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs interface edges."""

        return self.number_of_edge_types(EdgeProps.visibility.name, int(deptype.Interface))


class ShimCounter(Counter):
    """Counts and reports number of shim nodes in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.shim.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs shim nodes."""

        return self.node_type_count(NodeProps.shim.name, True)


class LibCounter(Counter):
    """Counts and reports number of library nodes in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.lib.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs lib nodes."""

        return self.node_type_count(NodeProps.bin_type.name, 'SharedLibrary')


class ProgCounter(Counter):
    """Counts and reports number of program nodes in the graph."""

    def __init__(self, graph):
        """Store graph and set type."""

        super().__init__(graph)
        self._count_type = CountTypes.prog.name

    @schema_check(schema_version=1)
    def run(self):
        """Count the graphs program nodes."""

        return self.node_type_count(NodeProps.bin_type.name, 'Program')


def counter_factory(graph, counters, progressbar=True):
    """Construct counters from a list of strings."""

    counter_map = {
        CountTypes.node.name: NodeCounter,
        CountTypes.edge.name: EdgeCounter,
        CountTypes.dir_edge.name: DirectEdgeCounter,
        CountTypes.trans_edge.name: TransEdgeCounter,
        CountTypes.dir_pub_edge.name: DirectPubEdgeCounter,
        CountTypes.pub_edge.name: PublicEdgeCounter,
        CountTypes.priv_edge.name: PrivateEdgeCounter,
        CountTypes.if_edge.name: InterfaceEdgeCounter,
        CountTypes.shim.name: ShimCounter,
        CountTypes.lib.name: LibCounter,
        CountTypes.prog.name: ProgCounter,
    }

    if not isinstance(counters, list):
        counters = [counters]

    counter_objs = []
    for counter in counters:
        if counter in counter_map:
            counter_obj = counter_map[counter](graph)
            counter_obj.set_progress(progressbar)
            counter_objs.append(counter_obj)

        else:
            print(f"Skipping unknown counter: {counter}")

    return counter_objs


class CommonDependencies(Analyzer):
    """Finds common dependencies for a set of given nodes."""

    def __init__(self, graph, nodes):
        """Store graph and strip the nodes."""

        super().__init__(graph)
        self._nodes = self._strip_build_dirs(nodes)

    @schema_check(schema_version=1)
    def run(self):
        """For a given set of nodes, report what nodes depend on all nodes from that set."""

        neighbor_sets = [set(self._dependents_graph[node]) for node in self._nodes]
        return list(set.intersection(*neighbor_sets))

    def report(self, report):
        """Add the common depends list for this tuple of nodes."""

        if DependsReportTypes.common_depends.name not in report:
            report[DependsReportTypes.common_depends.name] = {}
        report[DependsReportTypes.common_depends.name][tuple(self._nodes)] = self.run()


class DirectDependencies(Analyzer):
    """Finds direct dependencies for a given node."""

    def __init__(self, graph, node):
        """Store graph and strip the node."""

        super().__init__(graph)
        self._node = self._strip_build_dir(node)

    @schema_check(schema_version=1)
    def run(self):
        """For given nodes, report what nodes depend directly on that node."""

        return [
            depender for depender in self._dependents_graph[self._node]
            if self._dependents_graph[self._node][depender].get(EdgeProps.direct.name)
        ]

    def report(self, report):
        """Add the direct depends list for this node."""

        if DependsReportTypes.direct_depends.name not in report:
            report[DependsReportTypes.direct_depends.name] = {}
        report[DependsReportTypes.direct_depends.name][self._node] = self.run()


class ExcludeDependencies(Analyzer):
    """Finds finds dependencies which include one node, but exclude others."""

    def __init__(self, graph, nodes):
        """Store graph and strip the nodes."""

        super().__init__(graph)
        self._nodes = self._strip_build_dirs(nodes)

    @schema_check(schema_version=1)
    def run(self):
        """Find depends with exclusions.

        Given a node, and a set of other nodes, find what nodes depend on the given
        node, but do not depend on the set of nodes.
        """

        valid_depender_nodes = []
        for depender_node in set(self._dependents_graph[self._nodes[0]]):
            if all([
                    bool(excludes_node not in set(self._dependency_graph[depender_node]))
                    for excludes_node in self._nodes[1:]
            ]):
                valid_depender_nodes.append(depender_node)
        return valid_depender_nodes

    def report(self, report):
        """Add the exclude depends list for this tuple of nodes."""

        if DependsReportTypes.exclude_depends.name not in report:
            report[DependsReportTypes.exclude_depends.name] = {}
        report[DependsReportTypes.exclude_depends.name][tuple(self._nodes)] = self.run()


class GraphPaths(Analyzer):
    """Finds all paths between two nodes in the graph."""

    def __init__(self, graph, nodes):
        """Store graph and strip the nodes."""

        super().__init__(graph)
        self._start_node, self._end_node = self._strip_build_dirs(nodes)

    def _recursive_direct_public_libdeps(self, current_node, current_path):
        """Check each direct public libdep on the current node and recurse to find other paths."""

        paths = []

        # Get the direct public libdeps on the current node so we can check if the start node is
        # in them. If it is then we will copy the current path so we have a new reference we can
        # safe off and prevent modification as we go further down the tree. All direct public
        # nodes are added as a branch and traversal is continued to keep search for the
        # start node.
        for dir_pub_node in self._dependency_graph[current_node]:
            if (self._dependency_graph[current_node][dir_pub_node].get(EdgeProps.direct.name)
                    and self._dependency_graph[current_node][dir_pub_node].get(
                        EdgeProps.visibility.name) == int(deptype.Public)):

                local_path = copy.copy(current_path)
                local_path.append(dir_pub_node)
                if dir_pub_node == self._start_node:
                    paths.append(list(reversed(local_path)))

                if self._start_node in self._dependency_graph[dir_pub_node]:
                    paths += self._recursive_direct_public_libdeps(dir_pub_node, local_path)
        return paths

    @schema_check(schema_version=1)
    def run(self):
        """Find all paths between the two nodes in the graph."""

        paths = []

        # This for loop checks the dependency nodes directly on the end node
        # and adds that as a path. Probably could break, but don't want to silent cases
        # where the node is listed twice as a dependency
        for node in self._dependency_graph[self._end_node]:
            if (self._dependency_graph[self._end_node][node].get(EdgeProps.direct.name)
                    and self._dependency_graph[self._end_node][node].get(
                        EdgeProps.visibility.name) == int(deptype.Public)):

                if self._start_node == node:
                    paths.append([self._start_node, self._end_node])

        # Now we need to walk the direct public tree backwards, recording the nodes we
        # took as we go, so we can see if the start node is in that tree and
        # then construct the path taken between the two.
        current_path = [self._end_node]
        paths += self._recursive_direct_public_libdeps(self._end_node, current_path)

        return paths

    def report(self, report):
        """Add the path list to the report."""

        if DependsReportTypes.graph_paths.name not in report:
            report[DependsReportTypes.graph_paths.name] = {}
        report[DependsReportTypes.graph_paths.name][tuple(
            [self._start_node, self._end_node])] = [f"{' -> '.join(path)}" for path in self.run()]


class CriticalEdges(GraphPaths):
    """Finds all edges between two nodes, where remove that edge breaks the dependency."""

    @schema_check(schema_version=1)
    def run(self):
        """Go through the list of paths for the two nodes finding the edges that exist in every path."""

        critical_edge_counts = {}

        # We can get all paths through the graph with the other analyzer, and then we can check
        # to see if any given edge exists in every path by using a counter to record the number of
        # times it appears, and compare that to the number of paths, this assumes no cycles. If
        # that given edge exists in every path, then it is critical and
        # and removing that edge would disrupt all paths through the graph.
        paths = super().run()
        for nodes in paths:
            for from_node, to_node in zip(nodes[:-1], nodes[1:]):
                nodes_tuple = tuple([from_node, to_node])
                if nodes_tuple not in critical_edge_counts:
                    critical_edge_counts[nodes_tuple] = 1
                else:
                    critical_edge_counts[nodes_tuple] += 1

        critical_edges = []
        for nodes, count in critical_edge_counts.items():
            if count == len(paths):
                critical_edges.append(nodes)

        return critical_edges

    def report(self, report):
        """Add the critical edges to report."""

        if DependsReportTypes.critical_edges.name not in report:
            report[DependsReportTypes.critical_edges.name] = {}
        report[DependsReportTypes.critical_edges.name][tuple([self._start_node,
                                                              self._end_node])] = self.run()



class HeaviestPublicLinter(Analyzer):
    """Lints the graph for the heaviest edges, or edge with the most resulting transitive edges."""

    def _get_trans_nodes(self, edge, trans_pub_nodes):
        """Get all the nodes that the target edge will transitively induce."""

        for trans_node in self._dependency_graph[edge[0]]:
            if (self._dependency_graph[edge[0]][trans_node].get(EdgeProps.visibility.name) == int(
                    deptype.Public) or self._dependency_graph[edge[0]][trans_node].get(
                        EdgeProps.visibility.name) == int(deptype.Interface)):
                trans_pub_nodes.add(trans_node)

    def count_edges(self, edge, unique_trans_nodes):
        """Sum all the edges created down a tree growing off an edge."""

        edge_attribs = self._dependents_graph[edge[0]][edge[1]]

        if (edge_attribs.get(EdgeProps.direct.name)
                and edge_attribs.get(EdgeProps.visibility.name) == int(deptype.Public)):

            # add in the current count for edges we have brought forward.
            count = len(unique_trans_nodes)

            # if everything this node brings forward has become redundant so
            # skip going any further in this tree
            if len(unique_trans_nodes) > 0:

                # we need to remove any redundant edges found from other dependencies
                # at the current destination node. We need to make local copy so we don't
                # modify the same list on different paths down the tree.
                local_copy = copy.deepcopy(unique_trans_nodes)
                for node in self._dependency_graph[edge[1]]:

                    if node == edge[0]:
                        continue

                    other_edge_attribs = self._dependency_graph[edge[1]][node]
                    if (other_edge_attribs.get(EdgeProps.direct.name)
                        and other_edge_attribs.get(EdgeProps.visibility.name) == int(deptype.Public)):

                        redundant_trans_nodes = set()
                        self._get_trans_nodes((node, edge[0]), redundant_trans_nodes)
                        for trans in redundant_trans_nodes:
                            try:
                                local_copy.remove(trans)
                            except KeyError:
                                pass

                for node in self._dependents_graph[edge[1]]:
                    count += self.count_edges((edge[1], node), local_copy)
                return count

        return 0

    @schema_check(schema_version=1)
    def run(self):
        """Run the linter counting the weights of all direct public edges."""

        edges = []

        dir_pub_edges = []
        for edge in self._dependents_graph.edges:
            edge_attribs = self._dependents_graph[edge[0]][edge[1]]
            if (edge_attribs.get(EdgeProps.direct.name)
                    and edge_attribs.get(EdgeProps.visibility.name) == int(deptype.Public)):
                dir_pub_edges.append(edge)

        for edge in self._progressbar(dir_pub_edges):
            unique_trans_nodes = set([edge[0]])
            self._get_trans_nodes(edge, unique_trans_nodes)
            count = self.count_edges(edge, unique_trans_nodes)
            edges.append((count, edge))

        return list(reversed(sorted(edges)))

    def report(self, report):
        """Report the lint issues."""

        report[LinterTypes.heaviest_pub_dep.name] = self.run()


class UnusedPublicLinter(Analyzer):
    """Lints the graph for any public libdeps that are unused in all resulting transitive edges."""

    def _check_edge_no_symbols(self, edge, original_nodes, checked_edges):
        """Check the edge's transitive tree and made sure no edges have symbols."""

        if edge not in checked_edges:
            checked_edges.add(edge)
            original_node = edge[0]
            depender = edge[1]
            try:
                edge_attribs = self._dependents_graph[original_node][depender]

                if (edge_attribs.get(EdgeProps.visibility.name) == int(deptype.Public)
                        or edge_attribs.get(EdgeProps.visibility.name) == int(deptype.Interface)):
                    if not edge_attribs.get(EdgeProps.symbols.name):
                        if not self._tree_uses_no_symbols(depender, original_nodes, checked_edges):
                            return False
                    else:
                        return False
            except KeyError:
                pass

        return True

    def _tree_uses_no_symbols(self, node, original_nodes, checked_edges):
        """Recursive walk for a public node.

        Walk the dependency tree for a given Public node, and check if all edges
        in that tree do not have symbol dependencies.
        """

        for depender in self._dependents_graph[node]:
            for original_node in original_nodes:
                edge = (original_node, depender)
                if not self._check_edge_no_symbols(edge, original_nodes, checked_edges):
                    return False
        return True

    def _check_trans_nodes_no_symbols(self, edge, trans_pub_nodes):
        """Check the edge against the transitive nodes for symbols."""

        for trans_node in self._dependency_graph[edge[0]]:
            if (self._dependency_graph[edge[0]][trans_node].get(EdgeProps.visibility.name) == int(
                    deptype.Public) or self._dependency_graph[edge[0]][trans_node].get(
                        EdgeProps.visibility.name) == int(deptype.Interface)):
                trans_pub_nodes.add(trans_node)
                try:
                    if self._dependents_graph[trans_node][edge[1]].get(EdgeProps.symbols.name):
                        return True
                except KeyError:
                    pass
        return False

    @schema_check(schema_version=1)
    def run(self):
        """Run the unused public linter.

        Run the linter to check for and PUBLIC libdeps which are
        unnecessary and can be converted to PRIVATE.
        """

        unused_public_libdeps = []
        checked_edges = set()

        for edge in self._dependents_graph.edges:
            edge_attribs = self._dependents_graph[edge[0]][edge[1]]

            if (edge_attribs.get(EdgeProps.direct.name)
                    and edge_attribs.get(EdgeProps.visibility.name) == int(deptype.Public)
                    and not self._dependents_graph.nodes()[edge[0]].get(NodeProps.shim.name)
                    and self._dependents_graph.nodes()[edge[1]].get(
                        NodeProps.bin_type.name) == 'SharedLibrary'):

                # First we will get all the transitive libdeps the dependent node
                # induces, while we are getting those we also check if the depender
                # node has any symbol dependencies to that transitive libdep.
                trans_pub_nodes = set([edge[0]])
                found_symbols = self._check_trans_nodes_no_symbols(edge, trans_pub_nodes)

                # If the depender node has no symbol dependencies on the induced libdeps,
                # then we will walk up the tree for the depender node, checking if any of the
                # induced dependencies have symbols. If there are no simples between all transitive
                # edges from this direct public libdep, its safe to change it to public.
                if not found_symbols and self._tree_uses_no_symbols(edge[1], list(trans_pub_nodes),
                                                                    checked_edges):
                    unused_public_libdeps.append((edge[0], edge[1]))

        return unused_public_libdeps

    def report(self, report):
        """Report the lint issies."""

        report[LinterTypes.public_unused.name] = self.run()


def linter_factory(graph, linters, progressbar=True):
    """Construct linters from a list of strings."""

    linter_map = {
        LinterTypes.public_unused.name: UnusedPublicLinter,
        LinterTypes.heaviest_pub_dep.name: HeaviestPublicLinter,
    }

    if not isinstance(linters, list):
        linters = [linters]

    linters_objs = []
    for linter in linters:
        if linter in linter_map:
            linters_objs.append(linter_map[linter](graph, progressbar))
        else:
            print(f"Skipping unknown counter: {linter}")

    return linters_objs


class BuildDataReport(Analyzer):
    """Adds the build and graph meta data to the report."""

    @schema_check(schema_version=1)
    def report(self, report):
        """Add the build data from the graph to the report."""

        report['invocation'] = self._dependents_graph.graph.get('invocation')
        report['git_hash'] = self._dependents_graph.graph.get('git_hash')
        report['graph_schema_version'] = self._dependents_graph.graph.get('graph_schema_version')


class LibdepsGraphAnalysis:
    """Runs the given analysis on the input graph."""

    def __init__(self, libdeps_graph, analysis):
        """Perform analysis based off input args."""

        self._libdeps_graph = libdeps_graph

        self._results = {}
        for analyzer in analysis:
            analyzer.report(self._results)

    def get_results(self):
        """Return the results fo the analysis."""

        return self._results

    def run_linters(self, linters):
        """Run the various dependency reports."""

        if LinterTypes.public_unused.name in linters:
            self.results[LinterTypes.public_unused.name] = \
                self.libdeps_graph.unused_public_linter()


class GaPrinter:
    """Base class for printers of the graph analysis."""

    def __init__(self, libdeps_graph_analysis):
        """Store the graph analysis for use when printing."""

        self._libdeps_graph_analysis = libdeps_graph_analysis


class GaJsonPrinter(GaPrinter):
    """Printer for json output."""

    def serialize(self, dictionary):
        """Serialize the k,v pairs in the dictionary."""

        new = {}
        for key, value in dictionary.items():
            if isinstance(value, dict):
                value = self.serialize(value)
            new[str(key)] = value
        return new

    def print(self):
        """Print the result data."""

        print(self.get_json())

    def get_json(self):

        results = self._libdeps_graph_analysis.get_results()
        return json.dumps(self.serialize(results))


class GaPrettyPrinter(GaPrinter):
    """Printer for pretty console output."""

    _count_descs = {
        CountTypes.node.name: "Nodes in Graph: {}",
        CountTypes.edge.name: "Edges in Graph: {}",
        CountTypes.dir_edge.name: "Direct Edges in Graph: {}",
        CountTypes.trans_edge.name: "Transitive Edges in Graph: {}",
        CountTypes.dir_pub_edge.name: "Direct Public Edges in Graph: {}",
        CountTypes.pub_edge.name: "Public Edges in Graph: {}",
        CountTypes.priv_edge.name: "Private Edges in Graph: {}",
        CountTypes.if_edge.name: "Interface Edges in Graph: {}",
        CountTypes.shim.name: "Shim Nodes in Graph: {}",
        CountTypes.lib.name: "Library Nodes in Graph: {}",
        CountTypes.prog.name: "Program Nodes in Graph: {}",
    }

    @staticmethod
    def _print_results_node_list(heading, nodes):
        """Util function for printing a list of nodes for depend reports."""

        print(heading)
        for i, depender in enumerate(nodes, start=1):
            print(f"    {i}: {depender}")
        print("")

    def _print_depends_reports(self, results):
        """Print the depends reports result data."""

        if DependsReportTypes.direct_depends.name in results:
            print("\nNodes that directly depend on:")
            for node in results[DependsReportTypes.direct_depends.name]:
                self._print_results_node_list(f'=>depends on {node}:',
                                              results[DependsReportTypes.direct_depends.name][node])

        if DependsReportTypes.common_depends.name in results:
            print("\nNodes that commonly depend on:")
            for nodes in results[DependsReportTypes.common_depends.name]:
                self._print_results_node_list(
                    f'=>depends on {nodes}:',
                    results[DependsReportTypes.common_depends.name][nodes])

        if DependsReportTypes.exclude_depends.name in results:
            print("\nNodes that depend on a node, but exclude others:")
            for nodes in results[DependsReportTypes.exclude_depends.name]:
                self._print_results_node_list(
                    f"=>depends: {nodes[0]}, exclude: {nodes[1:]}:",
                    results[DependsReportTypes.exclude_depends.name][nodes])

        if DependsReportTypes.graph_paths.name in results:
            print("\nDependency graph paths:")
            for nodes in results[DependsReportTypes.graph_paths.name]:
                self._print_results_node_list(f"=>start node: {nodes[0]}, end node: {nodes[1]}:",
                                              results[DependsReportTypes.graph_paths.name][nodes])

        if DependsReportTypes.critical_edges.name in results:
            print("\nCritical Edges:")
            for nodes in results[DependsReportTypes.critical_edges.name]:
                self._print_results_node_list(
                    f"=>critical edges between {nodes[0]} and {nodes[1]}:",
                    results[DependsReportTypes.critical_edges.name][nodes])

    def print(self):
        """Print the result data."""
        results = self._libdeps_graph_analysis.get_results()

        if 'invocation' in results:
            print(
                textwrap.dedent(f"""\
                    Graph built from git hash:
                    {results['git_hash']}

                    Graph Schema version:
                    {results['graph_schema_version']}

                    Build invocation:
                    {results['invocation']}
                    """))

        for count_type in CountTypes.__members__.items():
            if count_type[0] in self._count_descs and count_type[0] in results:
                print(self._count_descs[count_type[0]].format(results[count_type[0]]))

        self._print_depends_reports(results)

        if LinterTypes.public_unused.name in results:
            print(
                f"\nLibdepsLinter: PUBLIC libdeps that could be PRIVATE: {len(results[LinterTypes.public_unused.name])}"
            )
            for issue in sorted(results[LinterTypes.public_unused.name],
                                key=lambda item: item[1] + item[0]):
                print(f"    {issue[1]}: PUBLIC -> {issue[0]} -> PRIVATE")

        if LinterTypes.heaviest_pub_dep.name in results:
            top_n = 30
            print(f"\nLibdepsLinter: Edges created from direct public links (top {top_n}):")
            for weight in results[LinterTypes.heaviest_pub_dep.name][:top_n]:
                print(f"    {weight[0]}: [{weight[1][1]}] has direct public link [{weight[1][0]}]")
            if len(results) > top_n:
                print(f"    |: ...")
                print(f"    V: {len(results[LinterTypes.heaviest_pub_dep.name])-top_n} others")

