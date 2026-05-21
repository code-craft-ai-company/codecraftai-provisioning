"""
    .. module:: test_property_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based tests for the lifecycle contracts.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import unittest

from hypothesis import given, settings, strategies as st

from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.model.cloud._fake.fakecloudprovisioner import (
    FakeCloudProvisioner
)
from automojo.provisioning.aspects.provisioningaspects import (
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


class ApplyIdempotenceProperty(unittest.TestCase):

    @settings(max_examples=30, deadline=None)
    @given(resources=_spec_strategy())
    def test_apply_apply_equals_apply(self, resources) -> None:
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

        self.assertEqual(first_inv, second_inv)
        # Idempotence: the second apply produces zero new mutation log entries.
        self.assertEqual(mutations_after_first, mutations_after_second)
        return


class DestroyInversibilityProperty(unittest.TestCase):

    @settings(max_examples=30, deadline=None)
    @given(resources=_spec_strategy())
    def test_destroy_after_apply_restores_pre_state(self, resources) -> None:
        spec = {"resources": resources}
        fake = FakeCloudProvisioner(venue=_venue(), spec=spec)
        aspects_apply = ProvisioningAspects()
        aspects_destroy = ProvisioningAspects(confirm=True)

        pre = list(fake.inventory(aspects=aspects_apply))
        fake.apply(aspects=aspects_apply)
        fake.destroy(aspects=aspects_destroy)
        post = list(fake.inventory(aspects=aspects_apply))

        self.assertEqual(pre, post)
        return


class PlanStabilityProperty(unittest.TestCase):

    @settings(max_examples=30, deadline=None)
    @given(resources=_spec_strategy())
    def test_plan_twice_yields_equal_action_lists(self, resources) -> None:
        spec = {"resources": resources}
        fake = FakeCloudProvisioner(venue=_venue(), spec=spec)
        aspects = ProvisioningAspects()

        plan_a = fake.plan(aspects=aspects)
        plan_b = fake.plan(aspects=aspects)

        names_a = [(a.intent, a.resource_kind, a.resource_name)
                   for a in plan_a.actions]
        names_b = [(a.intent, a.resource_kind, a.resource_name)
                   for a in plan_b.actions]
        self.assertEqual(names_a, names_b)
        return


class OwnerTagInvariantProperty(unittest.TestCase):

    @settings(max_examples=30, deadline=None)
    @given(resources=_spec_strategy())
    def test_every_owned_resource_carries_owner_tag(self, resources) -> None:
        spec = {"resources": resources}
        fake = FakeCloudProvisioner(venue=_venue(), spec=spec)
        aspects = ProvisioningAspects()
        fake.apply(aspects=aspects)

        owner_key = FakeCloudProvisioner.OWNER_TAG_KEY
        owner_value = FakeCloudProvisioner.OWNER_TAG_VALUE
        for resource in fake.inventory(aspects=aspects):
            has_tag = resource.tags.get(owner_key) == owner_value
            self.assertTrue(has_tag,
                            "resource missing owner tag: {!r}".format(resource))
        return


if __name__ == "__main__":
    unittest.main()
