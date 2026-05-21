"""
    .. module:: test_m6_exit
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: M6 milestone exit-criterion smoke test.

    The exit criterion: a `ProvisioningEngine.plan(...)` call with dry-run
    aspects returns a complete MultiVenueProvisioningPlan covering at least
    two distinct mock venues and every declared resource — with no side
    effects on any provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import unittest

from typing import Any, Dict, List

from automojo.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.model.cloud.plannedaction import PlannedAction
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from automojo.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.model.cloud.validationresult import ValidationResult
from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.cloudprovisionerregistry import (
    CloudProvisionerRegistry
)
from automojo.provisioning.pipelineplan import MultiVenueProvisioningPlan
from automojo.provisioning.provisioningengine import ProvisioningEngine


class _SideEffectFreeProvisioner(CloudProvisioner):
    """
        Records every method call so the M6 exit test can prove plan() is
        side-effect free.
    """

    def __init__(self, *, venue: CloudVenue,
                 venue_spec: Dict[str, Any]) -> None:
        super().__init__(venue=venue, spec=venue_spec)
        self.calls: List[str] = []
        return

    def validate(self, *, aspects: Any) -> ValidationResult:
        self.calls.append("validate")
        rtnval = ValidationResult(ok=True)
        return rtnval

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        self.calls.append("plan")
        actions: List[PlannedAction] = []
        for entry in self.spec.get("resources", []):
            actions.append(PlannedAction(
                intent=PlannedActionIntent.CREATE,
                resource_kind=entry["kind"],
                resource_name=entry["name"],
            ))
        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def apply(self, *, aspects: Any) -> ProvisioningResult:
        self.calls.append("apply")
        raise AssertionError("apply must not be invoked in dry-run.")

    def apply_subset(self, *, kinds: List[str],
                     aspects: Any) -> ProvisioningResult:
        self.calls.append("apply_subset")
        raise AssertionError(
            "apply_subset must not be invoked in dry-run."
        )

    def _destroy_impl(self, *, aspects: Any) -> None:
        self.calls.append("_destroy_impl")
        raise AssertionError("_destroy_impl must not be invoked in dry-run.")

    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        self.calls.append("inventory")
        rtnval: List[ProvisionedResource] = []
        return rtnval


def _venue(name: str) -> CloudVenue:
    rtnval = CloudVenue(name=name, provider="mock",
                        region="r", credential="cred")
    return rtnval


class M6ExitCriterionTests(unittest.TestCase):

    def test_dry_run_plan_covers_multi_venue_spec_without_side_effects(
        self,
    ) -> None:
        east_spec = {"resources": [
            {"kind": "network", "name": "vpc-east"},
            {"kind": "instance", "name": "web-01"},
        ]}
        west_spec = {"resources": [
            {"kind": "instance", "name": "web-02"},
            {"kind": "bucket", "name": "logs-west"},
        ]}
        engine_spec = {
            "apod": {"name": "lab"},
            "venues": [{"name": "mock-east"}, {"name": "mock-west"}],
            "networks": [{"name": "vpc-east"}],
            "subnets": [{"name": "sub-east", "network": "vpc-east"}],
            "instances": [
                {"name": "web-01", "subnet": "sub-east"},
                {"name": "web-02", "subnet": "sub-east"},
            ],
            "buckets": [{"name": "logs-west"}],
        }

        east = _SideEffectFreeProvisioner(venue=_venue("mock-east"),
                                          venue_spec=east_spec)
        west = _SideEffectFreeProvisioner(venue=_venue("mock-west"),
                                          venue_spec=west_spec)

        registry = CloudProvisionerRegistry()
        registry.register(name="mock-east", provisioner=east)
        registry.register(name="mock-west", provisioner=west)

        engine = ProvisioningEngine(spec=engine_spec, registry=registry)
        aspects = ProvisioningAspects(dry_run=True)

        plan = engine.plan(aspects=aspects)

        # 1. The returned object is a MultiVenueProvisioningPlan.
        self.assertIsInstance(plan, MultiVenueProvisioningPlan)

        # 2. The plan covers at least two distinct mock venues.
        self.assertEqual(set(plan.per_venue_plans.keys()),
                         {"mock-east", "mock-west"})

        # 3. Every resource declared per venue is represented exactly once.
        east_names = sorted(
            a.resource_name for a in plan.per_venue_plans["mock-east"].actions
        )
        west_names = sorted(
            a.resource_name for a in plan.per_venue_plans["mock-west"].actions
        )
        self.assertEqual(east_names, ["vpc-east", "web-01"])
        self.assertEqual(west_names, ["logs-west", "web-02"])

        # 4. No side effect occurred — only validate and plan were called.
        self.assertEqual(east.calls, ["validate", "plan"])
        self.assertEqual(west.calls, ["validate", "plan"])

        # 5. apply() is also a no-op when dry_run is set: returns empty.
        apply_result = engine.apply(aspects=aspects)
        self.assertEqual(apply_result, {})
        self.assertEqual(east.calls,
                         ["validate", "plan", "validate", "plan"])

        # 6. The topological order is populated.
        self.assertGreater(len(plan.topological_order), 0)
        return


if __name__ == "__main__":
    unittest.main()
