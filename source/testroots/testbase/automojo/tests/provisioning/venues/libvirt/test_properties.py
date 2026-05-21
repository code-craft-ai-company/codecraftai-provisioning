"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based (hypothesis) tests for the libvirt venue
               provisioner — apply idempotence, destroy inversibility,
               metadata tag round-trip, and seed-ISO content-hash
               determinism.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.venues.libvirt.libvirtcloudprovisioner import (
    LibvirtCloudProvisioner
)
from automojo.provisioning.venues.libvirt.libvirtspec import LibvirtSpec
from automojo.provisioning.venues.libvirt.lvmetadatatranslator import (
    LvMetadataTranslator
)
from automojo.provisioning.venues.libvirt.lvseedisobuilder import (
    LvSeedIsoBuilder
)

from ._mockclient import MockLibvirtClient
from ._specfactory import (
    BASE_IMAGE_VOLUME, basic_spec, make_config, make_instance,
    make_keypair, make_network
)


def _venue() -> CloudVenue:
    """
        Build a CloudVenue for the property tests.

        :returns: A CloudVenue instance.
    """
    rtnval = CloudVenue(name="libvirt-prop", provider="libvirt",
                        endpoint="qemu:///system",
                        region="local", credential="lv")
    return rtnval


def _aspects() -> ProvisioningAspects:
    """
        Build a ProvisioningAspects bundle for the property tests.

        :returns: A ProvisioningAspects instance.
    """
    rtnval = ProvisioningAspects(runid="proprun01", verify_timeout=10.0,
                                 verify_interval=0.01)
    return rtnval


def _seeded_client() -> MockLibvirtClient:
    """
        Build a MockLibvirtClient with the base image seeded.

        :returns: A seeded MockLibvirtClient.
    """
    config = make_config()
    client = MockLibvirtClient()
    client.seed_base_image(pool=config.base_image_pool,
                           volume_name=BASE_IMAGE_VOLUME)
    rtnval = client
    return rtnval


@settings(max_examples=30, deadline=None)
@given(reapply_count=st.integers(min_value=1, max_value=4))
def test_apply_idempotent(reapply_count):
    """
        Repeated applies over the same client define exactly one domain
        regardless of how many times apply runs.
    """
    client = _seeded_client()
    provisioner = LibvirtCloudProvisioner(
        venue=_venue(), client=client, config=make_config(),
        spec=basic_spec(), output_root=tempfile.mkdtemp(),
    )
    for _ in range(reapply_count):
        provisioner.apply(aspects=_aspects())

    assert client.define_domain_calls == 1
    assert len(client.domains.list_domains(aspects=_aspects())) == 1
    return


@settings(max_examples=20, deadline=None)
@given(instance_count=st.integers(min_value=1, max_value=4))
def test_destroy_is_inverse_of_apply(instance_count):
    """
        apply followed by destroy leaves no run-owned domains, networks,
        or volumes.
    """
    client = _seeded_client()
    instances = []
    for index in range(instance_count):
        instances.append(make_instance(name="node{}".format(index)))
    spec = LibvirtSpec(networks=[make_network()],
                       keypairs=[make_keypair()], instances=instances)

    provisioner = LibvirtCloudProvisioner(
        venue=_venue(), client=client, config=make_config(), spec=spec,
        output_root=tempfile.mkdtemp(),
    )
    confirm = ProvisioningAspects(runid="proprun01", confirm=True,
                                  verify_timeout=10.0, verify_interval=0.01)

    provisioner.apply(aspects=_aspects())
    assert len(client.domains.list_domains(
        aspects=_aspects())) == instance_count

    provisioner.destroy(aspects=confirm)
    assert len(client.domains.list_domains(aspects=_aspects())) == 0
    assert len(client.networks.list_networks(aspects=_aspects())) == 0
    return


@settings(max_examples=80)
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
    min_size=0, max_size=5))
def test_metadata_tag_round_trip_identity(tags):
    """
        Embedding a neutral tag dict into XML metadata and extracting it
        back is the identity — even for namespaces, colons, and
        whitespace in keys and values.
    """
    translator = LvMetadataTranslator()
    inner = translator.embed(neutral_tags=tags, run_id="run-xyz")
    domain_xml = ("<domain><metadata>{}</metadata></domain>").format(inner)

    recovered = translator.extract(domain_xml=domain_xml)
    assert recovered == tags

    recovered_run = translator.extract_run_id(domain_xml=domain_xml)
    assert recovered_run == "run-xyz"
    return


@settings(max_examples=40, deadline=None)
@given(user_data=st.text(min_size=0, max_size=64),
       meta_data=st.text(min_size=0, max_size=64))
def test_seed_iso_content_hash_deterministic(user_data, meta_data):
    """
        Identical seed-ISO inputs always produce an identical content
        hash; differing inputs change the hash.
    """
    builder = LvSeedIsoBuilder(staging_root=tempfile.mkdtemp())

    first = builder.build(user_data=user_data, meta_data=meta_data,
                          network_config="", iso_path="/tmp/seed.iso")
    second = builder.build(user_data=user_data, meta_data=meta_data,
                           network_config="", iso_path="/tmp/seed.iso")
    assert first.content_hash == second.content_hash

    altered = builder.build(user_data=user_data + "x", meta_data=meta_data,
                            network_config="", iso_path="/tmp/seed.iso")
    assert altered.content_hash != first.content_hash
    return


def test_validate_rejects_unsupported_kinds(venue, aspects):
    """
        Buckets, load balancers, and DNS records all surface in a single
        validate-error message.
    """
    import pytest

    from ._specfactory import bucket_lb_dns_spec
    from automojo.provisioning.venues.libvirt.lverrors import (
        LvValidationError
    )

    provisioner = LibvirtCloudProvisioner(
        venue=venue, client=_seeded_client(), config=make_config(),
        spec=bucket_lb_dns_spec(),
    )
    with pytest.raises(LvValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    message = str(excinfo.value)
    assert "data-bucket" in message
    assert "api-lb" in message
    return
