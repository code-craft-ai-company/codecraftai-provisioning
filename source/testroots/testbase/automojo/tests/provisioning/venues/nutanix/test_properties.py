"""
    .. module:: test_properties
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property tests (hypothesis) for the Nutanix venue
               provisioner: idempotent apply, inverse destroy, category
               round-trip identity, and the task-poll timeout aspect.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from hypothesis import given, settings
from hypothesis import strategies as st

from automojo.interop.nutanix.aspectsnutanix import AspectsNutanix
from automojo.interop.nutanix.model.nutanixtaskhandle import (
    NutanixTaskHandle
)

from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.venues.nutanix.nutanixcloudprovisioner import (
    NutanixCloudProvisioner
)
from automojo.provisioning.venues.nutanix.ntxcategorytranslator import (
    NtxCategoryTranslator
)

from ._mockclient import MockNutanixClient
from ._specfactory import basic_spec, make_config


def _venue() -> CloudVenue:
    """
        Build a CloudVenue for the property tests.

        :returns: A CloudVenue instance.
    """
    rtnval = CloudVenue(name="nutanix-prop", provider="nutanix",
                        management_url="https://prism.example.com:9440",
                        subscription="homelab", region="homelab",
                        credential="ntx-test")
    return rtnval


def _aspects() -> ProvisioningAspects:
    """
        Build a fast ProvisioningAspects bundle.

        :returns: A ProvisioningAspects instance.
    """
    rtnval = ProvisioningAspects(runid="propsrun01", confirm=True,
                                 verify_timeout=10.0, verify_interval=0.01)
    return rtnval


_TAG_KEYS = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1,
                    max_size=8)
_TAG_VALUES = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
                      min_size=1, max_size=8)


@settings(max_examples=25, deadline=None)
@given(tag_pairs=st.dictionaries(keys=_TAG_KEYS, values=_TAG_VALUES,
                                 min_size=0, max_size=4))
def test_apply_idempotent(tag_pairs):
    """
        apply ∘ apply yields the same VM inventory with no fresh creates.
    """
    tags = [{key: value} for key, value in tag_pairs.items()]
    client = MockNutanixClient()
    provisioner = NutanixCloudProvisioner(venue=_venue(), client=client,
                                          config=make_config(),
                                          spec=basic_spec(tags=tags))
    provisioner.apply(aspects=_aspects())
    vm_calls_after_first = client.create_vm_calls

    provisioner.apply(aspects=_aspects())
    assert client.create_vm_calls == vm_calls_after_first
    assert len(client.vms_state) == 1


@settings(max_examples=25, deadline=None)
@given(tag_pairs=st.dictionaries(keys=_TAG_KEYS, values=_TAG_VALUES,
                                 min_size=0, max_size=4))
def test_destroy_is_inverse_of_apply(tag_pairs):
    """
        destroy ∘ apply leaves the venue empty of run-owned resources.
    """
    tags = [{key: value} for key, value in tag_pairs.items()]
    client = MockNutanixClient()
    provisioner = NutanixCloudProvisioner(venue=_venue(), client=client,
                                          config=make_config(),
                                          spec=basic_spec(tags=tags))
    provisioner.apply(aspects=_aspects())
    provisioner.destroy(aspects=_aspects())

    assert len(client.vms_state) == 0
    assert len(client.subnets_state) == 0
    assert len(client.vpcs_state) == 0


@settings(max_examples=40, deadline=None)
@given(tag_pairs=st.dictionaries(keys=_TAG_KEYS, values=_TAG_VALUES,
                                 min_size=0, max_size=5))
def test_category_value_round_trip_identity(tag_pairs):
    """
        Translating neutral tags to Prism Categories and reading them
        back is the identity (modulo the injected automojo-run-id entry).
    """
    tags = [{key: value} for key, value in tag_pairs.items()]
    client = MockNutanixClient()
    provisioner = NutanixCloudProvisioner(venue=_venue(), client=client,
                                          config=make_config(),
                                          spec=basic_spec(tags=tags))
    provisioner.apply(aspects=_aspects())

    translator = NtxCategoryTranslator(client=client)
    vm = client.vms_state["node-propsrun"]
    recovered = translator.read(vm=vm)

    recovered_map = {}
    for entry in recovered:
        for key, value in entry.items():
            recovered_map[key] = value
    assert recovered_map == tag_pairs


def test_task_poll_honours_timeout_aspect():
    """
        A real NutanixTaskHandle polling a never-completing task raises
        TimeoutError bounded by the aspect completion_timeout.
    """
    client = MockNutanixClient()
    # An unknown task uuid is reported RUNNING forever by the mock.
    handle = NutanixTaskHandle(task_uuid="never-completes", client=client)
    aspects = AspectsNutanix(completion_timeout=0.2,
                             completion_interval=0.02)
    with pytest.raises(TimeoutError):
        handle.wait(aspects=aspects)
