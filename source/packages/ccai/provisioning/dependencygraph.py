"""
    .. module:: dependencygraph
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Resource dependency graph + Kahn's stable topological sort.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Set, Tuple

from ccai.interfaces.schemasemanticerror import SchemaSemanticError


# Per-kind preferred stage ordering used as the primary sort key in Kahn's
# algorithm.  Lower runs first.
_KIND_STAGE_RANK: Dict[str, int] = {
    "network": 10,
    "subnet": 20,
    "sg": 30,
    "security_group": 30,
    "keypair": 40,
    "instance": 50,
    "volume": 60,
    "volume_attachment": 70,
    "shared_filesystem": 80,
    "bucket": 90,
    "lb": 100,
    "load_balancer": 100,
    "dns": 110,
    "dns_record": 110,
}


class DependencyGraph:
    """
        Directed acyclic graph of (kind, name) nodes.

        Edges run from consumer to producer (an instance edge points to its
        subnet).  Kahn's algorithm produces a stable topological sort with
        a deterministic tiebreaker (stage rank, then alphabetical name).
    """

    def __init__(self) -> None:
        """
            Initialise an empty graph.
        """
        self._nodes: Set[Tuple[str, str]] = set()
        self._edges_out: Dict[Tuple[str, str], Set[Tuple[str, str]]] = {}
        return

    def add_node(self, *, kind: str, name: str) -> None:
        """
            Add a node to the graph.

            :param kind: Resource kind.
            :param name: Resource name.
        """
        node = (kind, name)
        self._nodes.add(node)
        if node not in self._edges_out:
            self._edges_out[node] = set()
        return

    def add_edge(self, *, consumer: Tuple[str, str],
                 producer: Tuple[str, str]) -> None:
        """
            Add a consumer -> producer edge.

            Both endpoints are auto-added.

            :param consumer: The dependent (kind, name).
            :param producer: The depended-upon (kind, name).
        """
        self.add_node(kind=consumer[0], name=consumer[1])
        self.add_node(kind=producer[0], name=producer[1])
        self._edges_out[consumer].add(producer)
        return

    @property
    def nodes(self) -> Set[Tuple[str, str]]:
        """
            Return the node set.

            :returns: Set of (kind, name) tuples.
        """
        rtnval = self._nodes
        return rtnval

    @property
    def edges_out(self) -> Dict[Tuple[str, str], Set[Tuple[str, str]]]:
        """
            Return the outgoing-edge map.

            :returns: Dict node -> set of producers.
        """
        rtnval = self._edges_out
        return rtnval

    def topological_sort(self) -> List[Tuple[str, str]]:
        """
            Return a stable topological ordering of the graph's nodes.

            Producers come before consumers — i.e., networks before subnets
            before instances.  Ties are broken by (stage_rank, name).

            :returns: Ordered list of (kind, name) tuples.
            :raises: SchemaSemanticError
        """
        # Reverse adjacency for in-degree counting (producer -> consumers).
        in_degree: Dict[Tuple[str, str], int] = {n: 0 for n in self._nodes}
        consumers_of: Dict[Tuple[str, str], List[Tuple[str, str]]] = {
            n: [] for n in self._nodes
        }
        for consumer, producers in self._edges_out.items():
            for producer in producers:
                in_degree[consumer] = in_degree[consumer] + 1
                consumers_of[producer].append(consumer)

        def _key(node: Tuple[str, str]) -> Tuple[int, str, str]:
            rank = _KIND_STAGE_RANK.get(node[0], 1000)
            rtnval = (rank, node[1], node[0])
            return rtnval

        ready: List[Tuple[str, str]] = sorted(
            [n for n, deg in in_degree.items() if deg == 0],
            key=_key,
        )

        order: List[Tuple[str, str]] = []
        while len(ready) > 0:
            node = ready.pop(0)
            order.append(node)
            for cons in consumers_of[node]:
                in_degree[cons] = in_degree[cons] - 1
                if in_degree[cons] == 0:
                    # Maintain stable order: insert in sorted position.
                    ready.append(cons)
                    ready.sort(key=_key)

        if len(order) != len(self._nodes):
            remaining = [n for n in self._nodes if n not in set(order)]
            err_msg_lines = ["Cycle detected in resource dependency graph."]
            err_msg_lines.append("REMAINING:")
            for node in sorted(remaining):
                err_msg_lines.append("    {}/{}".format(node[0], node[1]))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        rtnval = order
        return rtnval


def build_dependency_graph(*, spec: Dict[str, Any]
                           ) -> DependencyGraph:
    """
        Build a DependencyGraph from a normalised spec dict.

        Expected spec shape (per venue or merged):

            {
                "networks":          [{"name": ...}, ...],
                "subnets":           [{"name", "network": ...}, ...],
                "security_groups":   [{"name", "network": ...}, ...],
                "keypairs":          [{"name": ...}, ...],
                "instances":         [{"name", "subnet", "security_groups",
                                       "keypair", "vpn_join"}, ...],
                "volumes":           [{"name", "attached_to": ...}, ...],
                "dns_records":       [{"name", "instance_ref": ...}, ...],
                "load_balancers":    [{"name", "target_instance_names":
                                       [...]}, ...],
                "shared_filesystems":[{"name": ...}, ...],
                "buckets":           [{"name": ...}, ...],
            }

        Unknown sections are ignored so callers may pass partial specs.

        :param spec: Normalised spec dict.

        :returns: A DependencyGraph.
    """
    graph = DependencyGraph()

    for entry in spec.get("networks", []):
        graph.add_node(kind="network", name=entry["name"])

    for entry in spec.get("subnets", []):
        graph.add_node(kind="subnet", name=entry["name"])
        parent = entry.get("network", None)
        if parent is not None:
            graph.add_edge(consumer=("subnet", entry["name"]),
                           producer=("network", parent))

    for entry in spec.get("security_groups", []):
        graph.add_node(kind="sg", name=entry["name"])
        parent = entry.get("network", None)
        if parent is not None:
            graph.add_edge(consumer=("sg", entry["name"]),
                           producer=("network", parent))

    for entry in spec.get("keypairs", []):
        graph.add_node(kind="keypair", name=entry["name"])

    for entry in spec.get("instances", []):
        graph.add_node(kind="instance", name=entry["name"])
        subnet_ref = entry.get("subnet", None)
        if subnet_ref is not None:
            graph.add_edge(consumer=("instance", entry["name"]),
                           producer=("subnet", subnet_ref))
        for sg_ref in entry.get("security_groups", []) or []:
            graph.add_edge(consumer=("instance", entry["name"]),
                           producer=("sg", sg_ref))
        keypair_ref = entry.get("keypair", None)
        if keypair_ref is not None:
            graph.add_edge(consumer=("instance", entry["name"]),
                           producer=("keypair", keypair_ref))

    for entry in spec.get("shared_filesystems", []):
        graph.add_node(kind="shared_filesystem", name=entry["name"])

    for entry in spec.get("volumes", []):
        graph.add_node(kind="volume", name=entry["name"])
        attached = entry.get("attached_to", None)
        if attached is not None:
            graph.add_edge(consumer=("volume", entry["name"]),
                           producer=("instance", attached))

    for entry in spec.get("buckets", []):
        graph.add_node(kind="bucket", name=entry["name"])

    for entry in spec.get("load_balancers", []):
        graph.add_node(kind="lb", name=entry["name"])
        for tgt in entry.get("target_instance_names", []) or []:
            graph.add_edge(consumer=("lb", entry["name"]),
                           producer=("instance", tgt))

    for entry in spec.get("dns_records", []):
        graph.add_node(kind="dns", name=entry["name"])
        ref = entry.get("instance_ref", None)
        if ref is not None:
            graph.add_edge(consumer=("dns", entry["name"]),
                           producer=("instance", ref))

    rtnval = graph
    return rtnval
