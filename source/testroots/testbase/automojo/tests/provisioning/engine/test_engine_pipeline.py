"""
    .. module:: test_engine_pipeline
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the ProvisioningEngine pipeline behaviour.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import tempfile
import unittest

from pathlib import Path
from typing import Any, Dict, List

from automojo.provisioning.model.exceptions import SchemaSemanticError
from automojo.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from automojo.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from automojo.provisioning.model.cloud.plannedaction import PlannedAction
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.validationresult import ValidationResult
from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.cloudprovisionerregistry import (
    CloudProvisionerRegistry
)
from automojo.provisioning.provisioningengine import ProvisioningEngine
from automojo.provisioning.state.provisioningstatestore import (
    ProvisioningStateStore
)


class MockCloudProvisioner(CloudProvisioner):
    """
        Mock provisioner that records stage call order and produces a
        plan/result reflecting the spec's instances.
    """

    def __init__(self, *, venue: CloudVenue,
                 venue_spec: Dict[str, Any]) -> None:
        super().__init__(venue=venue, spec=venue_spec)
        self.apply_calls: List[List[str]] = []
        self.destroy_calls: int = 0
        self.validate_calls: int = 0
        self._inventory: List[ProvisionedResource] = []
        return

    def validate(self, *, aspects: Any) -> ValidationResult:
        self.validate_calls = self.validate_calls + 1
        rtnval = ValidationResult(ok=True)
        return rtnval

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        actions: List[PlannedAction] = []
        for entry in self._iter_resources():
            actions.append(PlannedAction(
                intent=PlannedActionIntent.CREATE,
                resource_kind=entry["kind"],
                resource_name=entry["name"],
            ))
        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def apply(self, *, aspects: Any) -> ProvisioningResult:
        # apply_subset uses this method; record nothing here.
        created: List[ProvisionedResource] = []
        for entry in self._iter_resources():
            existing = next(
                (r for r in self._inventory if r.name == entry["name"]),
                None,
            )
            if existing is None:
                res = ProvisionedResource(
                    kind=entry["kind"], name=entry["name"],
                    venue_id="{}-{}".format(self.venue.name, entry["name"]),
                    attributes=dict(entry.get("attributes", {})),
                    tags={self.OWNER_TAG_KEY: self.OWNER_TAG_VALUE},
                )
                self._inventory.append(res)
                created.append(res)
        rtnval = ProvisioningResult(created=created)
        return rtnval

    def apply_subset(self, *, kinds: List[str],
                     aspects: Any) -> ProvisioningResult:
        self.apply_calls.append(list(kinds))
        full = self.apply(aspects=aspects)
        wanted = set(kinds)
        filtered_created = [r for r in full.created if r.kind in wanted]
        rtnval = ProvisioningResult(created=filtered_created)
        return rtnval

    def _destroy_impl(self, *, aspects: Any) -> None:
        self.destroy_calls = self.destroy_calls + 1
        self._inventory = []
        return

    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        rtnval = list(self._inventory)
        return rtnval

    def _iter_resources(self) -> List[Dict[str, Any]]:
        spec = self.spec if self.spec is not None else {}
        rtnval: List[Dict[str, Any]] = []
        for entry in spec.get("instances", []):
            rtnval.append({"kind": "instance", "name": entry["name"],
                           "attributes": {}})
        for entry in spec.get("networks", []):
            rtnval.append({"kind": "network", "name": entry["name"],
                           "attributes": {}})
        return rtnval


def _venue(name: str) -> CloudVenue:
    rtnval = CloudVenue(name=name, provider="mock",
                        region="r", credential="cred")
    return rtnval


def _multi_venue_spec() -> Dict[str, Any]:
    rtnval = {
        "apod": {"name": "lab"},
        "venues": [{"name": "mock-east"}, {"name": "mock-west"}],
        "networks": [{"name": "vpc-east"}],
        "subnets": [{"name": "sub-east", "network": "vpc-east"}],
        "instances": [
            {"name": "web-01", "subnet": "sub-east"},
            {"name": "web-02", "subnet": "sub-east"},
        ],
    }
    return rtnval


def _build_engine_for_dryrun(*, with_state: bool = False
                             ) -> ProvisioningEngine:
    registry = CloudProvisionerRegistry()
    east_spec = {"instances": [{"name": "web-01"}],
                 "networks": [{"name": "vpc-east"}]}
    west_spec = {"instances": [{"name": "web-02"}]}
    registry.register(name="mock-east",
                      provisioner=MockCloudProvisioner(
                          venue=_venue("mock-east"),
                          venue_spec=east_spec))
    registry.register(name="mock-west",
                      provisioner=MockCloudProvisioner(
                          venue=_venue("mock-west"),
                          venue_spec=west_spec))

    rtnval = ProvisioningEngine(spec=_multi_venue_spec(), registry=registry)
    return rtnval


class EnginePlanTests(unittest.TestCase):

    def test_plan_aggregates_per_venue_plans(self) -> None:
        engine = _build_engine_for_dryrun()
        aspects = ProvisioningAspects(dry_run=True)
        plan = engine.plan(aspects=aspects)
        self.assertEqual(set(plan.per_venue_plans.keys()),
                         {"mock-east", "mock-west"})
        self.assertGreater(plan.total_action_count(), 0)
        return

    def test_apply_dry_run_returns_empty_dict_no_side_effects(self) -> None:
        engine = _build_engine_for_dryrun()
        aspects = ProvisioningAspects(dry_run=True)
        result = engine.apply(aspects=aspects)
        self.assertEqual(result, {})
        # No apply_subset calls on any provisioner.
        for _, prov in engine._registry.items():
            self.assertEqual(prov.apply_calls, [])
        return


class EngineApplyTests(unittest.TestCase):

    def test_apply_runs_stages_in_documented_order(self) -> None:
        engine = _build_engine_for_dryrun()
        aspects = ProvisioningAspects()
        engine.apply(aspects=aspects)

        for _, prov in engine._registry.items():
            # Three apply_subset invocations: networking, compute, dns/storage/lb.
            self.assertEqual(len(prov.apply_calls), 3)
            self.assertIn("network", prov.apply_calls[0])
            self.assertIn("instance", prov.apply_calls[1])
        return

    def test_destroy_without_confirm_raises_semantic_error(self) -> None:
        engine = _build_engine_for_dryrun()
        aspects = ProvisioningAspects(confirm=False)
        with self.assertRaises(SchemaSemanticError):
            engine.destroy(aspects=aspects)
        return

    def test_destroy_with_confirm_invokes_each_provisioner(self) -> None:
        engine = _build_engine_for_dryrun()
        engine.apply(aspects=ProvisioningAspects())
        aspects = ProvisioningAspects(confirm=True)
        engine.destroy(aspects=aspects)
        for _, prov in engine._registry.items():
            self.assertEqual(prov.destroy_calls, 1)
        return


class EngineStateIntegrationTests(unittest.TestCase):

    def test_apply_persists_state_when_store_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProvisioningStateStore(root=Path(tmp))
            registry = CloudProvisionerRegistry()
            registry.register(name="mock-east",
                              provisioner=MockCloudProvisioner(
                                  venue=_venue("mock-east"),
                                  venue_spec={"instances": [{"name": "w"}]}))
            engine = ProvisioningEngine(
                spec=_multi_venue_spec(), registry=registry,
                state_store=store,
            )
            engine.apply(aspects=ProvisioningAspects())
            self.assertTrue((Path(tmp) / engine.runid).exists())
            self.assertTrue(
                (Path(tmp) / engine.runid / "inventory.yaml").exists()
            )
            self.assertTrue(
                (Path(tmp) / engine.runid / "landscape.yaml").exists()
            )
        return

    def test_apply_seeds_runid_so_destroy_after_apply_succeeds(self
                                                               ) -> None:
        """
            PC-H4 regression: apply seeds aspects.runid when a state store is
            configured, so a destroy issued with the same aspects object
            after apply locates the persisted run instead of raising.
        """
        with tempfile.TemporaryDirectory() as tmp:
            store = ProvisioningStateStore(root=Path(tmp))
            registry = CloudProvisionerRegistry()
            registry.register(name="mock-east",
                              provisioner=MockCloudProvisioner(
                                  venue=_venue("mock-east"),
                                  venue_spec={"instances": [{"name": "w"}]}))
            engine = ProvisioningEngine(
                spec=_multi_venue_spec(), registry=registry,
                state_store=store,
            )

            aspects = ProvisioningAspects()
            engine.apply(aspects=aspects)
            # apply seeded the runid onto the aspects object.
            self.assertEqual(aspects.runid, engine.runid)

            # destroy with the same aspects object must not raise.
            aspects.confirm = True
            engine.destroy(aspects=aspects)
            self.assertTrue(
                (Path(tmp) / "{}.destroyed".format(engine.runid)).exists()
            )
        return


if __name__ == "__main__":
    unittest.main()
