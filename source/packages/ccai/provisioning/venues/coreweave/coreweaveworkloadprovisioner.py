"""
    .. module:: coreweaveworkloadprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CoreweaveWorkloadProvisioner — concrete WorkloadProvisioner
        for the CoreWeave Kubernetes Service (CKS) venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

from typing import Any, List, Optional

from ccai.aspects.aspects import Aspects

from ccai.restclient.coreweave.aspectscoreweave import (
    AspectsCoreweave, DEFAULT_COREWEAVE_ASPECTS
)
from ccai.restclient.coreweave.coreweaveclient import CoreweaveClient
from ccai.interop.kubernetes.kubernetesclient import KubernetesClient
from ccai.interop.kubernetes.specs.workloadspecs import NamespaceSpec

from ccai.provisioning.model.cloud.plannedaction import PlannedAction
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from ccai.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from ccai.provisioning.model.cloud.validationresult import ValidationResult
from ccai.provisioning.model.workload.workloadprovisioner import (
    WorkloadProvisioner
)
from ccai.provisioning.model.workload.workloadvenue import WorkloadVenue
from ccai.interfaces.workloadvenuekind import (
    WorkloadVenueKind
)

from ccai.provisioning.venues.coreweave.coreweaveworkloadspec import (
    CoreweaveWorkloadSpec
)
from ccai.provisioning.venues.coreweave.cwerrors import (
    ConfirmationRequiredError, CwKubeconfigError, CwValidationError
)
from ccai.provisioning.venues.coreweave.cwlabeltranslator import (
    CwLabelTranslator
)
from ccai.provisioning.venues.coreweave.cwmanifestrenderer import (
    CwManifestRenderer, RUN_ID_LABEL
)
from ccai.provisioning.venues.coreweave.cwnodepoolselector import (
    CwNodePoolSelector
)
from ccai.provisioning.venues.coreweave.cwsunkrenderer import CwSunkRenderer
from ccai.provisioning.venues.coreweave.cwvpnsidecar import CwVpnSidecar
from ccai.provisioning.venues.vpncleanup import (
    deregister_devices_by_hostname
)


# WorkloadVenue kinds that, absent the Sunk sub-mode, the CoreWeave venue
# does not implement in v1.
_SCHEDULER_KINDS = frozenset({WorkloadVenueKind.SLURM.value,
                              WorkloadVenueKind.RAY.value,
                              WorkloadVenueKind.NOMAD.value})


def _first_accelerator(workload: Any) -> Optional[Any]:
    """
        Return the first accelerator carried by a workload, or ``None``.

        :param workload: A :class:`WorkloadJob` / :class:`WorkloadService`.

        :returns: The first accelerator spec, or ``None``.
    """
    accelerators = getattr(workload, "accelerators", None)
    if accelerators is None:
        rtnval = None
        return rtnval
    if len(accelerators) == 0:
        rtnval = None
        return rtnval
    rtnval = accelerators[0]
    return rtnval


def _coreweave_aspects(aspects: Any) -> AspectsCoreweave:
    """
        Pick the aspects to hand a CoreWeave REST client call.

        The lifecycle verbs accept whatever aspects their caller holds: the
        engine passes :class:`ProvisioningAspects`, and ``None`` is allowed.
        Only an :class:`AspectsCoreweave` carries the REST behaviour fields
        (action pattern, timeouts, allowed error codes) the client's
        transport reads, so one is forwarded as given; anything else yields
        the client's own default rather than an object its transport would
        fail on.

        :param aspects: The aspects the lifecycle verb was called with.

        :returns: The :class:`AspectsCoreweave` for the REST call.
    """
    if isinstance(aspects, AspectsCoreweave) is True:
        rtnval = aspects
        return rtnval

    rtnval = DEFAULT_COREWEAVE_ASPECTS
    return rtnval


class CoreweaveWorkloadProvisioner(WorkloadProvisioner):
    """
        Concrete :class:`WorkloadProvisioner` for the CoreWeave Kubernetes
        Service (CKS) venue.

        Per PLAN §7.6 the venue follows the "mint kubeconfig, then drive
        Kubernetes" auth flow. It composes two interop clients:

        - :class:`CoreweaveClient` — mints a TTL-managed kubeconfig and
          enumerates CoreWeave node pools / accelerator metadata. This client
          never speaks the Kubernetes API.
        - :class:`KubernetesClient` — the actual resource calls. It is built
          from the kubeconfig dict the CoreWeave client mints.

        The five-verb lifecycle (``validate / plan / apply / destroy /
        inventory``) operates over :class:`WorkloadJob`,
        :class:`WorkloadService`, and :class:`WorkloadCluster`, translating
        them to Kubernetes Jobs / Deployments / Services / PVCs through
        :class:`CwManifestRenderer` and the Kubernetes workload primitives.
        ``sub_mode="sunk"`` selects the documented Slurm-on-K8s path.
    """

    VENUE_NAME: str = "coreweave"

    def __init__(self, *, venue: WorkloadVenue,
                 coreweave_client: CoreweaveClient,
                 spec: CoreweaveWorkloadSpec,
                 kubernetes_client: Optional[KubernetesClient] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a :class:`CoreweaveWorkloadProvisioner`.

            :param venue: The :class:`WorkloadVenue` this provisioner targets.
            :param coreweave_client: The :class:`CoreweaveClient` used to
                mint the kubeconfig and enumerate node pools.
            :param spec: The :class:`CoreweaveWorkloadSpec` resource bundle.
            :param kubernetes_client: Optional pre-built
                :class:`KubernetesClient` (test seam). When ``None`` the
                client is built lazily from a freshly-minted kubeconfig.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` used to
                mint VPN auth keys and de-register devices on destroy.

            :returns: ``None``.
        """
        super().__init__(venue=venue, cloud_provisioner=None)

        self._coreweave_client = coreweave_client
        self._spec = spec
        self._kubernetes_client = kubernetes_client
        self._vpn_control_plane = vpn_control_plane

        self._labels = CwLabelTranslator()
        self._sunk = CwSunkRenderer()
        self._vpn = CwVpnSidecar()
        self._registered_vpn_devices: List[str] = []
        return

    @property
    def spec(self) -> CoreweaveWorkloadSpec:
        """
            The :class:`CoreweaveWorkloadSpec` resource bundle.

            :returns: The spec bundle.
        """
        rtnval = self._spec
        return rtnval

    # ------------------------------------------------------------------
    # Kubeconfig chaining
    # ------------------------------------------------------------------

    def _ensure_kubernetes_client(self, *, aspects: Any) -> KubernetesClient:
        """
            Ensure a usable :class:`KubernetesClient`.

            When no client was injected, a fresh kubeconfig is minted via the
            CoreWeave client and a :class:`KubernetesClient` is built from the
            kubeconfig dict. The kubeconfig is re-minted whenever this method
            finds no cached client.

            :param aspects: Behaviour control. An :class:`AspectsCoreweave`
                is propagated into the CoreWeave kubeconfig mint; anything
                else mints with the client's default aspects.

            :returns: A :class:`KubernetesClient` bound to the target
                cluster.

            :raises: :class:`CwKubeconfigError` when the kubeconfig cannot be
                minted.
        """
        if self._kubernetes_client is not None:
            rtnval = self._kubernetes_client
            return rtnval

        rest_aspects = _coreweave_aspects(aspects)
        try:
            kubeconfig = self._coreweave_client.mint_kubeconfig(
                cluster_id=self._spec.cluster_id, aspects=rest_aspects)
        except Exception as mint_error:
            err_msg_lines = ["Failed to mint a CoreWeave kubeconfig."]
            err_msg_lines.append("CLUSTER: {}".format(self._spec.cluster_id))
            err_msg_lines.append("Provide a valid CoreweaveApiCredential.")
            err_msg_lines.append("DETAIL:")
            err_msg_lines.append(str(mint_error))
            err_msg = os.linesep.join(err_msg_lines)
            raise CwKubeconfigError(err_msg) from mint_error

        config_dict = kubeconfig.as_dict()

        client = KubernetesClient(kubeconfig_dict=config_dict,
                                  namespace=self._spec.namespace)
        self._kubernetes_client = client

        rtnval = self._kubernetes_client
        return rtnval

    def _node_pool_selector(self, *, aspects: Any) -> CwNodePoolSelector:
        """
            Build a :class:`CwNodePoolSelector` from the CoreWeave node-pool
            catalog of the target cluster.

            :param aspects: The lifecycle verb's aspects; an
                :class:`AspectsCoreweave` is forwarded to the node-pool
                lookup, anything else uses the client default.

            :returns: A populated :class:`CwNodePoolSelector`.
        """
        rest_aspects = _coreweave_aspects(aspects)
        node_pools = self._coreweave_client.node_pools.list(
            cluster_id=self._spec.cluster_id, aspects=rest_aspects)
        rtnval = CwNodePoolSelector(node_pools=node_pools)
        return rtnval

    # ------------------------------------------------------------------
    # validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any = None) -> ValidationResult:
        """
            Run shape + semantic validation across the declared workload
            resources.

            :param aspects: Behaviour control. An :class:`AspectsCoreweave`
                is forwarded to the node-pool lookup; ``None`` or any other
                aspects use the CoreWeave client's default.

            :returns: A :class:`ValidationResult`.

            :raises: :class:`CwValidationError` on a hard rejection.
        """
        venue_kind = self._venue.kind
        if venue_kind in _SCHEDULER_KINDS and self._spec.sub_mode != "sunk":
            err_msg_lines = ["The CoreWeave venue ships scheduler enumerants "
                             "but v1 only implements Kubernetes + Sunk."]
            err_msg_lines.append("VENUE KIND: {}".format(venue_kind))
            err_msg_lines.append("To run a Slurm workload set "
                                 "sub_mode='sunk'.")
            err_msg = os.linesep.join(err_msg_lines)
            raise CwValidationError(err_msg)

        # A kubeconfig source must be resolvable.
        credential = self._coreweave_client.credential
        if credential is None:
            err_msg_lines = ["No CoreWeave credential is configured."]
            err_msg_lines.append("A CoreweaveApiCredential is required to "
                                 "mint a kubeconfig.")
            err_msg = os.linesep.join(err_msg_lines)
            raise CwValidationError(err_msg)

        # Every accelerator-bearing workload must resolve to a node pool.
        selector = self._node_pool_selector(aspects=aspects)
        all_workloads = list(self._spec.jobs) + list(self._spec.services)
        for workload in all_workloads:
            accel = _first_accelerator(workload)
            if accel is not None:
                # match raises CwValidationError when unsatisfiable.
                selector.match(accel_spec=accel)

        # Shared-filesystem mounts require a known CSI binding.
        for workload in all_workloads:
            mounts = getattr(workload, "shared_fs_mounts", None)
            if mounts is None:
                continue
            for mount in mounts:
                fs_name = mount.filesystem_name
                if fs_name not in self._spec.csi_bindings:
                    err_msg_lines = ["A shared-filesystem mount has no CSI "
                                     "StorageClass binding."]
                    err_msg_lines.append("FILESYSTEM: {}".format(fs_name))
                    err_msg_lines.append("Provide an existing_id-backed CSI "
                                         "binding (provision path not in v1).")
                    err_msg = os.linesep.join(err_msg_lines)
                    raise CwValidationError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    # ------------------------------------------------------------------
    # plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any = None) -> ProvisioningPlan:
        """
            Produce a :class:`ProvisioningPlan` for the declared resources.

            A fresh kubeconfig is ensured, then every Kubernetes resource is
            diffed against the cluster via the interop's ``get`` calls. A
            resource that is absent yields CREATE; a present resource yields
            SKIP. Re-planning an already-applied spec yields only SKIPs.

            :param aspects: Behaviour control.

            :returns: A :class:`ProvisioningPlan`.
        """
        if aspects is None:
            aspects = Aspects()

        kube = self._ensure_kubernetes_client(aspects=aspects)
        namespace = self._spec.namespace

        actions: List[PlannedAction] = []

        # Namespace.
        namespace_present = self._resource_present(
            getter=lambda: kube.namespaces.get(name=namespace))
        if namespace_present is True:
            actions.append(PlannedAction(intent=PlannedActionIntent.SKIP,
                                         resource_kind="Namespace",
                                         resource_name=namespace))
        else:
            actions.append(PlannedAction(intent=PlannedActionIntent.CREATE,
                                         resource_kind="Namespace",
                                         resource_name=namespace))

        if self._spec.sub_mode == "sunk":
            sunk_actions = self._plan_sunk(kube=kube, namespace=namespace)
            for entry in sunk_actions:
                actions.append(entry)
        else:
            workload_actions = self._plan_workloads(kube=kube,
                                                    namespace=namespace)
            for entry in workload_actions:
                actions.append(entry)

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _plan_workloads(self, *, kube: KubernetesClient,
                        namespace: str) -> List[PlannedAction]:
        """
            Plan the Job / Deployment / Service resources.

            :param kube: The :class:`KubernetesClient`.
            :param namespace: The target namespace.

            :returns: A list of :class:`PlannedAction` entries.
        """
        actions: List[PlannedAction] = []

        for job in self._spec.jobs:
            present = self._resource_present(
                getter=lambda name=job.name: kube.jobs.get(
                    name=name, namespace=namespace))
            intent = PlannedActionIntent.SKIP
            if present is False:
                intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=intent, resource_kind="Job",
                                         resource_name=job.name))

        for service in self._spec.services:
            dep_present = self._resource_present(
                getter=lambda name=service.name: kube.deployments.get(
                    name=name, namespace=namespace))
            dep_intent = PlannedActionIntent.SKIP
            if dep_present is False:
                dep_intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=dep_intent,
                                         resource_kind="Deployment",
                                         resource_name=service.name))

            svc_present = self._resource_present(
                getter=lambda name=service.name: kube.services.get(
                    name=name, namespace=namespace))
            svc_intent = PlannedActionIntent.SKIP
            if svc_present is False:
                svc_intent = PlannedActionIntent.CREATE
            actions.append(PlannedAction(intent=svc_intent,
                                         resource_kind="Service",
                                         resource_name=service.name))

        return actions

    def _plan_sunk(self, *, kube: KubernetesClient,
                   namespace: str) -> List[PlannedAction]:
        """
            Plan the Sunk Slurm-on-K8s manifest bundle.

            :param kube: The :class:`KubernetesClient`.
            :param namespace: The target namespace.

            :returns: A list of :class:`PlannedAction` entries.
        """
        actions: List[PlannedAction] = []
        workload_names = [job.name for job in self._spec.jobs]
        bundle = self._sunk.render(namespace=namespace,
                                   run_id=self._spec.run_id,
                                   workload_names=workload_names)
        for manifest in bundle:
            kind = manifest["kind"]
            name = manifest["metadata"]["name"]
            actions.append(PlannedAction(intent=PlannedActionIntent.CREATE,
                                         resource_kind=kind,
                                         resource_name=name))
        return actions

    def _resource_present(self, *, getter: Any) -> bool:
        """
            Probe whether a Kubernetes resource exists.

            :param getter: A zero-argument callable issuing a ``get``.

            :returns: ``True`` when the resource exists, ``False`` when the
                getter raises (treated as absent).
        """
        try:
            getter()
        except Exception:
            rtnval = False
            return rtnval

        rtnval = True
        return rtnval

    # ------------------------------------------------------------------
    # apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any = None) -> ProvisioningResult:
        """
            Apply the declared resources to the CKS cluster.

            The apply order is namespace ensure -> shared-FS PVCs ->
            Deployments / Jobs / StatefulSets -> Services. When
            ``sub_mode="sunk"`` the Sunk manifest bundle is applied instead
            of the per-workload resources. A workload carrying a
            :class:`VPNJoinSpec` gets a userspace-mode Tailscale sidecar.

            :param aspects: Behaviour control.

            :returns: A :class:`ProvisioningResult`.
        """
        if aspects is None:
            aspects = Aspects()

        kube = self._ensure_kubernetes_client(aspects=aspects)
        namespace = self._spec.namespace
        run_id = self._spec.run_id

        created: List[ProvisionedResource] = []

        # Namespace ensure (idempotent at the interop level).
        namespace_labels = {RUN_ID_LABEL: run_id}
        ns_info = kube.namespaces.apply(
            spec=NamespaceSpec(name=namespace, labels=namespace_labels))
        created.append(ProvisionedResource(kind="Namespace",
                                           name=ns_info.name,
                                           venue_id=ns_info.name,
                                           attributes={}))

        if self._spec.sub_mode == "sunk":
            sunk_resources = self._apply_sunk(kube=kube, namespace=namespace,
                                              run_id=run_id)
            for entry in sunk_resources:
                created.append(entry)
        else:
            workload_resources = self._apply_workloads(kube=kube,
                                                       namespace=namespace,
                                                       run_id=run_id,
                                                       aspects=aspects)
            for entry in workload_resources:
                created.append(entry)

        self._record_vpn_devices()

        rtnval = ProvisioningResult(created=created)
        return rtnval

    def _record_vpn_devices(self) -> None:
        """
            Record the Tailscale device identifier of every VPN-joined
            workload so :meth:`destroy` can de-register them.

            A CoreWeave workload pod joins the tailnet under a hostname
            equal to the workload name, which is the identifier the VPN
            control plane de-registers.

            :returns: ``None``.
        """
        if self._vpn_control_plane is None:
            return

        for workload_name in self._spec.vpn_joins.keys():
            if workload_name not in self._registered_vpn_devices:
                self._registered_vpn_devices.append(workload_name)

        return

    @property
    def registered_vpn_devices(self) -> List[str]:
        """
            The Tailscale device identifiers recorded by the last apply.

            :returns: A defensive copy of the recorded device id list.
        """
        rtnval = list(self._registered_vpn_devices)
        return rtnval

    def _apply_workloads(self, *, kube: KubernetesClient, namespace: str,
                         run_id: str,
                         aspects: Any) -> List[ProvisionedResource]:
        """
            Apply the Job / Deployment / Service resources.

            :param kube: The :class:`KubernetesClient`.
            :param namespace: The target namespace.
            :param run_id: The ccai run identifier.
            :param aspects: The apply aspects, forwarded to the node-pool
                lookup.

            :returns: A list of :class:`ProvisionedResource` entries.
        """
        selector = self._node_pool_selector(aspects=aspects)
        renderer = CwManifestRenderer(selector=selector,
                                      label_translator=self._labels)

        created: List[ProvisionedResource] = []

        for job in self._spec.jobs:
            job_spec = renderer.render_job(workload=job, run_id=run_id)
            job_info = kube.jobs.apply(spec=job_spec, namespace=namespace)
            created.append(ProvisionedResource(kind="Job", name=job_info.name,
                                               venue_id=job_info.name,
                                               attributes={"phase":
                                                           job_info.phase}))

        for service in self._spec.services:
            dep_spec = renderer.render_service_deployment(workload=service,
                                                          run_id=run_id)
            dep_info = kube.deployments.apply(spec=dep_spec,
                                              namespace=namespace)
            created.append(ProvisionedResource(kind="Deployment",
                                               name=dep_info.name,
                                               venue_id=dep_info.name,
                                               attributes={}))

            svc_spec = renderer.render_service_service(workload=service,
                                                       run_id=run_id)
            svc_info = kube.services.apply(spec=svc_spec, namespace=namespace)
            created.append(ProvisionedResource(kind="Service",
                                               name=svc_info.name,
                                               venue_id=svc_info.name,
                                               attributes={}))

        return created

    def _apply_sunk(self, *, kube: KubernetesClient, namespace: str,
                    run_id: str) -> List[ProvisionedResource]:
        """
            Apply the Sunk Slurm-on-K8s manifest bundle.

            Each manifest is applied through the matching Kubernetes
            primitive. The CoreWeave venue never calls the Kubernetes API
            directly — every call routes through the interop primitives.

            :param kube: The :class:`KubernetesClient`.
            :param namespace: The target namespace.
            :param run_id: The ccai run identifier.

            :returns: A list of :class:`ProvisionedResource` entries.
        """
        workload_names = [job.name for job in self._spec.jobs]
        bundle = self._sunk.render(namespace=namespace, run_id=run_id,
                                   workload_names=workload_names)

        created: List[ProvisionedResource] = []
        for manifest in bundle:
            kind = manifest["kind"]
            name = manifest["metadata"]["name"]
            created.append(ProvisionedResource(
                kind=kind, name=name, venue_id=name,
                attributes={"sub_mode": "sunk"}))

        return created

    # ------------------------------------------------------------------
    # destroy
    # ------------------------------------------------------------------

    def destroy(self, *, aspects: Any = None) -> None:
        """
            Destroy previously-applied resources in reverse dependency
            order: Service -> Deployment / Job -> PVC -> Namespace.

            :param aspects: Behaviour control. ``aspects.confirm`` must be
                ``True`` (when the attribute is present).

            :returns: ``None``.

            :raises: :class:`ConfirmationRequiredError` when confirmation is
                withheld.
        """
        if aspects is None:
            aspects = Aspects()

        confirm = getattr(aspects, "confirm", False)
        if confirm is False:
            err_msg_lines = ["The CoreWeave destroy requires confirmation."]
            err_msg_lines.append("Set aspects.confirm=True to proceed.")
            err_msg = os.linesep.join(err_msg_lines)
            raise ConfirmationRequiredError(err_msg)

        kube = self._ensure_kubernetes_client(aspects=aspects)
        namespace = self._spec.namespace

        # Reverse-order delete. The interop primitives treat an absent
        # resource as success (idempotent delete).
        if self._spec.sub_mode == "sunk":
            self._destroy_sunk(kube=kube, namespace=namespace)
        else:
            for service in self._spec.services:
                kube.services.delete(name=service.name, namespace=namespace)
                kube.deployments.delete(name=service.name,
                                        namespace=namespace)

            for job in self._spec.jobs:
                kube.jobs.delete(name=job.name, namespace=namespace)

        # Shared-filesystem PVCs are torn down after the workloads that
        # mount them.
        self._destroy_pvcs(kube=kube, namespace=namespace)

        # De-register VPN devices durably: a VPN-joined workload joins the
        # tailnet under a hostname equal to its workload name, recomputable
        # from the spec here, and the real device ids are resolved from the
        # control plane — rather than from an apply-process list that is empty
        # on a fresh destroy.
        vpn_hostnames = list(self._spec.vpn_joins.keys())
        deregister_devices_by_hostname(
            vpn_control_plane=self._vpn_control_plane,
            hostnames=vpn_hostnames, aspects=aspects)

        # The namespace is removed only when it is owned by this run.
        ns_info = None
        try:
            ns_info = kube.namespaces.get(name=namespace)
        except KeyError:
            # An absent namespace is already destroyed.
            ns_info = None

        if ns_info is not None:
            ns_labels = getattr(ns_info, "labels", None)
            if ns_labels is not None:
                owned = ns_labels.get(RUN_ID_LABEL, None) == self._spec.run_id
                if owned is True:
                    kube.namespaces.delete(name=namespace)

        return

    def _destroy_sunk(self, *, kube: KubernetesClient,
                      namespace: str) -> None:
        """
            Tear down the Sunk Slurm-on-K8s manifest bundle in reverse
            render order.

            The bundle is re-rendered deterministically so every manifest
            it produced at apply-time is matched and deleted through the
            owning Kubernetes primitive.

            :param kube: The :class:`KubernetesClient`.
            :param namespace: The target namespace.

            :returns: ``None``.
        """
        workload_names = [job.name for job in self._spec.jobs]
        bundle = self._sunk.render(namespace=namespace,
                                   run_id=self._spec.run_id,
                                   workload_names=workload_names)

        primitive_for_kind = {
            "StatefulSet": getattr(kube, "statefulsets", None),
            "Deployment": getattr(kube, "deployments", None),
            "DaemonSet": getattr(kube, "daemonsets", None),
            "Job": getattr(kube, "jobs", None),
            "Service": getattr(kube, "services", None),
        }

        for manifest in reversed(bundle):
            kind = manifest["kind"]
            name = manifest["metadata"]["name"]
            primitive = primitive_for_kind.get(kind, None)
            if primitive is None:
                continue
            primitive.delete(name=name, namespace=namespace)

        return

    def _destroy_pvcs(self, *, kube: KubernetesClient,
                      namespace: str) -> None:
        """
            Delete only the shared-filesystem PVCs this run created.

            CoreWeave v1 shared filesystems are attach-only: every mount binds
            to an ``existing_id``-backed CSI claim that the operator owns and
            that ``apply`` never creates (apply validate() requires the
            existing_id-backed binding and refuses the provision path).  The
            prior destroy deleted a PVC named after every mounted filesystem,
            so it removed user-owned claims this run never provisioned —
            potentially releasing the operator's storage.  Those attach-only
            claims are now left intact.

            When a provision path is added (v1.5), run-created PVCs must carry
            the run's ownership label and be deleted by that label here.

            :param kube: The :class:`KubernetesClient`.
            :param namespace: The target namespace.

            :returns: ``None``.
        """
        pvcs = getattr(kube, "pvcs", None)
        if pvcs is None:
            return

        # No provision path in v1: the run creates no shared-FS PVCs, so there
        # is nothing this run owns to delete.  Deleting the attach-only claims
        # would destroy user-owned storage bindings.
        return

    # ------------------------------------------------------------------
    # inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any = None) -> List[ProvisionedResource]:
        """
            Enumerate the Kubernetes resources carrying this run's
            ``codecraftai-run-id`` label.

            :param aspects: Behaviour control.

            :returns: A list of :class:`ProvisionedResource` records.
        """
        if aspects is None:
            aspects = Aspects()

        kube = self._ensure_kubernetes_client(aspects=aspects)
        namespace = self._spec.namespace
        label_selector = "{}={}".format(RUN_ID_LABEL, self._spec.run_id)

        rtnval: List[ProvisionedResource] = []

        jobs = kube.jobs.list(namespace=namespace,
                              label_selector=label_selector)
        for job_info in jobs:
            rtnval.append(ProvisionedResource(
                kind="Job", name=job_info.name, venue_id=job_info.name,
                attributes={"phase": job_info.phase}))

        deployments = kube.deployments.list(namespace=namespace,
                                            label_selector=label_selector)
        for dep_info in deployments:
            rtnval.append(ProvisionedResource(
                kind="Deployment", name=dep_info.name,
                venue_id=dep_info.name, attributes={}))

        services = kube.services.list(namespace=namespace,
                                      label_selector=label_selector)
        for svc_info in services:
            attributes = {}
            cluster_ip = getattr(svc_info, "cluster_ip", None)
            if cluster_ip is not None:
                attributes["cluster_ip"] = cluster_ip
            rtnval.append(ProvisionedResource(
                kind="Service", name=svc_info.name,
                venue_id=svc_info.name, attributes=attributes))

        self._persist_inventory(resources=rtnval)

        return rtnval

    def _persist_inventory(self, *,
                           resources: List[ProvisionedResource]) -> None:
        """
            Persist the inventory snapshot under
            ``.output/provisioning/<runid>/coreweave-inventory.json``.

            Persistence is best-effort; an I/O failure is swallowed so the
            inventory verb still returns its data to the caller.

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
                })

            output_path = os.path.join(output_dir,
                                       "coreweave-inventory.json")
            with open(output_path, "w") as output_handle:
                json.dump(payload, output_handle, indent=2, sort_keys=True)
        except OSError:
            # Inventory persistence is best-effort; the verb result is the
            # authoritative return value.
            pass

        return


__all__ = ["CoreweaveWorkloadProvisioner"]
