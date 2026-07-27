"""
    .. module:: test_properties
        :platform: Darwin, Linux, Unix, Windows
        :synopsis: Property-based (hypothesis) tests for the CoreWeave
                   workload provisioner — idempotent apply, destroy-as-
                   inverse, label round-trip, and Sunk bundle determinism.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import re

from typing import Dict, List


from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.venues.coreweave.cwlabeltranslator import (
    CwLabelTranslator
)
from ccai.provisioning.venues.coreweave.cwsunkrenderer import CwSunkRenderer
from ccai.provisioning.venues.coreweave.cwvpnsidecar import CwVpnSidecar

from ccai.tests.provisioning.venues.coreweave.testsupport import (
    MockKubernetesClient, make_gpu_job, make_provisioner, make_spec
)


# A name strategy that yields valid WorkloadJob names (lowercase DNS label).
_NAME_RE = re.compile(r"^[a-z]([a-z0-9-]{0,12}[a-z0-9])?$")
_job_name = st.from_regex(_NAME_RE, fullmatch=True)

# A strategy producing Kubernetes-conformant label segments.
_conformant = st.from_regex(re.compile(r"^[a-z]([a-z0-9-]{0,8}[a-z0-9])?$"),
                            fullmatch=True)


@given(job_names=st.lists(_job_name, min_size=1, max_size=4, unique=True), constraints={"max_examples": 40})
def test_apply_is_idempotent(job_names: List[str]):
    """
        For any set of jobs, ``apply`` composed with itself realises the same
        resource set — idempotence at the venue level.
    """
    jobs = [make_gpu_job(name=name) for name in job_names]
    provisioner = make_provisioner(spec=make_spec(jobs=jobs))

    first = provisioner.apply()
    second = provisioner.apply()

    first_set = sorted("{}/{}".format(r.kind, r.name) for r in first.created)
    second_set = sorted("{}/{}".format(r.kind, r.name)
                        for r in second.created)
    assert first_set == second_set
    return


@given(job_names=st.lists(_job_name, min_size=1, max_size=4, unique=True), constraints={"max_examples": 40})
def test_destroy_is_inverse_of_apply(job_names: List[str]):
    """
        ``destroy`` after ``apply`` leaves no run-labelled resources — the
        destroy is the inverse of the apply.
    """
    jobs = [make_gpu_job(name=name) for name in job_names]
    kube = MockKubernetesClient()
    provisioner = make_provisioner(spec=make_spec(jobs=jobs),
                                   kubernetes_client=kube)

    class _Confirm:
        confirm = True

    provisioner.apply()
    provisioner.destroy(aspects=_Confirm())

    inventory = provisioner.inventory()
    assert len(inventory) == 0
    return


@given(tags=st.dictionaries(_conformant, _conformant, min_size=0,
                            max_size=6), constraints={"max_examples": 100})
def test_label_round_trip_identity_for_conformant_inputs(tags: Dict[str, str]):
    """
        For Kubernetes-conformant inputs, ``from_k8s(to_k8s(...))`` is the
        identity.
    """
    translator = CwLabelTranslator()

    round_tripped = translator.from_k8s(
        labels=translator.to_k8s(neutral_tags=tags))

    assert round_tripped == tags
    return


@given(workload_names=st.lists(_job_name, min_size=0, max_size=4,
                               unique=True), constraints={"max_examples": 40})
def test_sunk_bundle_hash_is_deterministic(workload_names: List[str]):
    """
        The Sunk manifest bundle is a deterministic function of its inputs —
        re-rendering yields the same content hash.
    """
    renderer = CwSunkRenderer()

    first = renderer.bundle_hash(namespace="default", run_id="run-1",
                                 workload_names=list(workload_names))
    second = renderer.bundle_hash(namespace="default", run_id="run-1",
                                  workload_names=list(workload_names))
    assert first == second
    return


@given(want_router=st.booleans(), constraints={"max_examples": 30})
def test_vpn_sidecar_vs_subnet_router_branch(want_router: bool):
    """
        The VPN renderer produces a pod-sidecar container or a subnet-router
        DaemonSet depending on the requested connectivity shape.
    """
    renderer = CwVpnSidecar()

    class _FakeVpnJoin:
        advertise_tags = ["tag:ci"]

    if want_router is True:
        manifest = renderer.render_subnet_router_daemonset(
            vpn_join=_FakeVpnJoin(), authkey="tskey-1", namespace="default",
            run_id="run-1", routes=["10.0.0.0/8"])
        assert manifest["kind"] == "DaemonSet"
    else:
        pod_template = {"spec": {"containers": [{"name": "main"}]}}
        rendered = renderer.render(vpn_join=_FakeVpnJoin(),
                                   pod_template=pod_template,
                                   authkey="tskey-1", hostname="h1")
        names = [c["name"] for c in rendered["spec"]["containers"]]
        assert "tailscale" in names
    return
