"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based (hypothesis) tests for the Proxmox VE venue
               provisioner — apply idempotence, destroy inversibility, tag
               round-trip identity, and cloud-init snippet dedup.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


import tempfile

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.proxmox.proxmoxcloudprovisioner import (
    ProxmoxCloudProvisioner
)
from ccai.provisioning.venues.proxmox.proxmoxspec import ProxmoxSpec
from ccai.provisioning.venues.proxmox.pvecloudinitrenderer import (
    PveCloudInitRenderer
)
from ccai.provisioning.venues.proxmox.pvetagtranslator import (
    PveTagTranslator
)

from ccai.tests.provisioning.venues.proxmox._mockclient import MockProxmoxClient, RecordingVpnControlPlane
from ccai.tests.provisioning.venues.proxmox._specfactory import (
    basic_spec, make_credential, make_instance, make_keypair,
    make_network, make_resolver
)


def _venue() -> CloudVenue:
    """
        Build a CloudVenue for the property tests.

        :returns: A CloudVenue instance.
    """
    rtnval = CloudVenue(name="proxmox-prop", provider="proxmox",
                        endpoint="https://pve.test:8006",
                        region="local", credential="pve")
    return rtnval


def _aspects() -> ProvisioningAspects:
    """
        Build a ProvisioningAspects bundle for the property tests.

        :returns: A ProvisioningAspects instance.
    """
    rtnval = ProvisioningAspects(runid="proprun01", verify_timeout=10.0,
                                 verify_interval=0.01)
    return rtnval


@given(reapply_count=st.integers(min_value=1, max_value=4), constraints={"max_examples": 25})
def test_apply_idempotent(reapply_count):
    """
        Repeated applies over the same client clone exactly one VM
        regardless of how many times apply runs (apply ∘ apply = apply).
    """
    client = MockProxmoxClient()
    provisioner = ProxmoxCloudProvisioner(
        venue=_venue(), credential=make_credential(), client=client,
        spec=basic_spec(), resolver=make_resolver(),
        output_root=tempfile.mkdtemp(),
    )
    for _ in range(reapply_count):
        provisioner.apply(aspects=_aspects())

    assert client.clone_vm_calls == 1
    assert len(client.all_vms()) == 1
    return


@given(instance_count=st.integers(min_value=1, max_value=4), constraints={"max_examples": 20})
def test_destroy_is_inverse_of_apply(instance_count):
    """
        apply followed by destroy leaves no run-owned VMs
        (destroy ∘ apply = nop).
    """
    client = MockProxmoxClient()
    instances = []
    for index in range(instance_count):
        instances.append(make_instance(name="node{}".format(index)))
    spec = ProxmoxSpec(networks=[make_network()],
                       keypairs=[make_keypair()], instances=instances)

    provisioner = ProxmoxCloudProvisioner(
        venue=_venue(), credential=make_credential(), client=client,
        spec=spec, resolver=make_resolver(),
        output_root=tempfile.mkdtemp(),
    )
    confirm = ProvisioningAspects(runid="proprun01", confirm=True,
                                  verify_timeout=10.0, verify_interval=0.01)

    provisioner.apply(aspects=_aspects())
    assert len(client.all_vms()) == instance_count

    provisioner.destroy(aspects=confirm)
    assert len(client.all_vms()) == 0
    return


@given(tags=st.dictionaries(
    keys=st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"),
            whitelist_characters=" :/-_.",
        ),
        min_size=1, max_size=12),
    values=st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"),
            whitelist_characters=" :/-_.",
        ),
        min_size=1, max_size=12),
    min_size=0, max_size=5), constraints={"max_examples": 80})
def test_tag_round_trip_identity(tags):
    """
        Encoding a neutral tag dict into Proxmox tag strings and decoding
        it back is the identity — even for keys and values containing
        namespaces, colons, slashes, and whitespace.
    """
    encoded = PveTagTranslator.to_pve(neutral_tags=tags)
    recovered = PveTagTranslator.from_pve(pve_tags=encoded)
    assert recovered == tags
    return


@given(user_data=st.text(min_size=1, max_size=64), constraints={"max_examples": 40})
def test_snippet_upload_dedup(user_data):
    """
        Re-rendering and re-uploading an identical cloud-init snippet
        uploads it only once; a differing body uploads a fresh snippet.
    """
    client = MockProxmoxClient()
    renderer = PveCloudInitRenderer(client=client)
    instance = make_instance()
    instance.user_data_script = user_data

    renderer.render_and_upload(node_name="pve-node-1", instance=instance,
                               keypairs=[make_keypair()],
                               rendered_hostname="host", authkey="",
                               aspects=_aspects())
    renderer.render_and_upload(node_name="pve-node-1", instance=instance,
                               keypairs=[make_keypair()],
                               rendered_hostname="host", authkey="",
                               aspects=_aspects())
    assert client.upload_snippet_calls == 1

    instance.user_data_script = user_data + "-altered"
    renderer.render_and_upload(node_name="pve-node-1", instance=instance,
                               keypairs=[make_keypair()],
                               rendered_hostname="host", authkey="",
                               aspects=_aspects())
    assert client.upload_snippet_calls == 2
    return


def test_validate_rejects_unsupported_kinds(venue, aspects):
    """
        Object buckets and load balancers both surface in a single
        validate-error message.
    """

    from ccai.tests.provisioning.venues.proxmox._specfactory import bucket_lb_dns_spec
    from ccai.provisioning.venues.proxmox.pveerrors import (
        PveValidationError
    )

    provisioner = ProxmoxCloudProvisioner(
        venue=venue, credential=make_credential(),
        client=MockProxmoxClient(), spec=bucket_lb_dns_spec(),
        resolver=make_resolver(),
    )
    with testbase.raises(PveValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    message = str(excinfo.value)
    assert "data-bucket" in message
    assert "api-lb" in message
    return
