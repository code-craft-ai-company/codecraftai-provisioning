"""
    .. module:: fakecloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: In-memory CloudProvisioner reference subclass for property tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional, Tuple

from ccai.provisioning.model.exceptions import SchemaSemanticError
from ccai.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
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


class FakeCloudProvisioner(CloudProvisioner):
    """
        In-memory reference subclass used by property tests.

        The "venue" is a dict keyed by (kind, name).  Each apply runs the
        match-then-act loop documented on the base class.  Every venue
        plugin author is expected to compose this fake's property-test
        suite against their own SDK mock.
    """

    def __init__(self, *, venue: CloudVenue,
                 spec: Optional[Dict[str, Any]] = None) -> None:
        """
            Construct a FakeCloudProvisioner.

            :param venue: CloudVenue this fake is bound to.
            :param spec: Spec dict ``{"resources": [{"kind", "name", ...}]}``.
        """
        super().__init__(venue=venue, spec=spec)
        self._state: Dict[Tuple[str, str], ProvisionedResource] = {}
        self._mutation_log: List[Tuple[str, str, str]] = []
        return

    @property
    def state(self) -> Dict[Tuple[str, str], ProvisionedResource]:
        """
            Return the underlying state dict (mutable — test-only).

            :returns: The state dict.
        """
        rtnval = self._state
        return rtnval

    @property
    def mutation_log(self) -> List[Tuple[str, str, str]]:
        """
            Return the per-resource mutation log.

            Each entry is (op, kind, name).  Used by property tests to count
            mutations and prove idempotence.

            :returns: The mutation log.
        """
        rtnval = self._mutation_log
        return rtnval

    def _spec_resources(self) -> List[Dict[str, Any]]:
        """
            Return the list of resource dicts declared in the spec.

            :returns: List of resource dicts.
        """
        if self._spec is None:
            rtnval: List[Dict[str, Any]] = []
            return rtnval
        rtnval = list(self._spec.get("resources", []))
        return rtnval

    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the spec.  Checks duplicate (kind, name) pairs.

            :param aspects: Aspects.

            :returns: A ValidationResult.
            :raises: SchemaSemanticError
        """
        seen: set = set()
        duplicates: List[str] = []
        for entry in self._spec_resources():
            key = (entry["kind"], entry["name"])
            if key in seen:
                duplicates.append("{}/{}".format(key[0], key[1]))
            else:
                seen.add(key)

        if len(duplicates) > 0:
            err_msg_lines = ["Duplicate resources in spec."]
            for dup in duplicates:
                err_msg_lines.append("    {}".format(dup))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        """
            Compute a dry-run plan against the in-memory state.

            :param aspects: Aspects.

            :returns: A ProvisioningPlan.
        """
        actions: List[PlannedAction] = []

        spec_keys: set = set()
        for entry in self._spec_resources():
            key = (entry["kind"], entry["name"])
            spec_keys.add(key)
            existing = self._state.get(key, None)

            if existing is None:
                action = self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind=entry["kind"],
                    resource_name=entry["name"],
                    diff={"after": dict(entry.get("attributes", {}))},
                )
                actions.append(action)
            else:
                desired_attrs = entry.get("attributes", {})
                if existing.attributes != desired_attrs:
                    action = self._planned_action_for(
                        intent=PlannedActionIntent.UPDATE,
                        resource_kind=entry["kind"],
                        resource_name=entry["name"],
                        diff={"before": dict(existing.attributes),
                              "after": dict(desired_attrs)},
                    )
                    actions.append(action)
                else:
                    action = self._planned_action_for(
                        intent=PlannedActionIntent.SKIP,
                        resource_kind=entry["kind"],
                        resource_name=entry["name"],
                    )
                    actions.append(action)

        for key, existing in list(self._state.items()):
            if key not in spec_keys and self._is_owned(resource=existing):
                action = self._planned_action_for(
                    intent=PlannedActionIntent.DELETE,
                    resource_kind=key[0],
                    resource_name=key[1],
                )
                actions.append(action)

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def apply(self, *, aspects: Any) -> ProvisioningResult:
        """
            Apply the spec to the in-memory state.

            Match-then-act on each resource.  Already-matching resources
            produce no mutation log entry — that's what makes idempotence
            visible in tests.

            :param aspects: Aspects.

            :returns: A ProvisioningResult.
        """
        created: List[ProvisionedResource] = []
        updated: List[ProvisionedResource] = []
        skipped: List[str] = []

        for entry in self._spec_resources():
            key = (entry["kind"], entry["name"])
            existing = self._state.get(key, None)
            desired_attrs = dict(entry.get("attributes", {}))
            owner_tag = {self.OWNER_TAG_KEY: self.OWNER_TAG_VALUE}

            if existing is None:
                venue_id = "{}-{}-{}".format(
                    self._venue.name, entry["kind"], entry["name"]
                )
                resource = ProvisionedResource(
                    kind=entry["kind"], name=entry["name"],
                    venue_id=venue_id, attributes=desired_attrs,
                    tags=dict(owner_tag),
                )
                self._state[key] = resource
                self._mutation_log.append(("create", key[0], key[1]))
                created.append(resource)
            elif existing.attributes != desired_attrs:
                resource = ProvisionedResource(
                    kind=existing.kind, name=existing.name,
                    venue_id=existing.venue_id, attributes=desired_attrs,
                    tags=dict(existing.tags),
                )
                self._state[key] = resource
                self._mutation_log.append(("update", key[0], key[1]))
                updated.append(resource)
            else:
                skipped.append(entry["name"])

        rtnval = ProvisioningResult(created=created, updated=updated,
                                    skipped=skipped, errors=[])
        return rtnval

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Subclass hook: empty the state of every owned resource.

            :param aspects: Aspects.
        """
        for key in list(self._state.keys()):
            resource = self._state[key]
            if self._is_owned(resource=resource):
                del self._state[key]
                self._mutation_log.append(("delete", key[0], key[1]))
        return

    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        """
            Return all owned resources.

            :param aspects: Aspects.

            :returns: List of ProvisionedResource.
        """
        rtnval: List[ProvisionedResource] = []
        for resource in self._state.values():
            if self._is_owned(resource=resource):
                rtnval.append(resource)
        return rtnval

    def _is_owned(self, *, resource: ProvisionedResource) -> bool:
        """
            Check whether the resource carries the owner-tag pair.

            :param resource: The ProvisionedResource.

            :returns: True when owned by ccai.
        """
        rtnval = resource.tags.get(self.OWNER_TAG_KEY) == self.OWNER_TAG_VALUE
        return rtnval

    def seed_external_resource(self, *, resource: ProvisionedResource) -> None:
        """
            Test helper: insert a resource carrying no owner tag.

            Used by tag-ownership-invariant tests.

            :param resource: Resource to insert.
        """
        self._state[(resource.kind, resource.name)] = resource
        return
