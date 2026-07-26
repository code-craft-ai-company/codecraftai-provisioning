"""
    .. module:: test_dependency_graph
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Unit + property tests for DependencyGraph topological sort.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from hypothesis import given, settings, strategies as st

from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.dependencygraph import (
    DependencyGraph, build_dependency_graph,
)


class DependencyGraphBasicTests(unittest.TestCase):

    def test_network_before_subnet_before_instance(self) -> None:
        spec = {
            "networks": [{"name": "vpc-a"}],
            "subnets": [{"name": "sub-a", "network": "vpc-a"}],
            "instances": [{"name": "web-01", "subnet": "sub-a"}],
        }
        graph = build_dependency_graph(spec=spec)
        order = graph.topological_sort()
        positions = {node: idx for idx, node in enumerate(order)}
        self.assertLess(positions[("network", "vpc-a")],
                        positions[("subnet", "sub-a")])
        self.assertLess(positions[("subnet", "sub-a")],
                        positions[("instance", "web-01")])
        return

    def test_cycle_raises_semantic_error(self) -> None:
        graph = DependencyGraph()
        graph.add_edge(consumer=("a", "1"), producer=("b", "2"))
        graph.add_edge(consumer=("b", "2"), producer=("a", "1"))
        with self.assertRaises(SchemaSemanticError):
            graph.topological_sort()
        return

    def test_dns_after_referenced_instance(self) -> None:
        spec = {
            "instances": [{"name": "web-01"}],
            "dns_records": [{"name": "rec-a", "instance_ref": "web-01"}],
        }
        graph = build_dependency_graph(spec=spec)
        order = graph.topological_sort()
        positions = {node: idx for idx, node in enumerate(order)}
        self.assertLess(positions[("instance", "web-01")],
                        positions[("dns", "rec-a")])
        return


_name_st = st.text(alphabet=st.characters(min_codepoint=97,
                                          max_codepoint=122),
                   min_size=2, max_size=6)


@st.composite
def _valid_spec(draw):
    nets = draw(st.lists(st.fixed_dictionaries({"name": _name_st}),
                         min_size=1, max_size=3,
                         unique_by=lambda e: e["name"]))
    net_names = [n["name"] for n in nets]

    subnets = draw(st.lists(st.fixed_dictionaries({
        "name": _name_st,
        "network": st.sampled_from(net_names),
    }), min_size=1, max_size=4, unique_by=lambda e: e["name"]))
    sub_names = [s["name"] for s in subnets]

    instances = draw(st.lists(st.fixed_dictionaries({
        "name": _name_st,
        "subnet": st.sampled_from(sub_names),
    }), min_size=1, max_size=5, unique_by=lambda e: e["name"]))
    inst_names = [i["name"] for i in instances]

    dns = draw(st.lists(st.fixed_dictionaries({
        "name": _name_st,
        "instance_ref": st.sampled_from(inst_names),
    }), max_size=4, unique_by=lambda e: e["name"]))

    rtnval = {
        "networks": nets,
        "subnets": subnets,
        "instances": instances,
        "dns_records": dns,
    }
    return rtnval


class DependencyGraphProperty(unittest.TestCase):

    @settings(max_examples=30, deadline=None)
    @given(spec=_valid_spec())
    def test_instance_after_its_subnet(self, spec) -> None:
        graph = build_dependency_graph(spec=spec)
        order = graph.topological_sort()
        positions = {node: idx for idx, node in enumerate(order)}
        for inst in spec["instances"]:
            inst_pos = positions[("instance", inst["name"])]
            sub_pos = positions[("subnet", inst["subnet"])]
            self.assertLess(sub_pos, inst_pos)
        return

    @settings(max_examples=30, deadline=None)
    @given(spec=_valid_spec())
    def test_dns_after_referenced_instance(self, spec) -> None:
        graph = build_dependency_graph(spec=spec)
        order = graph.topological_sort()
        positions = {node: idx for idx, node in enumerate(order)}
        for rec in spec["dns_records"]:
            self.assertLess(positions[("instance", rec["instance_ref"])],
                            positions[("dns", rec["name"])])
        return

    @settings(max_examples=30, deadline=None)
    @given(spec=_valid_spec())
    def test_topo_sort_stable(self, spec) -> None:
        graph_a = build_dependency_graph(spec=spec)
        graph_b = build_dependency_graph(spec=spec)
        self.assertEqual(graph_a.topological_sort(),
                         graph_b.topological_sort())
        return


class CyclePropertyTests(unittest.TestCase):

    def test_synthesised_cycle_raises_semantic_error_only(self) -> None:
        graph = DependencyGraph()
        # Build a 3-node cycle.
        graph.add_edge(consumer=("network", "n-a"),
                       producer=("network", "n-b"))
        graph.add_edge(consumer=("network", "n-b"),
                       producer=("network", "n-c"))
        graph.add_edge(consumer=("network", "n-c"),
                       producer=("network", "n-a"))
        with self.assertRaises(SchemaSemanticError):
            graph.topological_sort()
        return


if __name__ == "__main__":
    unittest.main()
