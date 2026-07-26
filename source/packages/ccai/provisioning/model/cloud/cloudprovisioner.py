"""
    .. module:: cloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Abstract base class for cloud venue provisioners.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ccai.interfaces.schemasemanticerror import SchemaSemanticError
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


# Dependency-order weights for kinds.  Lower numbers run first (apply); the
# engine reverses this for destroy.  Subclasses do not implement ordering;
# the base class provides _destroy_order(plan).
_KIND_ORDER: Dict[str, int] = {
    "network": 10,
    "subnet": 20,
    "sg": 30,
    "security_group": 30,
    "keypair": 40,
    "image": 50,
    "instance": 60,
    "volume": 70,
    "volume_attachment": 80,
    "shared_filesystem": 90,
    "bucket": 100,
    "lb": 110,
    "load_balancer": 110,
    "dns": 120,
    "dns_record": 120,
}


class CloudProvisioner(ABC):
    """
        Abstract base for cloud-venue provisioners.

        Defines the five-verb lifecycle every venue plugin implements:

            validate  — shape + semantic checks; no remote I/O.
            plan      — dry-run; reads venue, returns ProvisioningPlan.
            apply     — match-then-act; idempotent.
            destroy   — reverse-order teardown; gated by aspects.confirm.
            inventory — enumerate owned resources.

        Two contracts every subclass must honour:

        * Idempotence — `apply ∘ apply = apply`.  Subclasses achieve this with
          read-before-create on every resource: look up by owner tag,
          compare shape, create only when absent.
        * Inversibility — `destroy ∘ apply = nop` (modulo external state).
          Required so CI runs can clean up after themselves.

        Both contracts are proven by property tests against the in-memory
        FakeCloudProvisioner reference subclass.

        Required template for every resource kind:

            def _ensure_<kind>(self, *, desired, aspects):
                existing = self._read_<kind>_by_tag(desired=desired, aspects=aspects)
                if existing is None:
                    created = self._create_<kind>(desired=desired, aspects=aspects)
                    rtnval = created
                elif not self._<kind>_matches(existing=existing, desired=desired):
                    updated = self._update_<kind>(existing=existing,
                                                  desired=desired,
                                                  aspects=aspects)
                    rtnval = updated
                else:
                    rtnval = existing
                return rtnval

        Every created resource carries the ownership tag pair
        (OWNER_TAG_KEY, OWNER_TAG_VALUE) so subsequent reads (and destroys)
        can identify codecraftai-owned resources without false positives.
    """

    OWNER_TAG_KEY: str = "ccai:owned-by"
    OWNER_TAG_VALUE: str = "codecraftai-provisioning"

    def __init__(self, *, venue: CloudVenue,
                 spec: Optional[Any] = None) -> None:
        """
            Initialise the cloud provisioner.

            :param venue: The CloudVenue this provisioner targets.
            :param spec: Optional venue-scoped spec object.  May be None when
                         a subclass is being used purely for inventory or
                         destroy from a persisted runid.
        """
        self._venue: CloudVenue = venue
        self._spec: Optional[Any] = spec
        return

    @property
    def venue(self) -> CloudVenue:
        """
            Return the CloudVenue this provisioner is bound to.

            :returns: The CloudVenue.
        """
        rtnval = self._venue
        return rtnval

    @property
    def spec(self) -> Optional[Any]:
        """
            Return the venue-scoped spec, if any.

            :returns: The spec object or None.
        """
        rtnval = self._spec
        return rtnval

    @abstractmethod
    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the venue-scoped spec.

            No remote I/O is performed.  Failures raise SchemaSemanticError
            with a multi-line message enumerating every offending resource.

            :param aspects: Aspects controlling validation behaviour.

            :returns: A ValidationResult with ok=True on success.
            :raises: SchemaSemanticError
        """
        raise NotImplementedError(
            "{}.validate must be implemented by subclasses.".format(
                type(self).__name__
            )
        )

    @abstractmethod
    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        """
            Compute a dry-run plan of intended actions.

            Reads venue state but performs no mutation.

            :param aspects: Aspects controlling planning behaviour.

            :returns: A ProvisioningPlan.
        """
        raise NotImplementedError(
            "{}.plan must be implemented by subclasses.".format(
                type(self).__name__
            )
        )

    @abstractmethod
    def apply(self, *, aspects: Any) -> ProvisioningResult:
        """
            Apply the plan in match-then-act fashion.

            Idempotent: running apply twice in succession yields the same
            inventory.

            :param aspects: Aspects controlling apply behaviour.

            :returns: A ProvisioningResult.
        """
        raise NotImplementedError(
            "{}.apply must be implemented by subclasses.".format(
                type(self).__name__
            )
        )

    def destroy(self, *, aspects: Any) -> None:
        """
            Tear down every owned resource in reverse dependency order.

            Gated by ``aspects.confirm = True``.  Without confirmation, this
            method raises SemanticError before dispatching to subclass code.

            :param aspects: Aspects controlling destroy behaviour.

            :raises: SchemaSemanticError
        """
        confirm = self._aspect_attr(aspects=aspects, name="confirm",
                                    default=False)
        if confirm is not True:
            err_msg = (
                "CloudProvisioner.destroy requires aspects.confirm=True "
                "to prevent accidental destruction."
            )
            raise SchemaSemanticError(err_msg)

        self._destroy_impl(aspects=aspects)
        return

    @abstractmethod
    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Subclass hook for destroy after confirm-gating.

            :param aspects: Aspects.
        """
        raise NotImplementedError(
            "{}._destroy_impl must be implemented by subclasses.".format(
                type(self).__name__
            )
        )

    @abstractmethod
    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        """
            Return an inventory of currently-known owned resources.

            :param aspects: Aspects controlling inventory behaviour.

            :returns: A list of ProvisionedResource entries.
        """
        raise NotImplementedError(
            "{}.inventory must be implemented by subclasses.".format(
                type(self).__name__
            )
        )

    def apply_subset(self, *, kinds: List[str],
                     aspects: Any) -> ProvisioningResult:
        """
            Apply only the subset of the spec whose kinds match.

            Default implementation calls ``apply`` and filters the result.
            Subclasses may override for finer-grained control.

            :param kinds: List of resource kind strings to include.
            :param aspects: Aspects controlling apply behaviour.

            :returns: A filtered ProvisioningResult.
        """
        full_result = self.apply(aspects=aspects)

        wanted = set(kinds)
        filtered_created = [r for r in full_result.created if r.kind in wanted]
        filtered_updated = [r for r in full_result.updated if r.kind in wanted]

        rtnval = ProvisioningResult(created=filtered_created,
                                    updated=filtered_updated,
                                    skipped=list(full_result.skipped),
                                    errors=list(full_result.errors))
        return rtnval

    @classmethod
    def supports_preemption(cls) -> bool:
        """
            Whether this venue offers spot / preemptible / interruptible
            capacity.

            Consulted by the spec validator for documentation purposes only;
            it does not change behaviour — the ``preemption_policy`` field is
            honoured on every venue (on venues that never preempt, all three
            policy values are simply equivalent).

            :returns: True when the venue can reclaim instances; False by
                      default.
        """
        rtnval = False
        return rtnval

    @classmethod
    def _planned_action_for(cls, *, intent: PlannedActionIntent,
                            resource_kind: str, resource_name: str,
                            diff: Optional[Dict[str, Any]] = None
                            ) -> PlannedAction:
        """
            Helper used by plan() implementations to build a PlannedAction.

            :param intent: PlannedActionIntent.
            :param resource_kind: Kind string.
            :param resource_name: Resource name.
            :param diff: Optional diff payload.

            :returns: A PlannedAction.
        """
        rtnval = PlannedAction(intent=intent, resource_kind=resource_kind,
                               resource_name=resource_name, diff=diff)
        return rtnval

    @classmethod
    def _destroy_order(cls, *,
                       plan: ProvisioningPlan) -> List[PlannedAction]:
        """
            Return the actions in reverse dependency order for destroy.

            Uses the static _KIND_ORDER weighting and reverses it; ties are
            broken alphabetically on resource_name (stable, reversed).

            :param plan: The ProvisioningPlan to reverse.

            :returns: A new list of PlannedAction in destroy order.
        """
        def _weight(action: PlannedAction) -> int:
            rtnval = _KIND_ORDER.get(action.resource_kind, 1000)
            return rtnval

        sorted_forward = sorted(
            plan.actions,
            key=lambda a: (_weight(a), a.resource_name),
        )
        rtnval = list(reversed(sorted_forward))
        return rtnval

    @classmethod
    def _read_by_tag_contract(cls) -> Dict[str, str]:
        """
            Contract documentation for subclass `_read_<kind>_by_tag` helpers.

            Subclasses must look up resources by the owner-tag pair, never by
            name alone — venue name collisions are common and the tag pair
            is the only stable ownership signal.

            :returns: Dict {OWNER_TAG_KEY: OWNER_TAG_VALUE}.
        """
        rtnval = {cls.OWNER_TAG_KEY: cls.OWNER_TAG_VALUE}
        return rtnval

    @staticmethod
    def _aspect_attr(*, aspects: Any, name: str, default: Any) -> Any:
        """
            Read a named attribute from an aspects object or dict.

            Tolerates None aspects and dict-shaped aspects so callers can
            pass either an Aspects subclass or a small dict during tests.

            :param aspects: Aspects object or dict.
            :param name: Attribute name.
            :param default: Default if missing.

            :returns: The attribute value or default.
        """
        if aspects is None:
            rtnval = default
            return rtnval
        if isinstance(aspects, dict):
            rtnval = aspects.get(name, default)
            return rtnval
        rtnval = getattr(aspects, name, default)
        return rtnval
