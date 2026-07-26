"""
    .. module:: provisioningengine
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Eight-stage provisioning pipeline driver.

    The engine drives the same five-verb lifecycle (validate / plan / apply /
    destroy / inventory) over every registered CloudProvisioner in a fixed
    stage order:

        1. LOAD_VALIDATE
        2. PLAN
        3. APPLY_NETWORKING
        4. APPLY_COMPUTE
        5. APPLY_DNS_AND_STORAGE_AND_LB
        6. BOOTSTRAP_VPN
        7. VERIFY
        8. EMIT_LANDSCAPE_INVENTORY

    Within a stage, the engine respects the resource dependency graph's
    topological sort (Kahn's algorithm, stable tiebreaker).  Cycles raise
    SchemaSemanticError listing the offending nodes.

    Dry-run halts at the end of PLAN and returns a MultiVenueProvisioningPlan.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import datetime
import logging
import os
import uuid

from typing import Any, Dict, List, Optional, Tuple

import yaml

from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.interfaces.schemavalidationerror import SchemaValidationError
from ccai.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from ccai.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.cloudprovisionerregistry import (
    CloudProvisionerRegistry
)
from ccai.provisioning.dependencygraph import (
    build_dependency_graph, DependencyGraph
)
from ccai.provisioning.pipelineplan import (
    PipelinePlan, MultiVenueProvisioningPlan
)
from ccai.provisioning.pipelinestage import PipelineStage
from ccai.provisioning.provisioningverifyerror import (
    ProvisioningVerifyError
)
from ccai.provisioning.state.provisioningstatestore import (
    ProvisioningStateStore
)
from ccai.provisioning.state.runstate import RunState
from ccai.provisioning.state.runstatus import RunStatus
from ccai.provisioning.landscape.landscapeemitter import LandscapeEmitter
from ccai.provisioning.preemption.preemptionhandler import (
    handle_preemption
)


logger = logging.getLogger(__name__)


class ProvisioningEngine:
    """
        Eight-stage venue-agnostic provisioning pipeline driver.

        The engine owns no venue-specific knowledge; venues land in M7+
        through CloudProvisionerRegistry registrations made by callers.
    """

    def __init__(self, *, spec: Dict[str, Any],
                 registry: CloudProvisionerRegistry,
                 runid: Optional[str] = None,
                 state_store: Optional[ProvisioningStateStore] = None,
                 control_planes: Optional[Dict[str, Any]] = None) -> None:
        """
            Construct a ProvisioningEngine.

            :param spec: Normalised spec dict.
            :param registry: CloudProvisionerRegistry of venue provisioners.
            :param runid: Optional run identifier (UUID4 minted if missing).
            :param state_store: Optional ProvisioningStateStore for
                                persistence; the engine omits persistence
                                when None.
            :param control_planes: Optional VPN control-plane registry.
        """
        if spec is None:
            raise SchemaValidationError("spec must not be None.")
        if registry is None or len(registry) == 0:
            raise SchemaValidationError(
                "registry must contain at least one provisioner."
            )

        self._spec: Dict[str, Any] = spec
        self._registry: CloudProvisionerRegistry = registry
        self._runid: str = runid if runid is not None else str(uuid.uuid4())
        self._state_store: Optional[ProvisioningStateStore] = state_store
        self._control_planes: Dict[str, Any] = (
            control_planes if control_planes is not None else {}
        )

        self._dependency_graph: DependencyGraph = build_dependency_graph(
            spec=spec
        )
        self._topo_order: List[Tuple[str, str]] = (
            self._dependency_graph.topological_sort()
        )

        self._results: Dict[str, ProvisioningResult] = {}
        self._inventory: Dict[str, List[ProvisionedResource]] = {}
        self._plan: Optional[PipelinePlan] = None
        self._landscape: Optional[Dict[str, Any]] = None

        return

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def runid(self) -> str:
        """
            Return the run identifier.

            :returns: The runid string.
        """
        rtnval = self._runid
        return rtnval

    @property
    def topological_order(self) -> List[Tuple[str, str]]:
        """
            Return the cached topological order.

            :returns: List of (kind, name).
        """
        rtnval = self._topo_order
        return rtnval

    @property
    def dependency_graph(self) -> DependencyGraph:
        """
            Return the cached DependencyGraph.

            :returns: The DependencyGraph.
        """
        rtnval = self._dependency_graph
        return rtnval

    @property
    def landscape(self) -> Optional[Dict[str, Any]]:
        """
            Return the last-emitted landscape dict, if any.

            :returns: Landscape dict or None.
        """
        rtnval = self._landscape
        return rtnval

    # ------------------------------------------------------------------
    # Public verbs
    # ------------------------------------------------------------------

    @classmethod
    def from_spec_file(cls, *, path: str,
                       registry: CloudProvisionerRegistry,
                       runid: Optional[str] = None,
                       state_store: Optional[ProvisioningStateStore] = None,
                       control_planes: Optional[Dict[str, Any]] = None
                       ) -> "ProvisioningEngine":
        """
            Construct an engine from a YAML spec file.

            :param path: Path to the YAML spec.
            :param registry: A populated CloudProvisionerRegistry.
            :param runid: Optional runid override.
            :param state_store: Optional state store.
            :param control_planes: Optional VPN control planes.

            :returns: A configured ProvisioningEngine.
        """
        with open(path, "r") as fh:
            data = yaml.safe_load(fh)
        rtnval = cls(spec=data, registry=registry, runid=runid,
                     state_store=state_store,
                     control_planes=control_planes)
        return rtnval

    def validate(self, *, aspects: ProvisioningAspects) -> None:
        """
            Run the LOAD_VALIDATE stage against every venue.

            :param aspects: ProvisioningAspects.
            :raises: SchemaSemanticError
        """
        self._log_stage(stage=PipelineStage.LOAD_VALIDATE, event="enter")
        for venue_name, provisioner in self._registry.items():
            provisioner.validate(aspects=aspects)
        self._log_stage(stage=PipelineStage.LOAD_VALIDATE, event="exit")
        return

    def plan(self, *,
             aspects: ProvisioningAspects) -> MultiVenueProvisioningPlan:
        """
            Run LOAD_VALIDATE then PLAN and return the aggregate plan.

            When ``aspects.dry_run`` is True the engine halts here (the
            apply/bootstrap/verify/emit stages are skipped).

            :param aspects: ProvisioningAspects.

            :returns: A MultiVenueProvisioningPlan.
        """
        self.validate(aspects=aspects)

        self._log_stage(stage=PipelineStage.PLAN, event="enter")
        per_venue: Dict[str, ProvisioningPlan] = {}
        for venue_name, provisioner in self._registry.items():
            per_venue[venue_name] = provisioner.plan(aspects=aspects)

        self._plan = PipelinePlan(per_venue_plans=per_venue,
                                  topological_order=self._topo_order)
        self._log_stage(stage=PipelineStage.PLAN, event="exit")

        rtnval = self._plan
        return rtnval

    def apply(self, *,
              aspects: ProvisioningAspects) -> Dict[str, ProvisioningResult]:
        """
            Run the full pipeline.

            Honours ``aspects.dry_run`` by stopping after PLAN.

            :param aspects: ProvisioningAspects.

            :returns: Per-venue ProvisioningResult map.
        """
        # Populate self._plan; the returned plan is consumed via self._plan.
        self.plan(aspects=aspects)

        if aspects.dry_run is True:
            rtnval: Dict[str, ProvisioningResult] = {}
            return rtnval

        if self._state_store is not None:
            self._state_store.create_run(runid=self._runid,
                                         venues=self._registry.names())
            # Seed the runid onto the aspects so a destroy issued with the
            # same aspects object after this apply (a state store is wired)
            # can locate the persisted inventory instead of raising.
            if aspects.runid is None:
                aspects.runid = self._runid

        self._stage_apply_networking(aspects=aspects)
        self._stage_apply_compute(aspects=aspects)
        self._stage_apply_dns_storage_lb(aspects=aspects)
        self._stage_bootstrap_vpn(aspects=aspects)
        self._stage_verify(aspects=aspects)
        self._stage_emit_landscape_inventory(aspects=aspects)

        if self._state_store is not None:
            self._persist_state()
            self._state_store.mark_finished(runid=self._runid,
                                            status=RunStatus.APPLIED)

        rtnval = self._results
        return rtnval

    def destroy(self, *, aspects: ProvisioningAspects) -> None:
        """
            Tear down every venue in reverse registration order.

            Requires ``aspects.confirm = True``.  When ``aspects.runid`` is
            set, the inventory is loaded from the persisted state store
            before dispatching to each provisioner's destroy.

            :param aspects: ProvisioningAspects.
            :raises: SchemaSemanticError
        """
        if aspects.confirm is not True:
            raise SchemaSemanticError(
                "ProvisioningEngine.destroy requires aspects.confirm=True."
            )

        if aspects.runid is None and self._state_store is not None:
            raise SchemaSemanticError(
                "ProvisioningEngine.destroy requires aspects.runid when "
                "a state store is configured."
            )

        for venue_name, provisioner in reversed(self._registry.items()):
            provisioner.destroy(aspects=aspects)

        if self._state_store is not None and aspects.runid is not None:
            self._state_store.mark_destroyed(runid=aspects.runid)

        return

    def inventory(self, *, aspects: ProvisioningAspects
                  ) -> Dict[str, List[ProvisionedResource]]:
        """
            Collect inventories from every venue.

            :param aspects: ProvisioningAspects.

            :returns: Per-venue inventory map.
        """
        rtnval: Dict[str, List[ProvisionedResource]] = {}
        for venue_name, provisioner in self._registry.items():
            rtnval[venue_name] = provisioner.inventory(aspects=aspects)
        self._inventory = rtnval
        return rtnval

    # ------------------------------------------------------------------
    # Stage bodies
    # ------------------------------------------------------------------

    _NETWORKING_KINDS = ("network", "subnet", "sg", "security_group",
                         "keypair")
    _COMPUTE_KINDS = ("instance", "volume", "volume_attachment",
                      "shared_filesystem")
    _DNS_STORAGE_LB_KINDS = ("dns", "dns_record", "bucket", "lb",
                             "load_balancer")

    def _stage_apply_networking(self, *,
                                aspects: ProvisioningAspects) -> None:
        """
            APPLY_NETWORKING stage.

            :param aspects: ProvisioningAspects.
        """
        self._log_stage(stage=PipelineStage.APPLY_NETWORKING, event="enter")
        for venue_name, provisioner in self._registry.items():
            result = provisioner.apply_subset(
                kinds=list(self._NETWORKING_KINDS),
                aspects=aspects,
            )
            self._merge_result(venue=venue_name, partial=result)
        self._log_stage(stage=PipelineStage.APPLY_NETWORKING, event="exit")
        return

    def _stage_apply_compute(self, *,
                             aspects: ProvisioningAspects) -> None:
        """
            APPLY_COMPUTE stage.

            :param aspects: ProvisioningAspects.
        """
        self._log_stage(stage=PipelineStage.APPLY_COMPUTE, event="enter")
        for venue_name, provisioner in self._registry.items():
            result = provisioner.apply_subset(
                kinds=list(self._COMPUTE_KINDS),
                aspects=aspects,
            )
            result = self._handle_apply_preemptions(
                venue_name=venue_name, provisioner=provisioner,
                result=result, aspects=aspects,
            )
            self._merge_result(venue=venue_name, partial=result)
        self._log_stage(stage=PipelineStage.APPLY_COMPUTE, event="exit")
        return

    def _stage_apply_dns_storage_lb(self, *,
                                    aspects: ProvisioningAspects) -> None:
        """
            APPLY_DNS_AND_STORAGE_AND_LB stage.

            :param aspects: ProvisioningAspects.
        """
        self._log_stage(
            stage=PipelineStage.APPLY_DNS_AND_STORAGE_AND_LB,
            event="enter",
        )
        for venue_name, provisioner in self._registry.items():
            result = provisioner.apply_subset(
                kinds=list(self._DNS_STORAGE_LB_KINDS),
                aspects=aspects,
            )
            self._merge_result(venue=venue_name, partial=result)
        self._log_stage(
            stage=PipelineStage.APPLY_DNS_AND_STORAGE_AND_LB,
            event="exit",
        )
        return

    def _stage_bootstrap_vpn(self, *,
                             aspects: ProvisioningAspects) -> None:
        """
            BOOTSTRAP_VPN stage — cloud-init was injected at instance create
            time; this stage exists for verify-only re-checks.

            :param aspects: ProvisioningAspects.
        """
        self._log_stage(stage=PipelineStage.BOOTSTRAP_VPN, event="enter")
        # No-op in the engine itself.  Venue subclasses inject cloud-init at
        # create time via the cloudinit renderer; this hook is here so
        # subclasses or callers may extend.
        self._log_stage(stage=PipelineStage.BOOTSTRAP_VPN, event="exit")
        return

    def _stage_verify(self, *, aspects: ProvisioningAspects) -> None:
        """
            VERIFY stage — collect inventory and check that every created
            instance is present.

            :param aspects: ProvisioningAspects.
            :raises: ProvisioningVerifyError
        """
        self._log_stage(stage=PipelineStage.VERIFY, event="enter")
        self.inventory(aspects=aspects)

        missing: List[str] = []
        for venue_name, result in self._results.items():
            provisioner = self._registry.get(name=venue_name)
            inv = {r.name for r in self._inventory.get(venue_name, [])}
            for created in result.created:
                if created.name in inv:
                    continue
                if created.kind != "instance":
                    missing.append("{}/{}".format(venue_name, created.name))
                    continue
                # An instance present in `created` but absent from a fresh
                # inventory was terminated mid-poll: a venue-signalled
                # preemption.  Dispatch the policy handler; a FAIL policy
                # re-raises here, REACQUIRE / BEST_EFFORT recover quietly.
                replacement = self._dispatch_preemption(
                    venue_name=venue_name, provisioner=provisioner,
                    instance_name=created.name, venue_id=created.venue_id,
                    stage="verify", aspects=aspects,
                    reason="instance terminated mid-poll during VERIFY",
                )
                if replacement is None:
                    # BEST_EFFORT dropped the instance; it is no longer
                    # expected in inventory and is not a verify failure.
                    continue
                # REACQUIRE produced a replacement; record it and accept it.
                self._absorb_replacement(venue_name=venue_name,
                                         original_name=created.name,
                                         replacement=replacement)

        if len(missing) > 0:
            err_msg_lines = ["VERIFY found instances missing from inventory."]
            err_msg_lines.append("MISSING:")
            for entry in missing:
                err_msg_lines.append("    {}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise ProvisioningVerifyError(err_msg)

        self._log_stage(stage=PipelineStage.VERIFY, event="exit")
        return

    def _stage_emit_landscape_inventory(self, *,
                                        aspects: ProvisioningAspects
                                        ) -> None:
        """
            EMIT_LANDSCAPE_INVENTORY stage.

            :param aspects: ProvisioningAspects.
        """
        self._log_stage(
            stage=PipelineStage.EMIT_LANDSCAPE_INVENTORY,
            event="enter",
        )
        emitter = LandscapeEmitter(spec=self._spec,
                                   inventory=self._inventory,
                                   control_planes=self._control_planes)
        self._landscape = emitter.emit(aspects=aspects)

        if self._state_store is not None:
            self._state_store.write_landscape(runid=self._runid,
                                              landscape=self._landscape)

        self._log_stage(
            stage=PipelineStage.EMIT_LANDSCAPE_INVENTORY,
            event="exit",
        )
        return

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _merge_result(self, *, venue: str,
                      partial: ProvisioningResult) -> None:
        """
            Merge a stage's per-venue partial result into the running map.

            :param venue: Venue name.
            :param partial: Stage partial result.
        """
        prior = self._results.get(venue, None)
        if prior is None:
            self._results[venue] = ProvisioningResult(
                created=list(partial.created),
                updated=list(partial.updated),
                skipped=list(partial.skipped),
                errors=list(partial.errors),
            )
            return

        merged_created = list(prior.created) + list(partial.created)
        merged_updated = list(prior.updated) + list(partial.updated)
        merged_skipped = list(prior.skipped) + list(partial.skipped)
        merged_errors = list(prior.errors) + list(partial.errors)
        self._results[venue] = ProvisioningResult(
            created=merged_created, updated=merged_updated,
            skipped=merged_skipped, errors=merged_errors,
        )
        return

    # ------------------------------------------------------------------
    # Preemption integration
    # ------------------------------------------------------------------

    def _instance_spec_for(self, *, name: str) -> Optional[CloudInstance]:
        """
            Build the CloudInstance spec for a named instance, if declared.

            The engine spec is a normalised dict; the preemption handler needs
            a typed CloudInstance (it reads ``vpn_join`` and the policy).

            :param name: Logical instance name.

            :returns: A CloudInstance, or None when the name is not declared
                      as an instance in the spec.
        """
        for entry in self._spec.get("instances", []):
            if entry.get("name", None) != name:
                continue
            if isinstance(entry, CloudInstance):
                rtnval: Optional[CloudInstance] = entry
                return rtnval
            try:
                rtnval = CloudInstance.from_dict(entry)
            except SchemaValidationError:
                # A spec entry too thin to promote (no image / size) cannot
                # drive a typed preemption decision; fall back to None so the
                # caller treats it as a plain verify miss. A SchemaSemanticError
                # is intentionally NOT caught -- it must bubble.
                rtnval = None
            return rtnval
        rtnval = None
        return rtnval

    def _dispatch_preemption(self, *, venue_name: str,
                             provisioner: CloudProvisioner,
                             instance_name: str, venue_id: str,
                             stage: str, aspects: ProvisioningAspects,
                             reason: str
                             ) -> Optional[ProvisionedResource]:
        """
            Build a PreemptionEvent and dispatch it to ``handle_preemption``.

            The instance's ``preemption_policy`` drives the branch: FAIL
            re-raises (ProvisioningPreemptionError bubbles), REACQUIRE returns
            a replacement ProvisionedResource, BEST_EFFORT returns None.

            :param venue_name: Venue the preemption was observed on.
            :param provisioner: The venue provisioner.
            :param instance_name: Logical name of the preempted instance.
            :param venue_id: Venue-side id that was reclaimed (may be empty
                             when the venue lost track of it).
            :param stage: "apply" or "verify".
            :param aspects: ProvisioningAspects.
            :param reason: Human-readable preemption reason.

            :returns: A replacement ProvisionedResource on REACQUIRE; None on
                      BEST_EFFORT.
            :raises: ProvisioningPreemptionError
        """
        spec_instance = self._instance_spec_for(name=instance_name)
        if spec_instance is None:
            err_msg_lines = [
                "VERIFY found an instance missing from inventory."
            ]
            err_msg_lines.append("MISSING:")
            err_msg_lines.append("    {}/{}".format(venue_name,
                                                    instance_name))
            err_msg = os.linesep.join(err_msg_lines)
            raise ProvisioningVerifyError(err_msg)

        effective_venue_id = venue_id if venue_id is not None and len(
            venue_id) > 0 else "unknown"

        logger.warning(
            "runid=%s venue=%s stage=%s detected preemption of instance=%s "
            "(policy=%s); dispatching handler.",
            self._runid, venue_name, stage, instance_name,
            spec_instance.preemption_policy,
        )

        replacement = handle_preemption(
            spec=spec_instance,
            policy=spec_instance.preemption_policy,
            provisioner=provisioner, stage=stage, aspects=aspects,
            venue_id=effective_venue_id, reason=reason,
        )
        rtnval = replacement
        return rtnval

    def _absorb_replacement(self, *, venue_name: str, original_name: str,
                            replacement: ProvisionedResource) -> None:
        """
            Record a REACQUIRE replacement into the running results/inventory.

            The replacement carries the same logical name but a new venue id;
            it supersedes the original entry so VERIFY and EMIT see the live
            resource.

            :param venue_name: Venue the replacement belongs to.
            :param original_name: Logical name of the superseded instance.
            :param replacement: The replacement ProvisionedResource.
        """
        prior = self._results.get(venue_name, None)
        if prior is not None:
            new_created = [
                r for r in prior.created if r.name != original_name
            ]
            new_created.append(replacement)
            self._results[venue_name] = ProvisioningResult(
                created=new_created,
                updated=list(prior.updated),
                skipped=list(prior.skipped),
                errors=list(prior.errors),
            )

        venue_inv = self._inventory.get(venue_name, None)
        if venue_inv is None:
            self._inventory[venue_name] = [replacement]
            return
        refreshed = [r for r in venue_inv if r.name != original_name]
        refreshed.append(replacement)
        self._inventory[venue_name] = refreshed
        return

    def _handle_apply_preemptions(self, *, venue_name: str,
                                  provisioner: CloudProvisioner,
                                  result: ProvisioningResult,
                                  aspects: ProvisioningAspects
                                  ) -> ProvisioningResult:
        """
            Inspect an apply-stage result for venue-signalled preemptions.

            A venue signals a preemption noticed during apply's match-then-act
            with an error entry whose ``kind`` is ``"preemption"`` (carrying
            the reclaimed ``resource`` name and, when known, its ``venue_id``).
            Each is dispatched to ``handle_preemption``; a FAIL policy
            re-raises, REACQUIRE swaps in the replacement, BEST_EFFORT drops
            the entry.

            :param venue_name: Venue the result came from.
            :param provisioner: The venue provisioner.
            :param result: The apply-stage ProvisioningResult.
            :param aspects: ProvisioningAspects.

            :returns: The result with any REACQUIRE / BEST_EFFORT fix-ups
                      applied.
            :raises: ProvisioningPreemptionError
        """
        preempted: List[Dict[str, str]] = []

        for err in result.errors:
            if not isinstance(err, dict):
                continue
            if err.get("kind", None) != "preemption":
                continue
            preempted.append({
                "name": err.get("resource", ""),
                "venue_id": err.get("venue_id", ""),
            })

        if len(preempted) == 0:
            rtnval = result
            return rtnval

        created = list(result.created)
        for entry in preempted:
            inst_name = entry["name"]
            replacement = self._dispatch_preemption(
                venue_name=venue_name, provisioner=provisioner,
                instance_name=inst_name, venue_id=entry["venue_id"],
                stage="apply", aspects=aspects,
                reason="venue reported instance preempted during APPLY",
            )
            created = [r for r in created if r.name != inst_name]
            if replacement is not None:
                created.append(replacement)

        kept_errors = [
            e for e in result.errors
            if not (isinstance(e, dict)
                    and e.get("kind", None) == "preemption")
        ]
        rtnval = ProvisioningResult(
            created=created, updated=list(result.updated),
            skipped=list(result.skipped), errors=kept_errors,
        )
        return rtnval

    def _log_stage(self, *, stage: PipelineStage, event: str) -> None:
        """
            Log a stage entry/exit transition.

            :param stage: The PipelineStage.
            :param event: "enter" or "exit".
        """
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        line = "{} runid={} stage={} event={}".format(
            ts, self._runid, stage.value, event,
        )
        logger.info(line)
        if self._state_store is not None:
            try:
                self._state_store.append_log(runid=self._runid, line=line)
            except OSError:
                # A filesystem error appending the stage log must never break
                # the pipeline; we already log via the module logger.
                logger.warning("Failed to append stage log line.")
        return

    def _persist_state(self) -> None:
        """
            Write the current state to the store.
        """
        if self._state_store is None:
            return
        plan_dict: Dict[str, Any] = {}
        if self._plan is not None:
            plan_dict = self._plan.to_dict()

        state = RunState(
            runid=self._runid,
            spec=self._spec,
            plan=plan_dict,
            results=self._results,
            inventory=self._inventory,
        )
        self._state_store.write_state(runid=self._runid, state=state)
        return
