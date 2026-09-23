"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based (hypothesis) tests for the Lambda Labs venue
               provisioner — apply idempotence, destroy inversibility,
               sidecar tag round-trip, and SKU resolution.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import tempfile


from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.credentials.lambdalabsapikeycredential import (
    LambdalabsApiKeyCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.lambdalabs.lambdalabscloudprovisioner import (
    LambdalabsCloudProvisioner
)
from ccai.provisioning.venues.lambdalabs.llsidecartag import LlSidecarTag

from ccai.tests.provisioning.venues.lambdalabs._mockclient import (
    MockLambdalabsClient
)
from ccai.tests.provisioning.venues.lambdalabs._specfactory import (
    basic_spec, cluster_spec, make_instance
)
from ccai.provisioning.venues.lambdalabs.lambdalabsspec import (
    LambdalabsSpec
)


def _venue() -> CloudVenue:
    """
        Build a CloudVenue for the property tests.

        :returns: A CloudVenue instance.
    """
    rtnval = CloudVenue(name="lambdalabs-prop", provider="lambdalabs",
                        region="us-east-1", credential="ll")
    return rtnval


def _credential() -> LambdalabsApiKeyCredential:
    """
        Build a Lambda Labs credential for the property tests.

        :returns: A LambdalabsApiKeyCredential instance.
    """
    rtnval = LambdalabsApiKeyCredential(identifier="ll-prop",
                                        categories=["hpc-venue"],
                                        token="secret_prop")
    return rtnval


def _aspects() -> ProvisioningAspects:
    """
        Build a ProvisioningAspects bundle for the property tests.

        :returns: A ProvisioningAspects instance.
    """
    rtnval = ProvisioningAspects(runid="proprun01", verify_timeout=10.0,
                                 verify_interval=0.01)
    return rtnval


@given(reapply_count=st.integers(min_value=1, max_value=4), constraints={"max_examples": 30})
def test_apply_idempotent(reapply_count):
    """
        Repeated applies over the same client launch exactly one instance
        regardless of how many times apply runs.
    """
    client = MockLambdalabsClient()
    provisioner = LambdalabsCloudProvisioner(
        venue=_venue(), credential=_credential(), client=client,
        spec=basic_spec(), output_root=tempfile.mkdtemp(),
    )
    for _ in range(reapply_count):
        provisioner.apply(aspects=_aspects())

    assert client.launch_calls == 1
    assert len(client.list_instances(aspects=_aspects())) == 1
    return


@given(instance_count=st.integers(min_value=1, max_value=4), constraints={"max_examples": 30})
def test_destroy_is_inverse_of_apply(instance_count):
    """
        apply followed by destroy leaves no run-owned instances.
    """
    client = MockLambdalabsClient()
    instances = []
    for index in range(instance_count):
        instances.append(make_instance(name="node{}".format(index)))
    spec = LambdalabsSpec(keypairs=[basic_spec().keypairs[0]],
                          instances=instances)

    provisioner = LambdalabsCloudProvisioner(
        venue=_venue(), credential=_credential(), client=client, spec=spec,
        output_root=tempfile.mkdtemp(),
    )
    confirm = ProvisioningAspects(runid="proprun01", confirm=True,
                                  verify_timeout=10.0, verify_interval=0.01)

    provisioner.apply(aspects=_aspects())
    assert len(client.list_instances(aspects=_aspects())) == instance_count

    provisioner.destroy(aspects=confirm)
    assert len(client.list_instances(aspects=_aspects())) == 0
    return


@given(tags=st.dictionaries(
    keys=st.text(alphabet=st.characters(min_codepoint=97,
                                        max_codepoint=122),
                 min_size=1, max_size=8),
    values=st.text(alphabet=st.characters(min_codepoint=97,
                                          max_codepoint=122),
                   min_size=1, max_size=8),
    min_size=0, max_size=5), constraints={"max_examples": 60})
def test_sidecar_tag_round_trip_identity(tags):
    """
        Writing a neutral tag dict and reading it back is the identity.
    """
    sidecar = LlSidecarTag(runid="roundtrip", output_root=tempfile.mkdtemp())
    sidecar.write(neutral_tags=tags, instance_id="i-xyz")
    recovered = sidecar.read(instance_id="i-xyz")
    assert recovered == tags
    return


@given(use_cluster=st.booleans(), constraints={"max_examples": 20})
def test_one_click_vs_single_instance_branch(use_cluster):
    """
        An InfiniBand spec resolves to the 1-Click Cluster API; a plain
        accelerator spec resolves to the single-instance launch API.
    """
    client = MockLambdalabsClient()
    if use_cluster is True:
        spec = cluster_spec()
    else:
        spec = basic_spec()

    provisioner = LambdalabsCloudProvisioner(
        venue=_venue(), credential=_credential(), client=client, spec=spec,
        output_root=tempfile.mkdtemp(),
    )
    provisioner.apply(aspects=_aspects())

    if use_cluster is True:
        assert client.cluster_calls == 1
        assert client.launch_calls == 0
    else:
        assert client.launch_calls == 1
        assert client.cluster_calls == 0
    return


def test_gpu_sku_resolution_maps_accelerator_to_slug():
    """
        The resolver maps the H100_SXM neutral name to the Lambda Labs
        ``gpu_8x_h100_sxm5`` slug.
    """
    from ccai.interfaces.cloudacceleratorspec import (
        CloudAcceleratorSpec
    )
    from ccai.provisioning.venues.lambdalabs.llresolver import LlResolver

    resolver = LlResolver()
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    resolution = resolver.accelerator_to_instance_type(accel_spec=accel,
                                                       interconnect=None)
    assert resolution.instance_type_slug == "gpu_8x_h100_sxm5"
    assert resolution.is_cluster is False
    return
