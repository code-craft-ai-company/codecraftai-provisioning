"""
    .. module:: kubernetesworkloadprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: KubernetesWorkloadProvisioner — the real v1 WorkloadProvisioner
        for the KUBERNETES venue kind.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, List, Optional

from automojo.provisioning.model.exceptions import SchemaSemanticError
from automojo.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog
)
from automojo.provisioning.model.cloud.plannedaction import PlannedAction
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
from automojo.provisioning.model.workload.workloadspec import WorkloadSpec
from automojo.provisioning.model.workload.workloadvenue import WorkloadVenue
from automojo.provisioning.model.workload.workloadvenuekind import (
    WorkloadVenueKind
)


# The Kubernetes label key carrying the automojo run identifier on every
# resource the provisioner realises, so inventory / destroy can scope to a
# single run without false positives.
RUN_ID_LABEL = "automojo.run-id"


class KubernetesWorkloadProvisioner(WorkloadProvisioner):
    """
        The real v1 :class:`WorkloadProvisioner` for the ``KUBERNETES``
        workload-venue kind.

        This is a *venue-agnostic* base.  It translates declarative
        :class:`WorkloadJob` / :class:`WorkloadService` resources into
        Kubernetes Job / Deployment / Service primitives through an injected
        :class:`automojo.interop.kubernetes.kubernetesclient.KubernetesClient`.
        The venue (CoreWeave, RunPod, self-hosted) supplies the cluster
        connection — the venue-specific ``CoreweaveWorkloadProvisioner``
        conceptually specialises this kind and overrides only the credential
        exchange (CoreWeave API credential -> kubeconfig).

        The five-verb lifecycle (validate / plan / apply / destroy /
        inventory) is fully implemented here.  The Kubernetes client is the
        sole I/O seam; tests inject a deterministic in-memory fake.
    """

    VENUE_KIND: str = WorkloadVenueKind.KUBERNETES.value

    def __init__(self, *, venue: WorkloadVenue,
                 kubernetes_client: Any,
                 spec: WorkloadSpec,
                 cloud_provisioner: Optional[Any] = None,
                 credential_resolver: Optional[Any] = None,
                 accelerator_catalog: Optional[CloudAcceleratorCatalog] = None
                 ) -> None:
        """
            Construct a :class:`KubernetesWorkloadProvisioner`.

            :param venue: The :class:`WorkloadVenue` this provisioner
                targets.  Its ``kind`` must be ``KUBERNETES``.
            :param kubernetes_client: A bound Kubernetes interop client (or
                an equivalent deterministic test fake) exposing the
                ``jobs`` / ``deployments`` / ``services`` / ``namespaces``
                primitive sub-clients.
            :param spec: The venue-neutral :class:`WorkloadSpec` resource
                bundle.
            :param cloud_provisioner: Optional CloudProvisioner composition
                for the self-hosted case.
            :param credential_resolver: Optional credential resolver
                callable (see :class:`WorkloadProvisioner`).
            :param accelerator_catalog: Optional accelerator catalog.

            :returns: None

            :raises: SchemaSemanticError
        """
        super().__init__(venue=venue, cloud_provisioner=cloud_provisioner,
                         credential_resolver=credential_resolver,
                         accelerator_catalog=accelerator_catalog)

        if venue.kind != self.VENUE_KIND:
            err_msg_lines = ["KubernetesWorkloadProvisioner requires a "
                             "KUBERNETES workload venue."]
            err_msg_lines.append("VENUE: {}".format(venue.name))
            err_msg_lines.append("VENUE_KIND: {}".format(venue.kind))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        self._kubernetes_client: Any = kubernetes_client
        self._spec: WorkloadSpec = spec
        return

    @property
    def spec(self) -> WorkloadSpec:
        """
            Return the :class:`WorkloadSpec` resource bundle.

            :returns: The spec bundle.
        """
        rtnval = self._spec
        return rtnval

    @property
    def kubernetes_client(self) -> Any:
        """
            Return the bound Kubernetes interop client.

            :returns: The Kubernetes client.
        """
        rtnval = self._kubernetes_client
        return rtnval

    # ------------------------------------------------------------------
    # validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any = None) -> ValidationResult:
        """
            Run shape + semantic validation across the declared workload
            resources.

            The validate sweep runs every base-class validation hook:
            credential resolution, credential-type match, node-pool
            accelerator resolution against the catalog, and LoadBalancer
            exposure rejection.  No remote I/O is performed.

            :param aspects: Behaviour control (unused; accepted for
                lifecycle-signature parity).

            :returns: A :class:`ValidationResult` with ``ok=True`` on
                success.

            :raises: SchemaSemanticError
        """
        credential = self.resolve_credential()
        if credential is not None:
            self.validate_credential(credential=credential)

        self.validate_node_pool_accelerators(cluster=self._spec.cluster)
        self.validate_service_exposure(services=self._spec.services)

        rtnval = ValidationResult(ok=True)
        return rtnval

    # ------------------------------------------------------------------
    # plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any = None) -> ProvisioningPlan:
        """
            Compute a dry-run :class:`ProvisioningPlan`.

            Every Kubernetes resource is diffed against the cluster via the
            interop ``get`` calls.  An absent resource yields CREATE; a
            present one yields SKIP.  Re-planning an already-applied spec
            yields only SKIPs.

            :param aspects: Behaviour control (unused).

            :returns: A :class:`ProvisioningPlan`.
        """
        kube = self._kubernetes_client
        namespace = self._spec.namespace

        actions: List[PlannedAction] = []

        ns_present = self._resource_present(
            getter=lambda: kube.namespaces.get(name=namespace))
        ns_intent = PlannedActionIntent.SKIP
        if ns_present is False:
            ns_intent = PlannedActionIntent.CREATE
        actions.append(PlannedAction(intent=ns_intent,
                                     resource_kind="Namespace",
                                     resource_name=namespace))

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

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    # ------------------------------------------------------------------
    # apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any = None) -> ProvisioningResult:
        """
            Apply the declared resources to the Kubernetes cluster.

            The apply order is namespace ensure -> Jobs -> Deployments ->
            Services.  Every realised resource is labelled with the run
            identifier so inventory and destroy can scope to one run.  The
            interop primitive ``apply`` calls are idempotent, so a repeat
            apply yields the same cluster state.

            :param aspects: Behaviour control (unused).

            :returns: A :class:`ProvisioningResult`.
        """
        from automojo.interop.kubernetes.specs.workloadspecs import (
            DeploymentSpec, JobSpec, NamespaceSpec, ServiceSpec
        )

        kube = self._kubernetes_client
        namespace = self._spec.namespace
        run_id = self._spec.run_id
        run_labels = {RUN_ID_LABEL: run_id}

        created: List[ProvisionedResource] = []

        ns_info = kube.namespaces.apply(
            spec=NamespaceSpec(name=namespace, labels=dict(run_labels)))
        created.append(ProvisionedResource(kind="Namespace",
                                           name=ns_info.name,
                                           venue_id=ns_info.name,
                                           attributes={}))

        for job in self._spec.jobs:
            job_spec = JobSpec(name=job.name, image=job.image,
                               command=list(job.command),
                               env=dict(job.env),
                               restart_policy=job.restart_policy,
                               completions=job.replicas,
                               parallelism=job.replicas,
                               labels=dict(run_labels))
            job_info = kube.jobs.apply(spec=job_spec, namespace=namespace)
            created.append(ProvisionedResource(kind="Job", name=job_info.name,
                                               venue_id=job_info.name,
                                               attributes={}))

        for service in self._spec.services:
            container_port = self._first_port(service=service)
            dep_spec = DeploymentSpec(name=service.name, image=service.image,
                                      replicas=service.replicas,
                                      container_port=container_port,
                                      env=dict(service.env),
                                      labels=dict(run_labels))
            dep_info = kube.deployments.apply(spec=dep_spec,
                                              namespace=namespace)
            created.append(ProvisionedResource(kind="Deployment",
                                               name=dep_info.name,
                                               venue_id=dep_info.name,
                                               attributes={}))

            svc_spec = ServiceSpec(name=service.name,
                                   ports=self._all_ports(service=service),
                                   selector={"app": service.name},
                                   service_type=service.exposure,
                                   labels=dict(run_labels))
            svc_info = kube.services.apply(spec=svc_spec, namespace=namespace)
            created.append(ProvisionedResource(kind="Service",
                                               name=svc_info.name,
                                               venue_id=svc_info.name,
                                               attributes={}))

        rtnval = ProvisioningResult(created=created)
        return rtnval

    # ------------------------------------------------------------------
    # destroy
    # ------------------------------------------------------------------

    def _destroy_impl(self, *, aspects: Any = None) -> None:
        """
            Destroy previously-applied resources in reverse dependency
            order: Service -> Deployment -> Job -> Namespace.

            This hook runs only after the base
            :meth:`WorkloadProvisioner.destroy` confirm-gate (which defaults
            ``aspects.confirm`` to ``False``) has passed.  The namespace that
            :meth:`apply` created is deleted last so that ``destroy``
            inverts ``apply`` (no orphaned namespace is left behind).

            :param aspects: Behaviour control (unused here; the confirm-gate
                is enforced by the base class).

            :returns: None
        """
        kube = self._kubernetes_client
        namespace = self._spec.namespace

        for service in self._spec.services:
            kube.services.delete(name=service.name, namespace=namespace)
            kube.deployments.delete(name=service.name, namespace=namespace)

        for job in self._spec.jobs:
            kube.jobs.delete(name=job.name, namespace=namespace)

        kube.namespaces.delete(name=namespace)

        return

    # ------------------------------------------------------------------
    # inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any = None) -> List[ProvisionedResource]:
        """
            Enumerate the Kubernetes resources carrying this run's
            run-id label.

            :param aspects: Behaviour control (unused).

            :returns: A list of :class:`ProvisionedResource` records.
        """
        kube = self._kubernetes_client
        namespace = self._spec.namespace
        label_selector = "{}={}".format(RUN_ID_LABEL, self._spec.run_id)

        rtnval: List[ProvisionedResource] = []

        jobs = kube.jobs.list(namespace=namespace,
                              label_selector=label_selector)
        for job_info in jobs:
            rtnval.append(ProvisionedResource(kind="Job", name=job_info.name,
                                              venue_id=job_info.name,
                                              attributes={}))

        deployments = kube.deployments.list(namespace=namespace,
                                            label_selector=label_selector)
        for dep_info in deployments:
            rtnval.append(ProvisionedResource(kind="Deployment",
                                              name=dep_info.name,
                                              venue_id=dep_info.name,
                                              attributes={}))

        services = kube.services.list(namespace=namespace,
                                      label_selector=label_selector)
        for svc_info in services:
            rtnval.append(ProvisionedResource(kind="Service",
                                              name=svc_info.name,
                                              venue_id=svc_info.name,
                                              attributes={}))

        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resource_present(self, *, getter: Any) -> bool:
        """
            Probe whether a Kubernetes resource exists.

            :param getter: A zero-argument callable issuing a ``get``.

            :returns: ``True`` when the resource exists, ``False`` when the
                getter raises a lookup-style error (treated as absent).

            :raises: SchemaSemanticError
        """
        try:
            getter()
        except (LookupError, FileNotFoundError):
            # A lookup-style failure means the resource is absent. Any other
            # error (transport, auth, semantic) must bubble rather than be
            # silently reported as "absent" and trigger a spurious create.
            rtnval = False
            return rtnval

        rtnval = True
        return rtnval

    def _first_port(self, *, service: Any) -> Optional[int]:
        """
            Return the first container port a service declares, or ``None``.

            :param service: The :class:`WorkloadService`.

            :returns: The first port number, or ``None``.
        """
        ports = self._all_ports(service=service)
        if len(ports) == 0:
            rtnval = None
            return rtnval
        rtnval = ports[0]
        return rtnval

    def _all_ports(self, *, service: Any) -> List[int]:
        """
            Return every port number a service declares.

            :param service: The :class:`WorkloadService`.

            :returns: A list of integer port numbers.
        """
        rtnval: List[int] = []
        port_dicts = getattr(service, "ports", None)
        if port_dicts is None:
            return rtnval
        for port_dict in port_dicts:
            port_value = port_dict.get("port", None)
            if port_value is not None:
                rtnval.append(port_value)
        return rtnval


__all__ = ["KubernetesWorkloadProvisioner", "RUN_ID_LABEL"]
