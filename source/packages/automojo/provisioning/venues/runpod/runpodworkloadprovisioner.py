"""
    .. module:: runpodworkloadprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RunpodWorkloadProvisioner — concrete WorkloadProvisioner for
        the container-shaped RunPod GPU-cloud venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import json
import os

from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from automojo.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from automojo.provisioning.model.cloud.validationresult import ValidationResult
from automojo.provisioning.model.workload.workloadprovisioner import (
    WorkloadProvisioner
)
from automojo.provisioning.model.workload.workloadvenue import WorkloadVenue

from automojo.provisioning.venues.runpod.rpapplystages import RpApplyStages
from automojo.provisioning.venues.runpod.rpcontainerstartrenderer import (
    RpContainerStartRenderer
)
from automojo.provisioning.venues.runpod.rpdestroystages import RpDestroyStages
from automojo.provisioning.venues.runpod.rperrors import (
    ConfirmationRequiredError, RpCapacityError, RpValidationError
)
from automojo.provisioning.venues.runpod.rpinventory import RpInventory
from automojo.provisioning.venues.runpod.rpnaming import pod_name
from automojo.provisioning.venues.runpod.rpplanbuilder import RpPlanBuilder
from automojo.provisioning.venues.runpod.rpresolver import RpResolver
from automojo.provisioning.venues.runpod.rpsidecartag import RpSidecarTag
from automojo.provisioning.venues.runpod.runpodworkloadspec import (
    RUNPOD_TIER_COMMUNITY, RUNPOD_TIER_SECURE
)


class RunpodWorkloadProvisioner(WorkloadProvisioner):
    """
        Concrete :class:`WorkloadProvisioner` for the RunPod GPU cloud.

        RunPod is **container-shaped**, not VM-shaped — it is a
        :class:`WorkloadProvisioner`, not a CloudProvisioner. The API surface
        is Pods, Pod Templates, GPU Types, and Network Volumes; there is no
        VPC, subnet, security group, load balancer, or DNS. Every
        :class:`WorkloadJob` / :class:`WorkloadService` becomes a RunPod pod
        bound to a GPU type and a container image.

        The five-verb lifecycle (``validate / plan / apply / destroy /
        inventory``) is honest about RunPod's shape: object-storage,
        load-balancer, DNS, and inter-pod-interconnect requests are rejected
        at validate-time; network / subnet / security-group / key-pair
        requests are warned about because RunPod realises none of them. A
        VPN-joined pod gets a userspace-mode Tailscale bring-up block
        rendered into its container start command, since RunPod containers
        run without ``NET_ADMIN`` and without a TUN device.
    """

    VENUE_NAME: str = "runpod"

    def __init__(self, *, venue: WorkloadVenue, runpod_client: Any,
                 spec: Any,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a :class:`RunpodWorkloadProvisioner`.

            :param venue: The :class:`WorkloadVenue` this provisioner targets.
            :param runpod_client: The RunPod interop client (a
                ``RunpodClient`` or a test mock exposing the same surface).
            :param spec: The :class:`RunpodWorkloadSpec` resource bundle.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` used to
                mint VPN auth keys and de-register devices on destroy.

            :returns: ``None``.
        """
        super().__init__(venue=venue, cloud_provisioner=None)

        self._runpod_client = runpod_client
        self._spec = spec
        self._vpn_control_plane = vpn_control_plane

        self._resolver = RpResolver()
        self._renderer = RpContainerStartRenderer()
        self._plan_builder = RpPlanBuilder(resolver=self._resolver)
        self._apply_stages = RpApplyStages(resolver=self._resolver,
                                           renderer=self._renderer)
        self._destroy_stages = RpDestroyStages()
        self._inventory = RpInventory()
        self._registered_vpn_devices: List[str] = []
        return

    @property
    def spec(self) -> Any:
        """
            The :class:`RunpodWorkloadSpec` resource bundle.

            :returns: The spec bundle.
        """
        rtnval = self._spec
        return rtnval

    # ------------------------------------------------------------------
    # validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any = None) -> ValidationResult:
        """
            Run shape + semantic validation across the declared workload
            resources.

            :param aspects: Behaviour control. ``None`` is accepted.

            :returns: A :class:`ValidationResult` carrying warnings for the
                unrealised network resources.

            :raises: :class:`RpValidationError` on an object-storage,
                load-balancer, DNS, or non-NONE interconnect request;
                :class:`RpCapacityError` when a Secure Cloud GPU type has no
                Secure Cloud capacity.
        """
        spec = self._spec

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        # Hard rejections — RunPod has no API surface for these.
        if len(spec.buckets) > 0:
            err_msg_lines = ["RunPod has no object-storage API."]
            err_msg_lines.append("CloudObjectBucket is not realisable on "
                                 "RunPod.")
            raise RpValidationError(os.linesep.join(err_msg_lines))

        if len(spec.load_balancers) > 0:
            err_msg_lines = ["RunPod has no load-balancer API."]
            err_msg_lines.append("CloudLoadBalancer is not realisable on "
                                 "RunPod.")
            raise RpValidationError(os.linesep.join(err_msg_lines))

        if len(spec.dns_records) > 0:
            err_msg_lines = ["RunPod has no DNS API."]
            err_msg_lines.append("CloudDnsRecord is not realisable on "
                                 "RunPod.")
            raise RpValidationError(os.linesep.join(err_msg_lines))

        for interconnect in spec.interconnects:
            kind = getattr(interconnect, "kind", "NONE")
            topology = getattr(interconnect, "topology", "NONE")
            if kind != "NONE" or topology != "NONE":
                err_msg_lines = ["RunPod offers no inter-pod interconnect "
                                 "fabric."]
                err_msg_lines.append("INTERCONNECT KIND: {}".format(kind))
                raise RpValidationError(os.linesep.join(err_msg_lines))

        # Soft warnings — RunPod exposes none of these.
        for label, items in (("CloudNetwork", spec.networks),
                              ("CloudSubnet", spec.subnets),
                              ("CloudSecurityGroup", spec.security_groups),
                              ("CloudKeyPair", spec.key_pairs)):
            if len(items) > 0:
                warnings.append({
                    "resource": label,
                    "message": ("RunPod exposes no {} concept; the request "
                                "is ignored.").format(label),
                })

        # Every accelerator-bearing workload must resolve to a GPU type.
        all_workloads = list(spec.jobs) + list(spec.services)
        for workload in all_workloads:
            # gpu_type_for_workload raises RpValidationError when the model
            # has no RunPod mapping.
            self._resolver.gpu_type_for_workload(workload=workload)

        # Secure Cloud capacity probe for every requested GPU type.
        if spec.tier == RUNPOD_TIER_SECURE:
            self._probe_secure_capacity(workloads=all_workloads)

        ok = len(errors) == 0
        rtnval = ValidationResult(ok=ok, errors=errors, warnings=warnings)
        return rtnval

    def _probe_secure_capacity(self, *, workloads: List[Any]) -> None:
        """
            Verify Secure Cloud capacity exists for every workload GPU type.

            :param workloads: The declared workloads.

            :returns: ``None``.

            :raises: :class:`RpCapacityError` when a GPU type has no Secure
                Cloud capacity in the requested data center.
        """
        gpu_types = self._runpod_client.list_gpu_types()
        catalog: Dict[str, Any] = {}
        for gpu_type in gpu_types:
            catalog[gpu_type.gpu_type_id] = gpu_type

        data_center = self._spec.data_center_id

        for workload in workloads:
            gpu_type_id = self._resolver.gpu_type_for_workload(
                workload=workload)
            if gpu_type_id is None:
                continue

            entry = catalog.get(gpu_type_id)
            if entry is None:
                err_msg_lines = ["The requested GPU type is not offered by "
                                 "RunPod."]
                err_msg_lines.append("GPU TYPE: {}".format(gpu_type_id))
                raise RpCapacityError(os.linesep.join(err_msg_lines))

            secure_dcs = getattr(entry, "secure_data_centers", [])
            if len(secure_dcs) == 0 or data_center not in secure_dcs:
                err_msg_lines = ["No Secure Cloud capacity is available for "
                                 "the requested GPU type and region."]
                err_msg_lines.append("GPU TYPE: {}".format(gpu_type_id))
                err_msg_lines.append("DATA CENTER: {}".format(data_center))
                err_msg_lines.append("Consider tier='community'.")
                raise RpCapacityError(os.linesep.join(err_msg_lines))

        return

    # ------------------------------------------------------------------
    # plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any = None) -> ProvisioningPlan:
        """
            Produce a :class:`ProvisioningPlan` for the declared resources.

            Pods and Network Volumes are listed by the run-id name prefix and
            diffed. Re-planning an already-applied spec yields only SKIPs.

            :param aspects: Behaviour control. ``None`` is accepted.

            :returns: A :class:`ProvisioningPlan`.
        """
        rtnval = self._plan_builder.plan(spec=self._spec,
                                         client=self._runpod_client)
        return rtnval

    # ------------------------------------------------------------------
    # apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any = None) -> ProvisioningResult:
        """
            Apply the declared resources to RunPod.

            Network Volumes are ensured first, then a RunPod pod is launched
            for every workload not already realised. When every planned
            action is SKIP no mutating call is made. A pod carrying a
            :class:`VPNJoinSpec` gets a userspace-Tailscale start script.

            :param aspects: Behaviour control. ``aspects.confirm`` must be
                ``True`` when the plan carries a DELETE / UPDATE action.

            :returns: A :class:`ProvisioningResult`.

            :raises: :class:`ConfirmationRequiredError` when a destructive
                action is planned and confirmation is withheld.
        """
        spec = self._spec

        plan = self.plan(aspects=aspects)
        if self._plan_is_all_skip(plan=plan):
            skipped_names = [action.resource_name for action in plan.actions]
            rtnval = ProvisioningResult(created=[], skipped=skipped_names)
            return rtnval

        confirm = getattr(aspects, "confirm", False)
        if confirm is False and self._plan_has_destructive(plan=plan):
            err_msg_lines = ["The RunPod apply carries a recreate / delete "
                             "action."]
            err_msg_lines.append("Set aspects.confirm=True to proceed.")
            raise ConfirmationRequiredError(os.linesep.join(err_msg_lines))

        existing_pods = self._index_pods()

        # UPDATE-by-recreate: terminate the drifted pods so apply_pods
        # re-launches them with the desired shape.
        for action in plan.actions:
            if action.intent == PlannedActionIntent.UPDATE.value:
                self._terminate_pod_by_name(name=action.resource_name,
                                            existing_pods=existing_pods)
                existing_pods.pop(action.resource_name, None)

        volume_ids = self._apply_stages.ensure_network_volumes(
            spec=spec, client=self._runpod_client)

        authkeys = self._mint_vpn_authkeys(aspects=aspects)

        created = self._apply_stages.apply_pods(
            spec=spec, client=self._runpod_client, volume_ids=volume_ids,
            existing_pods=existing_pods, authkeys=authkeys)

        self._record_vpn_devices(resources=created)

        self._persist_tags(resources=created)

        rtnval = ProvisioningResult(created=created)
        return rtnval

    def _plan_is_all_skip(self, *, plan: ProvisioningPlan) -> bool:
        """
            Report whether every action in a plan is a SKIP.

            :param plan: The :class:`ProvisioningPlan`.

            :returns: ``True`` when every action is SKIP.
        """
        for action in plan.actions:
            if action.intent != PlannedActionIntent.SKIP.value:
                rtnval = False
                return rtnval

        rtnval = True
        return rtnval

    def _plan_has_destructive(self, *, plan: ProvisioningPlan) -> bool:
        """
            Report whether a plan carries a DELETE or UPDATE action.

            :param plan: The :class:`ProvisioningPlan`.

            :returns: ``True`` when a destructive action is present.
        """
        destructive = (PlannedActionIntent.DELETE.value,
                       PlannedActionIntent.UPDATE.value)
        for action in plan.actions:
            if action.intent in destructive:
                rtnval = True
                return rtnval

        rtnval = False
        return rtnval

    def _terminate_pod_by_name(self, *, name: str,
                               existing_pods: Dict[str, Any]) -> None:
        """
            Terminate a live pod identified by its composed name.

            :param name: The composed pod name.
            :param existing_pods: The name-keyed pod index.

            :returns: ``None``.
        """
        pod = existing_pods.get(name)
        if pod is None:
            return

        self._runpod_client.terminate_pod(pod_id=pod.pod_id)
        return

    def _mint_vpn_authkeys(self, *, aspects: Any) -> Dict[str, str]:
        """
            Mint an ephemeral Tailscale auth key for every VPN-joined
            workload.

            :param aspects: Behaviour control propagated into the mint call.

            :returns: A ``workload-name -> auth-key`` map.
        """
        rtnval: Dict[str, str] = {}
        if self._vpn_control_plane is None:
            return rtnval

        for workload_name, vpn_join in self._spec.vpn_joins.items():
            tags = list(getattr(vpn_join, "advertise_tags", []))
            authkey = self._vpn_control_plane.mint_authkey(
                reusable=False,
                ephemeral=getattr(vpn_join, "ephemeral", True),
                tags=tags, ttl_seconds=3600, aspects=aspects)
            rtnval[workload_name] = authkey

        return rtnval

    def _record_vpn_devices(self, *,
                            resources: List[ProvisionedResource]) -> None:
        """
            Record the Tailscale device identifier of every VPN-joined pod
            that ``apply`` realised so ``destroy`` can de-register them.

            A RunPod pod joins the tailnet under a hostname equal to its
            composed pod name, which is the device identifier the VPN
            control plane de-registers.

            :param resources: The :class:`ProvisionedResource` records the
                apply stage realised.

            :returns: ``None``.
        """
        if self._vpn_control_plane is None:
            return

        run_short = self._spec.run_id_short
        realised_names: Dict[str, bool] = {}
        for resource in resources:
            if resource.kind == "Pod":
                realised_names[resource.name] = True

        for workload_name in self._spec.vpn_joins.keys():
            device_id = pod_name(workload_name=workload_name,
                                 run_id_short=run_short)
            if device_id not in realised_names:
                continue
            if device_id not in self._registered_vpn_devices:
                self._registered_vpn_devices.append(device_id)

        return

    @property
    def registered_vpn_devices(self) -> List[str]:
        """
            The Tailscale device identifiers recorded by the last apply.

            :returns: A defensive copy of the recorded device id list.
        """
        rtnval = list(self._registered_vpn_devices)
        return rtnval

    # ------------------------------------------------------------------
    # destroy
    # ------------------------------------------------------------------

    def destroy(self, *, aspects: Any = None) -> None:
        """
            Destroy previously-applied resources.

            Pods owned by the run are stopped and terminated, VPN devices are
            de-registered, then the run's Network Volumes are deleted.

            :param aspects: Behaviour control. ``aspects.confirm`` must be
                ``True``.

            :returns: ``None``.

            :raises: :class:`ConfirmationRequiredError` when confirmation is
                withheld.
        """
        confirm = getattr(aspects, "confirm", False)
        if confirm is False:
            err_msg_lines = ["The RunPod destroy requires confirmation."]
            err_msg_lines.append("Set aspects.confirm=True to proceed.")
            raise ConfirmationRequiredError(os.linesep.join(err_msg_lines))

        self._destroy_stages.destroy(
            spec=self._spec, client=self._runpod_client,
            vpn_control_plane=self._vpn_control_plane,
            vpn_device_ids=self._registered_vpn_devices, aspects=aspects)
        return

    # ------------------------------------------------------------------
    # inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any = None) -> List[ProvisionedResource]:
        """
            Enumerate the RunPod Pods and Volumes belonging to this run.

            :param aspects: Behaviour control. ``None`` is accepted.

            :returns: A list of :class:`ProvisionedResource` records.
        """
        resources = self._inventory.list_run(spec=self._spec,
                                              client=self._runpod_client)
        self._persist_inventory(resources=resources)

        rtnval = resources
        return rtnval

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _index_pods(self) -> Dict[str, Any]:
        """
            Build a name-keyed index of the live RunPod pods.

            :returns: A dictionary mapping pod name to pod record.
        """
        rtnval: Dict[str, Any] = {}
        for pod in self._runpod_client.list_pods():
            rtnval[pod.name] = pod
        return rtnval

    def _persist_tags(self, *,
                      resources: List[ProvisionedResource]) -> None:
        """
            Persist the neutral tag list keyed by pod id under
            ``.output/provisioning/<runid>/runpod-tags.json``.

            :param resources: The realised :class:`ProvisionedResource`
                records.

            :returns: ``None``.
        """
        try:
            sidecar = RpSidecarTag(runid=self._spec.run_id)
            for resource in resources:
                if resource.kind != "Pod":
                    continue
                sidecar.write(neutral_tags=self._spec.tags,
                              pod_id=resource.venue_id)
        except OSError:
            # Tag persistence is best-effort; the apply result is the
            # authoritative return value.
            pass

        return

    def _persist_inventory(self, *,
                           resources: List[ProvisionedResource]) -> None:
        """
            Persist the inventory snapshot under
            ``.output/provisioning/<runid>/runpod-inventory.json``.

            :param resources: The :class:`ProvisionedResource` records.

            :returns: ``None``.
        """
        try:
            output_dir = os.path.join(".output", "provisioning",
                                      self._spec.run_id)
            os.makedirs(output_dir, exist_ok=True)

            payload = []
            for resource in resources:
                payload.append({
                    "kind": resource.kind,
                    "name": resource.name,
                    "venue_id": resource.venue_id,
                    "attributes": resource.attributes,
                    "tags": resource.tags,
                })

            output_path = os.path.join(output_dir, "runpod-inventory.json")
            with open(output_path, "w", encoding="utf-8") as output_handle:
                json.dump(payload, output_handle, indent=2, sort_keys=True)
        except OSError:
            # Inventory persistence is best-effort.
            pass

        return


__all__ = ["RunpodWorkloadProvisioner"]
