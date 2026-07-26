"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based tests (hypothesis) for the Nebius venue —
        idempotent apply, inverse destroy, label round-trip identity, and
        GPU-cluster grouping.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.nebius.nebiuscloudprovisioner import (
    NebiusCloudProvisioner
)
from ccai.provisioning.venues.nebius.nebiuslabeltranslator import (
    NebiusLabelTranslator
)

from ._mockclient import MockNebiusClient
from ._specfactory import basic_spec, gpu_cluster_spec


def _venue() -> CloudVenue:
    """
        Build a CloudVenue for property tests.

        :returns: A CloudVenue.
    """
    rtnval = CloudVenue(
        name="nebius-prop", provider="nebius",
        account="proj-test", region="eu-north1",
        credential="nebius-prop",
    )
    return rtnval


# ----------------------------------------------------------------------
# Idempotent apply
# ----------------------------------------------------------------------

@given(repeat=st.integers(min_value=2, max_value=5),
       with_vpn=st.booleans(), constraints={"max_examples": 25})
def test_apply_idempotent(repeat, with_vpn):
    """
        Applying a spec N times yields exactly the same inventory as
        applying it once — no extra VMs, VPCs, or disks.
    """
    client = MockNebiusClient()
    spec = basic_spec(with_vpn=with_vpn)
    aspects = ProvisioningAspects(runid="propidem")
    provisioner = NebiusCloudProvisioner(venue=_venue(), client=client,
                                         spec=spec)

    provisioner.apply(aspects=aspects)
    baseline = (len(client.state.vms), len(client.state.vpcs),
                len(client.state.subnets), len(client.state.disks),
                len(client.state.security_groups))

    for _ in range(repeat - 1):
        provisioner.apply(aspects=aspects)

    after = (len(client.state.vms), len(client.state.vpcs),
             len(client.state.subnets), len(client.state.disks),
             len(client.state.security_groups))
    assert after == baseline
    return


# ----------------------------------------------------------------------
# destroy is the inverse of apply
# ----------------------------------------------------------------------

@given(with_vpn=st.booleans(), constraints={"max_examples": 25})
def test_destroy_is_inverse_of_apply(with_vpn):
    """
        destroy ∘ apply returns the venue inventory to the pre-apply state.
    """
    client = MockNebiusClient()
    spec = basic_spec(with_vpn=with_vpn)
    aspects = ProvisioningAspects(runid="propinv")
    confirm = ProvisioningAspects(runid="propinv", confirm=True)
    provisioner = NebiusCloudProvisioner(venue=_venue(), client=client,
                                         spec=spec)

    provisioner.apply(aspects=aspects)
    provisioner.destroy(aspects=confirm)

    assert len(client.state.vms) == 0
    assert len(client.state.vpcs) == 0
    assert len(client.state.subnets) == 0
    assert len(client.state.security_groups) == 0
    assert len(client.state.disks) == 0
    inventory = provisioner.inventory(aspects=aspects)
    assert len(inventory) == 0
    return


# ----------------------------------------------------------------------
# Label round-trip identity
# ----------------------------------------------------------------------

_KEY = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
               min_size=1, max_size=16)
_VAL = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
               min_size=0, max_size=20)


@given(pairs=st.dictionaries(keys=_KEY, values=_VAL,
                             min_size=0, max_size=8), constraints={"max_examples": 80})
def test_label_round_trip_identity_for_conformant_inputs(pairs):
    """
        Round-tripping a conformant neutral tag set through to_nebius then
        from_nebius and back is the identity transformation.
    """
    translator = NebiusLabelTranslator()

    labels = translator.to_nebius(neutral_tags=pairs)
    recovered = translator.from_nebius(labels=labels)

    assert recovered == pairs

    # A second round-trip is stable.
    labels_again = translator.to_nebius(neutral_tags=recovered)
    assert labels_again == labels
    return


# ----------------------------------------------------------------------
# GPU-cluster grouping
# ----------------------------------------------------------------------

@given(repeat=st.integers(min_value=1, max_value=3), constraints={"max_examples": 20})
def test_gpu_cluster_grouping(repeat):
    """
        Every instance sharing an IB interconnect group lands in exactly one
        GPU Cluster, idempotently across repeated applies.
    """
    client = MockNebiusClient()
    spec = gpu_cluster_spec()
    aspects = ProvisioningAspects(runid="propgpu")
    provisioner = NebiusCloudProvisioner(venue=_venue(), client=client,
                                         spec=spec)

    for _ in range(repeat):
        provisioner.apply(aspects=aspects)

    assert len(client.state.placement_groups) == 1
    cluster_id = client.state.placement_groups[0].id
    placed = {vm.placement_group_id for vm in client.state.vms}
    assert placed == {cluster_id}
    return
