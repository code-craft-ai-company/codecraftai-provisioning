"""
    .. module:: workloadprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Abstract base class for workload venue provisioners.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from automojo.provisioning.model.exceptions import SchemaSemanticError
from automojo.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog, default_accelerator_catalog
)
from automojo.provisioning.model.workload.workloadvenue import WorkloadVenue
from automojo.provisioning.model.workload.workloadvenuekind import (
    WorkloadVenueKind
)


# Per WorkloadVenueKind, the set of credential types accepted by validate.
# A credential object exposes its type via a ``credential_type`` (preferred)
# or ``kind`` attribute.  KUBERNETES additionally accepts venue-native
# credentials that exchange for a kubeconfig (e.g. CoreweaveApiCredential).
_ACCEPTED_CREDENTIAL_TYPES = {
    WorkloadVenueKind.KUBERNETES.value: frozenset({
        "kubeconfig", "KubeconfigCredential",
        "coreweave_api", "CoreweaveApiCredential",
        "runpod_api", "RunpodApiCredential",
    }),
    WorkloadVenueKind.SLURM.value: frozenset({
        "ssh", "SshCredential", "slurm_token", "SlurmTokenCredential",
    }),
    WorkloadVenueKind.RAY.value: frozenset({
        "ray_token", "RayTokenCredential", "ssh", "SshCredential",
    }),
    WorkloadVenueKind.NOMAD.value: frozenset({
        "nomad_token", "NomadTokenCredential",
    }),
}


class WorkloadProvisioner(ABC):
    """
        Abstract base for workload venue provisioners.

        The five-verb lifecycle (validate / plan / apply / destroy /
        inventory) mirrors :class:`CloudProvisioner`.  Optional
        ``cloud_provisioner`` composition supports the self-hosted case (the
        engine drives the cloud apply first and destroys in reverse).

        The base class supplies the venue-agnostic *validation hooks* every
        subclass needs:

        * :meth:`resolve_credential` — resolve ``venue.credential_ref`` to a
          credential object via an injected resolver.
        * :meth:`validate_credential` — confirm the resolved credential's
          type matches the venue ``kind``.
        * :meth:`validate_node_pool_accelerators` — confirm every node-pool
          accelerator resolves on the parent venue via the catalog.
        * :meth:`validate_service_exposure` — reject ``LoadBalancer``
          exposure on venues that do not support managed load balancers.
    """

    # Subclasses set this True when the venue offers managed load balancers.
    SUPPORTS_LOAD_BALANCER: bool = True

    def __init__(self, *, venue: WorkloadVenue,
                 cloud_provisioner: Optional[Any] = None,
                 credential_resolver: Optional[Any] = None,
                 accelerator_catalog: Optional[CloudAcceleratorCatalog] = None
                 ) -> None:
        """
            Initialise the workload provisioner.

            :param venue: WorkloadVenue this provisioner operates on.
            :param cloud_provisioner: Optional CloudProvisioner composition
                for the self-hosted case.
            :param credential_resolver: Optional callable that maps a
                ``credential_ref`` string to a credential object.  The
                callable signature is ``resolver(credential_ref=<str>)``.
                When ``None`` credential resolution is skipped during
                validate (no vault is wired).
            :param accelerator_catalog: Optional accelerator catalog used by
                :meth:`validate_node_pool_accelerators`.  Defaults to the
                process-wide catalog singleton.

            :returns: None
        """
        self._venue: WorkloadVenue = venue
        self._cloud_provisioner: Optional[Any] = cloud_provisioner
        self._credential_resolver: Optional[Any] = credential_resolver
        if accelerator_catalog is not None:
            self._accelerator_catalog: CloudAcceleratorCatalog = accelerator_catalog
        else:
            self._accelerator_catalog = default_accelerator_catalog()
        return

    @property
    def venue(self) -> WorkloadVenue:
        """
            Return the WorkloadVenue this provisioner is bound to.

            :returns: The WorkloadVenue.
        """
        rtnval = self._venue
        return rtnval

    @property
    def cloud_provisioner(self) -> Optional[Any]:
        """
            Return the optional composed CloudProvisioner, if any.

            :returns: The composed CloudProvisioner or None.
        """
        rtnval = self._cloud_provisioner
        return rtnval

    @property
    def accelerator_catalog(self) -> CloudAcceleratorCatalog:
        """
            Return the accelerator catalog this provisioner validates
            against.

            :returns: The CloudAcceleratorCatalog.
        """
        rtnval = self._accelerator_catalog
        return rtnval

    # ------------------------------------------------------------------
    # Validation hooks (shared by every subclass)
    # ------------------------------------------------------------------

    def resolve_credential(self) -> Optional[Any]:
        """
            Resolve the venue ``credential_ref`` to a credential object.

            When no resolver is injected this returns ``None`` so a
            subclass can decide whether the absence is fatal.  When a
            resolver is injected and the reference does not resolve, a
            :class:`SchemaSemanticError` is raised.

            :returns: The resolved credential object, or ``None`` when no
                resolver is wired.

            :raises: SchemaSemanticError
        """
        if self._credential_resolver is None:
            rtnval = None
            return rtnval

        credential_ref = self._venue.credential_ref
        resolved = self._credential_resolver(credential_ref=credential_ref)
        if resolved is None:
            err_msg_lines = ["The venue credential_ref did not resolve to a "
                             "registered credential."]
            err_msg_lines.append("VENUE: {}".format(self._venue.name))
            err_msg_lines.append("CREDENTIAL_REF: {}".format(credential_ref))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        rtnval = resolved
        return rtnval

    def validate_credential(self, *, credential: Any) -> None:
        """
            Confirm the resolved credential's type matches the venue
            ``kind``.

            The credential type is read from a ``credential_type`` attribute
            when present, otherwise from a ``kind`` attribute.  A type that
            is not in the accepted set for the venue ``kind`` raises
            :class:`SchemaSemanticError`.

            :param credential: The resolved credential object.

            :raises: SchemaSemanticError
        """
        if credential is None:
            err_msg_lines = ["No credential was supplied for credential-type "
                             "validation."]
            err_msg_lines.append("VENUE: {}".format(self._venue.name))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        credential_type = getattr(credential, "credential_type", None)
        if credential_type is None:
            credential_type = getattr(credential, "kind", None)
        if credential_type is None:
            err_msg_lines = ["The resolved credential exposes no "
                             "credential_type or kind attribute."]
            err_msg_lines.append("VENUE: {}".format(self._venue.name))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        venue_kind = self._venue.kind
        accepted = _ACCEPTED_CREDENTIAL_TYPES.get(venue_kind, frozenset())
        if credential_type not in accepted:
            err_msg_lines = ["The credential type does not match the "
                             "workload venue kind."]
            err_msg_lines.append("VENUE: {}".format(self._venue.name))
            err_msg_lines.append("VENUE_KIND: {}".format(venue_kind))
            err_msg_lines.append("CREDENTIAL_TYPE: {}".format(credential_type))
            err_msg_lines.append("ACCEPTED: {}".format(
                ", ".join(sorted(accepted))))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        return

    def validate_node_pool_accelerators(self, *,
                                        cluster: Optional[Any]) -> None:
        """
            Confirm every node-pool accelerator resolves on the parent venue.

            Each accelerator's neutral ``model`` name is resolved through the
            accelerator catalog against the parent venue name.  An
            unresolvable accelerator raises :class:`SchemaSemanticError` (the
            catalog raises it directly).

            :param cluster: The :class:`WorkloadCluster` to validate, or
                ``None`` when the spec declares no cluster.

            :raises: SchemaSemanticError
        """
        if cluster is None:
            return

        venue_name = self._venue.name

        all_pools: List[Any] = []
        node_pools = getattr(cluster, "node_pools", None)
        if node_pools is not None:
            for pool in node_pools:
                all_pools.append(pool)
        accelerator_pools = getattr(cluster, "accelerator_pools", None)
        if accelerator_pools is not None:
            for pool in accelerator_pools:
                all_pools.append(pool)

        for pool in all_pools:
            accelerators = getattr(pool, "accelerators", None)
            if accelerators is None:
                continue
            for accelerator in accelerators:
                model = getattr(accelerator, "model", None)
                if model is None:
                    continue
                # resolve raises SchemaSemanticError when unsupported.
                self._accelerator_catalog.resolve(neutral_name=model,
                                                  venue=venue_name)

        return

    def validate_service_exposure(self, *, services: List[Any]) -> None:
        """
            Reject ``LoadBalancer`` exposure on venues without LB support.

            When :attr:`SUPPORTS_LOAD_BALANCER` is ``False`` any service
            declaring ``exposure == "LoadBalancer"`` raises
            :class:`SchemaSemanticError`.

            :param services: The list of :class:`WorkloadService` resources.

            :raises: SchemaSemanticError
        """
        if self.SUPPORTS_LOAD_BALANCER is True:
            return

        offenders: List[str] = []
        for service in services:
            exposure = getattr(service, "exposure", None)
            if exposure == "LoadBalancer":
                offenders.append(getattr(service, "name", "<unnamed>"))

        if len(offenders) > 0:
            err_msg_lines = ["LoadBalancer exposure is not supported on this "
                             "workload venue."]
            err_msg_lines.append("VENUE: {}".format(self._venue.name))
            err_msg_lines.append("OFFENDING SERVICES: ({})".format(
                len(offenders)))
            for name in offenders:
                err_msg_lines.append("    {}".format(name))
            err_msg_lines.append("Use ClusterIP or NodePort exposure.")
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        return

    # ------------------------------------------------------------------
    # Five-verb lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def validate(self, *, aspects: Any) -> Any:
        """
            Run shape + semantic validation across the declared workload
            resources.

            :param aspects: Aspects controlling validation behaviour.
        """
        raise NotImplementedError(
            "{}.validate must be implemented by subclasses.".format(
                type(self).__name__
            )
        )

    @abstractmethod
    def plan(self, *, aspects: Any) -> Any:
        """
            Produce a ProvisioningPlan for the declared resources.

            :param aspects: Aspects controlling planning behaviour.
        """
        raise NotImplementedError(
            "{}.plan must be implemented by subclasses.".format(
                type(self).__name__
            )
        )

    @abstractmethod
    def apply(self, *, aspects: Any) -> Any:
        """
            Apply the plan and produce a ProvisioningResult.

            :param aspects: Aspects controlling apply behaviour.
        """
        raise NotImplementedError(
            "{}.apply must be implemented by subclasses.".format(
                type(self).__name__
            )
        )

    def destroy(self, *, aspects: Any = None) -> None:
        """
            Destroy previously-applied resources.

            This base implementation provides the central confirm-gate that
            mirrors :class:`CloudProvisioner.destroy`.  Teardown is gated by
            ``aspects.confirm = True``; without confirmation this method
            raises :class:`SchemaSemanticError` before dispatching to the
            subclass :meth:`_destroy_impl` hook.

            Subclasses should implement :meth:`_destroy_impl` rather than
            overriding :meth:`destroy`, so the confirm-gate cannot be
            bypassed.  Subclasses that still override :meth:`destroy`
            directly remain responsible for their own confirm-gating.

            :param aspects: Aspects controlling destroy behaviour.  When an
                ``aspects.confirm`` attribute is present it must be ``True``.

            :raises: SchemaSemanticError
        """
        confirm = self._destroy_confirm_value(aspects=aspects)
        if confirm is not True:
            err_msg_lines = ["{}.destroy requires aspects.confirm=True "
                             "to prevent accidental destruction.".format(
                                 type(self).__name__)]
            err_msg_lines.append("VENUE: {}".format(self._venue.name))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        self._destroy_impl(aspects=aspects)
        return

    @staticmethod
    def _destroy_confirm_value(*, aspects: Any) -> Any:
        """
            Read the ``confirm`` aspect from an aspects object or dict.

            The confirm-gate defaults to ``False`` (destruction denied)
            when no aspects are supplied or the attribute is absent.

            :param aspects: Aspects object, dict, or ``None``.

            :returns: The ``confirm`` value, defaulting to ``False``.
        """
        if aspects is None:
            rtnval = False
            return rtnval
        if isinstance(aspects, dict):
            rtnval = aspects.get("confirm", False)
            return rtnval
        rtnval = getattr(aspects, "confirm", False)
        return rtnval

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Subclass hook for destroy after confirm-gating.

            Subclasses implement teardown here.  The base :meth:`destroy`
            enforces the ``aspects.confirm=True`` gate before this hook is
            invoked.

            This hook is intentionally a concrete (non-abstract) method so
            that legacy subclasses which override :meth:`destroy` directly
            (and therefore never reach this hook) remain instantiable.
            Subclasses that rely on the base confirm-gate MUST override this
            hook; the default implementation raises ``NotImplementedError``.

            :param aspects: Aspects controlling destroy behaviour.

            :raises: NotImplementedError
        """
        raise NotImplementedError(
            "{}._destroy_impl must be implemented by subclasses that rely "
            "on the WorkloadProvisioner.destroy confirm-gate.".format(
                type(self).__name__
            )
        )

    @abstractmethod
    def inventory(self, *, aspects: Any) -> List[Any]:
        """
            Return an inventory of currently-known resources.

            :param aspects: Aspects controlling inventory behaviour.
        """
        raise NotImplementedError(
            "{}.inventory must be implemented by subclasses.".format(
                type(self).__name__
            )
        )


__all__ = ["WorkloadProvisioner"]
