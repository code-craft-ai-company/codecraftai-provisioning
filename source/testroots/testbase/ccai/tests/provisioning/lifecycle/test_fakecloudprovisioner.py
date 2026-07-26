"""
    .. module:: test_fakecloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for FakeCloudProvisioner — base-class contract checks.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.model.cloud._fake.fakecloudprovisioner import (
    FakeCloudProvisioner
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)


def _make_venue() -> CloudVenue:
    rtnval = CloudVenue(name="lab", provider="fake",
                        region="r1", credential="cred")
    return rtnval


def _basic_spec() -> dict:
    rtnval = {
        "resources": [
            {"kind": "network", "name": "vpc-a",
             "attributes": {"cidr": "10.0.0.0/16"}},
            {"kind": "instance", "name": "web-01",
             "attributes": {"size": "m5.large"}},
        ]
    }
    return rtnval


class FakeProvisionerBasicTests(unittest.TestCase):

    def test_apply_creates_resources(self) -> None:
        fake = FakeCloudProvisioner(venue=_make_venue(), spec=_basic_spec())
        aspects = ProvisioningAspects()
        result = fake.apply(aspects=aspects)
        self.assertEqual(len(result.created), 2)
        self.assertEqual(len(fake.inventory(aspects=aspects)), 2)
        return

    def test_destroy_without_confirm_raises_semantic_error(self) -> None:
        fake = FakeCloudProvisioner(venue=_make_venue(), spec=_basic_spec())
        aspects = ProvisioningAspects(confirm=False)
        with self.assertRaises(SchemaSemanticError):
            fake.destroy(aspects=aspects)
        return

    def test_destroy_with_confirm_empties_inventory(self) -> None:
        fake = FakeCloudProvisioner(venue=_make_venue(), spec=_basic_spec())
        aspects_apply = ProvisioningAspects()
        aspects_destroy = ProvisioningAspects(confirm=True)
        fake.apply(aspects=aspects_apply)
        fake.destroy(aspects=aspects_destroy)
        self.assertEqual(fake.inventory(aspects=aspects_apply), [])
        return

    def test_plan_marks_existing_as_skip(self) -> None:
        fake = FakeCloudProvisioner(venue=_make_venue(), spec=_basic_spec())
        aspects = ProvisioningAspects()
        fake.apply(aspects=aspects)
        plan = fake.plan(aspects=aspects)
        intents = {a.resource_name: a.intent_enum for a in plan.actions}
        self.assertEqual(intents["vpc-a"], PlannedActionIntent.SKIP)
        self.assertEqual(intents["web-01"], PlannedActionIntent.SKIP)
        return

    def test_inventory_excludes_unowned_resources(self) -> None:
        fake = FakeCloudProvisioner(venue=_make_venue(), spec=_basic_spec())
        aspects = ProvisioningAspects()
        fake.apply(aspects=aspects)
        external = ProvisionedResource(
            kind="instance", name="external-host",
            venue_id="i-ext", tags={},
        )
        fake.seed_external_resource(resource=external)
        names = {r.name for r in fake.inventory(aspects=aspects)}
        self.assertNotIn("external-host", names)
        return

    def test_validate_rejects_duplicates(self) -> None:
        spec = {
            "resources": [
                {"kind": "network", "name": "dup",
                 "attributes": {"cidr": "10.0.0.0/16"}},
                {"kind": "network", "name": "dup",
                 "attributes": {"cidr": "10.0.0.0/16"}},
            ]
        }
        fake = FakeCloudProvisioner(venue=_make_venue(), spec=spec)
        with self.assertRaises(SchemaSemanticError):
            fake.validate(aspects=ProvisioningAspects())
        return

    def test_destroy_does_not_remove_unowned(self) -> None:
        fake = FakeCloudProvisioner(venue=_make_venue(), spec=_basic_spec())
        aspects_apply = ProvisioningAspects()
        aspects_destroy = ProvisioningAspects(confirm=True)
        fake.apply(aspects=aspects_apply)
        external = ProvisionedResource(kind="bucket", name="external-bk",
                                       venue_id="bk-ext", tags={})
        fake.seed_external_resource(resource=external)
        fake.destroy(aspects=aspects_destroy)
        leftover_keys = list(fake.state.keys())
        self.assertEqual(leftover_keys, [("bucket", "external-bk")])
        return


if __name__ == "__main__":
    unittest.main()
