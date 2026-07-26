"""
    .. module:: test_provisioning_dataclasses
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the lifecycle dataclasses (PlannedAction,
               ProvisioningPlan, ProvisionedResource, ProvisioningResult).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from ccai.interfaces.schemavalidationerror import SchemaValidationError
from ccai.provisioning.model.cloud.plannedaction import PlannedAction
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from ccai.provisioning.model.cloud.validationresult import ValidationResult


class PlannedActionTests(unittest.TestCase):

    def test_roundtrip(self) -> None:
        action = PlannedAction(intent=PlannedActionIntent.CREATE,
                               resource_kind="instance",
                               resource_name="web-01",
                               diff={"after": {"size": "m5.large"}})
        rebuilt = PlannedAction.from_dict(action.to_dict())
        self.assertEqual(action.intent, rebuilt.intent)
        self.assertEqual(action.resource_kind, rebuilt.resource_kind)
        self.assertEqual(action.resource_name, rebuilt.resource_name)
        self.assertEqual(action.diff, rebuilt.diff)
        return

    def test_string_intent_promoted(self) -> None:
        action = PlannedAction(intent="update", resource_kind="network",
                               resource_name="lab")
        self.assertEqual(action.intent_enum, PlannedActionIntent.UPDATE)
        return

    def test_rejects_bad_intent(self) -> None:
        with self.assertRaises(SchemaValidationError):
            PlannedAction(intent="ignite", resource_kind="x",
                          resource_name="y")
        return

    def test_rejects_empty_kind(self) -> None:
        with self.assertRaises(SchemaValidationError):
            PlannedAction(intent=PlannedActionIntent.CREATE,
                          resource_kind="", resource_name="y")
        return


class ProvisioningPlanTests(unittest.TestCase):

    def test_roundtrip_promotes_actions(self) -> None:
        actions = [
            PlannedAction(intent=PlannedActionIntent.CREATE,
                          resource_kind="network", resource_name="lab"),
            PlannedAction(intent=PlannedActionIntent.SKIP,
                          resource_kind="subnet", resource_name="lab-a"),
        ]
        plan = ProvisioningPlan(actions=actions)
        rebuilt = ProvisioningPlan.from_dict(plan.to_dict())
        self.assertEqual(len(rebuilt.actions), 2)
        self.assertEqual(rebuilt.actions[0].resource_name, "lab")
        return

    def test_empty_plan_ok(self) -> None:
        plan = ProvisioningPlan()
        self.assertEqual(plan.actions, [])
        return


class ProvisionedResourceTests(unittest.TestCase):

    def test_roundtrip(self) -> None:
        res = ProvisionedResource(kind="instance", name="web-01",
                                  venue_id="i-12345",
                                  attributes={"public_ip": "203.0.113.10"},
                                  tags={"role": "web"})
        rebuilt = ProvisionedResource.from_dict(res.to_dict())
        self.assertEqual(res, rebuilt)
        return

    def test_requires_nonempty_id(self) -> None:
        with self.assertRaises(SchemaValidationError):
            ProvisionedResource(kind="instance", name="x", venue_id="")
        return


class ProvisioningResultTests(unittest.TestCase):

    def test_roundtrip_promotes_resources(self) -> None:
        res = ProvisionedResource(kind="instance", name="web-01",
                                  venue_id="i-1")
        result = ProvisioningResult(created=[res], skipped=["lab"])
        rebuilt = ProvisioningResult.from_dict(result.to_dict())
        self.assertEqual(len(rebuilt.created), 1)
        self.assertEqual(rebuilt.created[0].name, "web-01")
        self.assertEqual(rebuilt.skipped, ["lab"])
        return


class ValidationResultTests(unittest.TestCase):

    def test_roundtrip_ok(self) -> None:
        r = ValidationResult(ok=True)
        rebuilt = ValidationResult.from_dict(r.to_dict())
        self.assertTrue(rebuilt.ok)
        return


if __name__ == "__main__":
    unittest.main()
