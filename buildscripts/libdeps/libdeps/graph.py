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
Libdeps Graph Enums.

These are used for attributing data across the build scripts and analyzer scripts.
"""

import networkx

try:
    import progressbar
except ImportError:
    pass


import json
from enum import Enum, auto


# We need to disable invalid name here because it break backwards compatibility with
# our graph schemas. Possibly we could use lower case conversion process to maintain
# backwards compatibility and make pylint happy.
# pylint: disable=invalid-name
class CountTypes(Enum):
    """Enums for the different types of counts to perform on a graph."""

    ALL = auto()
    NODE = auto()
    EDGE = auto()
    DIR_EDGE = auto()
    TRANS_EDGE = auto()
    DIR_PUB_EDGE = auto()
    PUB_EDGE = auto()
    PRIV_EDGE = auto()
    IF_EDGE = auto()
    SHIM = auto()
    PROG = auto()
    LIB = auto()


class DependsReportTypes(Enum):
    """Enums for the different type of depends reports to perform on a graph."""

    DIRECT_DEPENDS = auto()
    COMMON_DEPENDS = auto()
    EXCLUDE_DEPENDS = auto()
    GRAPH_PATHS = auto()
    CRITICAL_EDGES = auto()
    PUBLIC_WEIGHT = auto()


class LinterTypes(Enum):
    """Enums for the different types of counts to perform on a graph."""

    ALL = auto()
    PUBLIC_UNUSED = auto()


class EdgeProps(Enum):
    """Enums for edge properties."""

    direct = auto()
    visibility = auto()
    symbols = auto()
    transitive_redundancy = auto()


class NodeProps(Enum):
    """Enums for node properties."""

    shim = auto()
    bin_type = auto()

def null_progressbar(items):
    """Fake stand-in for normal progressbar."""
    for item in items:
        yield item


class LibdepsGraph(networkx.DiGraph):
    """Class for analyzing the graph."""

    def __init__(self, graph=networkx.DiGraph()):
        """Load the graph data."""
        super().__init__(incoming_graph_data=graph)

    def get_deptype(self, deptype):
        if not hasattr(self, '_deptypes'):
            self._deptypes = json.loads(self.graph.get('deptypes', "{}"))
            if self.graph['graph_schema_version'] == 1:
                # get and set the legacy values
                self._deptypes['Global'] = self._deptypes.get('Global', 0)
                self._deptypes['Public'] = self._deptypes.get('Public', 1)
                self._deptypes['Private'] = self._deptypes.get('Private', 2)
                self._deptypes['Interface'] = self._deptypes.get('Interface', 3)
                self._deptypes['Typeinfo'] = self._deptypes.get('Typeinfo', 4)

        return self._deptypes[deptype]


    def get_direct_nonprivate_graph(self):
        """Get a graph view of direct nonprivate edges."""

        def filter_direct_nonprivate_edges(n1, n2):
            return (self[n1][n2].get(EdgeProps.direct.name)
                    and (self[n1][n2].get(EdgeProps.visibility.name) == self.get_deptype('Public')
                         or self[n1][n2].get(EdgeProps.visibility.name) == self.get_deptype('Interface')))

        return networkx.subgraph_view(self, filter_edge=filter_direct_nonprivate_edges)

    def get_node_tree(self, node):
        """Get a tree with the passed node as the single root."""

        direct_nonprivate_graph = self.get_direct_nonprivate_graph()
        substree_set = networkx.descendants(direct_nonprivate_graph, node)

        def subtree(n1):
            return n1 in substree_set or n1 == node

        return networkx.subgraph_view(direct_nonprivate_graph, filter_node=subtree)

    def get_progress(self, value=None):
        """
        Set if a progress bar should be used or not.

        No args means use progress bar if available.
        """

        if value is None:
            value = 'progressbar' in globals()

        if hasattr(self, '_progressbar'):
            if self._progressbar:
                return self._progressbar

        if value:

            def get_progress_bar(title, *args):
                custom_bar = progressbar.ProgressBar(widgets=[
                    title,
                    progressbar.Counter(format='[%(value)d/%(max_value)d]'),
                    progressbar.Timer(format=" Time: %(elapsed)s "),
                    progressbar.Bar(marker='>', fill=' ', left='|', right='|')
                ])
                return custom_bar(*args)

            self._progressbar = get_progress_bar
        else:
            self._progressbar = null_progressbar

        return self._progressbar

    def calculate_transitive_redundancy(self):
        """
        Walk the graph and determine the transitive redundancy.

        The transitive redundancy is defined as a transitive edge which is
        created in multiple ways, each way being a unique
        path in the direct nonprivate graph view.
        """

        # Get some views setup up-front that we will use for each node in the graph.
        dependency_graph = networkx.reverse_view(self)
        direct_nonprivate_dependency_graph = dependency_graph.get_direct_nonprivate_graph()

        # The algorithm will make use of the fact that when determing the paths of a target node
        # tree, we must find the paths of all descendent nodes, so we can skip these descendent nodes
        # when they are revisited later.
        nodes_checked = set()

        # The algorithm works as follows:
        #
        # 1. Iterate through all nodes in the graph topologically starting with the target nodes
        #    which would have the biggest dependency trees first, so that we can calculate the
        #    the transitive redundancy of all the subtrees in that tree.
        #
        # 2. For each node in the graph, topologically sort the dependency tree of that node, and
        #    use the topological sort to calculate the number of paths for each node to the target
        #    at the top of the current tree. Note this will also correctly calculate the paths for
        #    all subtrees in the current tree.
        #
        # 3. For every node in the current target node tree, set the transitive redundancy for every
        #    transitive edge to every node in the current tree. The transitive redundancy would be
        #    equal to the number of paths through the tree in this case. All transitive edges in the
        #    current tree will have there transitive redundancy calculated, so all related nodes
        #    are added to a set to not be checked again.
        #
        # Here is step 1 from above, it is critical to iterate the topological dependency_graph as
        # opposed to the dependents_graph because in a subtree you may not calculate the maximum
        # number of paths for a given node, disallowing you to skip nodes.
        for target_node in self.get_progress()('Calculating Transitive Redundancy: ',
                                             list(networkx.topological_sort(dependency_graph))):

            if target_node in nodes_checked:
                continue

            # Here is step 2 from above, this is a common topological path counting algorithm using
            # dynamic programming technique. This is the fastest way to calculate paths with single
            # root node DAG.
            dependency_tree = direct_nonprivate_dependency_graph.get_node_tree(target_node)
            dependents_tree = networkx.reverse_view(dependency_tree)

            source_nodes = list(networkx.topological_sort(dependency_tree))
            paths = {node: 0 for node in source_nodes}
            paths[source_nodes[0]] = 1

            for source_node in source_nodes:
                for successor in dependents_tree[source_node]:
                    paths[source_node] += paths[successor]

            # Here is step 3 from above, we have all the paths calculated for all nodes
            # to the root target node, and also all nodes down the tree. This double for
            # loop will check every possible transitive edge in the current tree, and if it exists
            # set the transitive redundancy for that edge.
            for trans_source_node in source_nodes:
                for trans_target_node in source_nodes:
                    if (self[trans_source_node].get(trans_target_node) and
                            not self[trans_source_node][trans_target_node][EdgeProps.direct.name]):
                        self[trans_source_node][trans_target_node][
                            EdgeProps.transitive_redundancy.name] = paths[trans_source_node]
                nodes_checked.add(trans_source_node)
