"""
    .. module:: test_property_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based tests for the lifecycle contracts.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []



from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.model.cloud._fake.fakecloudprovisioner import (
    FakeCloudProvisioner
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)


_KINDS = ("network", "subnet", "sg", "instance", "volume", "bucket",
          "dns", "lb", "keypair")


def _venue() -> CloudVenue:
    rtnval = CloudVenue(name="lab", provider="fake",
                        region="r1", credential="cred")
    return rtnval


_name_st = st.text(alphabet=st.characters(min_codepoint=97,
                                          max_codepoint=122),
                   min_size=2, max_size=8)


def _resource_strategy() -> st.SearchStrategy:
    rtnval = st.fixed_dictionaries({
        "kind": st.sampled_from(_KINDS),
        "name": _name_st,
        "attributes": st.dictionaries(
            keys=st.sampled_from(["size", "cidr", "az"]),
            values=st.text(min_size=1, max_size=8),
            max_size=3,
        ),
    })
    return rtnval


def _spec_strategy() -> st.SearchStrategy:
    rtnval = st.lists(_resource_strategy(),
                      min_size=1, max_size=8,
                      unique_by=lambda e: (e["kind"], e["name"]))
    return rtnval


# Module-level on purpose: the testbase sequencer collects module-level
# ``test_*`` and drives ``@given`` from the metadata the decorator records.
# A @given-decorated TestCase *method* never receives its generated
# arguments, so it cannot run at all.


@given(resources=_spec_strategy(), constraints={"max_examples": 30})
def test_property_apply_apply_equals_apply(resources) -> None:
    """
        A second apply converges on the same inventory and writes no new
        mutations -- the definition of an idempotent apply.
    """
    spec = {"resources": resources}
    fake = FakeCloudProvisioner(venue=_venue(), spec=spec)
    aspects = ProvisioningAspects()

    fake.apply(aspects=aspects)
    first_inv = {(r.kind, r.name, r.venue_id)
                 for r in fake.inventory(aspects=aspects)}
    mutations_after_first = len(fake.mutation_log)

    fake.apply(aspects=aspects)
    second_inv = {(r.kind, r.name, r.venue_id)
                  for r in fake.inventory(aspects=aspects)}
    mutations_after_second = len(fake.mutation_log)

    assert first_inv == second_inv
    assert mutations_after_first == mutations_after_second
    return


@given(resources=_spec_strategy(), constraints={"max_examples": 30})
def test_property_destroy_after_apply_restores_pre_state(resources) -> None:
    """
        Destroy inverts apply, leaving the inventory as it was found.
    """
    spec = {"resources": resources}
    fake = FakeCloudProvisioner(venue=_venue(), spec=spec)
    aspects_apply = ProvisioningAspects()
    aspects_destroy = ProvisioningAspects(confirm=True)

    pre = list(fake.inventory(aspects=aspects_apply))
    fake.apply(aspects=aspects_apply)
    fake.destroy(aspects=aspects_destroy)
    post = list(fake.inventory(aspects=aspects_apply))

    assert pre == post
    return


@given(resources=_spec_strategy(), constraints={"max_examples": 30})
def test_property_plan_twice_yields_equal_action_lists(resources) -> None:
    """
        Planning is stable, so re-planning an unchanged spec does not
        reorder or invent actions.
    """
    spec = {"resources": resources}
    fake = FakeCloudProvisioner(venue=_venue(), spec=spec)
    aspects = ProvisioningAspects()

    plan_a = fake.plan(aspects=aspects)
    plan_b = fake.plan(aspects=aspects)

    names_a = [(a.intent, a.resource_kind, a.resource_name)
               for a in plan_a.actions]
    names_b = [(a.intent, a.resource_kind, a.resource_name)
               for a in plan_b.actions]

    assert names_a == names_b
    return


@given(resources=_spec_strategy(), constraints={"max_examples": 30})
def test_property_every_owned_resource_carries_owner_tag(resources) -> None:
    """
        Everything apply creates is tagged as owned, so destroy can tell
        our resources from anything else living in the venue.
    """
    spec = {"resources": resources}
    fake = FakeCloudProvisioner(venue=_venue(), spec=spec)
    aspects = ProvisioningAspects()
    fake.apply(aspects=aspects)

    owner_key = FakeCloudProvisioner.OWNER_TAG_KEY
    owner_value = FakeCloudProvisioner.OWNER_TAG_VALUE
    for resource in fake.inventory(aspects=aspects):
        assert resource.tags.get(owner_key) == owner_value, \
            "resource missing owner tag: {!r}".format(resource)
    return
