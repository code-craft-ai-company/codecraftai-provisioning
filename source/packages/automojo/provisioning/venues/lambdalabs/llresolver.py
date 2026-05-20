"""
    .. module:: llresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LlResolver — neutral accelerator + interconnect to Lambda
               Labs instance-type slug / 1-click cluster resolution.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Optional

from automojo.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog, default_accelerator_catalog
)
from automojo.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from automojo.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from automojo.provisioning.model.exceptions import SchemaSemanticError
from automojo.provisioning.venues.lambdalabs.llerrors import LlValidationError


# Interconnect kinds that signal a multi-node InfiniBand request and so
# resolve to a 1-Click Cluster offering rather than a single instance.
_INFINIBAND_KINDS = frozenset({
    "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR",
})

VENUE_NAME = "lambdalabs"


class LlResolutionResult:
    """
        Result of resolving a neutral accelerator request onto Lambda Labs.

        Carries the Lambda instance-type slug, whether the request resolved
        to a 1-click cluster, and the resolved neutral catalog name.
    """

    def __init__(self, *, instance_type_slug: str, is_cluster: bool,
                 neutral_name: str) -> None:
        """
            Construct an LlResolutionResult.

            :param instance_type_slug: The Lambda Labs instance-type slug.
            :param is_cluster: Whether a 1-click cluster is required.
            :param neutral_name: The neutral accelerator catalog name.
        """
        self._instance_type_slug = instance_type_slug
        self._is_cluster = is_cluster
        self._neutral_name = neutral_name
        return

    @property
    def instance_type_slug(self) -> str:
        """
            The Lambda Labs instance-type slug.

            :returns: The instance-type slug string.
        """
        return self._instance_type_slug

    @property
    def is_cluster(self) -> bool:
        """
            Whether the request resolved to a 1-click cluster.

            :returns: ``True`` when a 1-click cluster is required.
        """
        return self._is_cluster

    @property
    def neutral_name(self) -> str:
        """
            The neutral accelerator catalog name.

            :returns: The neutral name string.
        """
        return self._neutral_name


class LlResolver:
    """
        Resolves a neutral accelerator spec — optionally with an
        interconnect — onto a Lambda Labs instance-type slug, deciding
        between a single instance and a 1-Click Cluster offering.
    """

    def __init__(self, *,
                 catalog: Optional[CloudAcceleratorCatalog] = None) -> None:
        """
            Construct an LlResolver.

            :param catalog: Optional accelerator catalog; defaults to the
                packaged singleton.
        """
        if catalog is not None:
            self._catalog: CloudAcceleratorCatalog = catalog
        else:
            self._catalog = default_accelerator_catalog()
        return

    def accelerator_to_instance_type(self, *,
                                     accel_spec: CloudAcceleratorSpec,
                                     interconnect: Optional[CloudInterconnect]
                                     ) -> LlResolutionResult:
        """
            Resolve a neutral accelerator spec onto a Lambda Labs slug.

            When ``interconnect`` is an InfiniBand kind the result is
            flagged as a 1-Click Cluster; otherwise a single-instance slug
            is returned.

            :param accel_spec: The neutral :class:`CloudAcceleratorSpec`.
            :param interconnect: Optional :class:`CloudInterconnect`.

            :returns: An :class:`LlResolutionResult`.

            :raises: :class:`LlValidationError` when the accelerator has no
                Lambda Labs SKU.
        """
        if accel_spec is None:
            raise LlValidationError(
                "LlResolver requires a non-None CloudAcceleratorSpec."
            )

        try:
            slug = self._catalog.resolve(neutral_name=accel_spec.model,
                                         venue=VENUE_NAME)
        except SchemaSemanticError as xcpt:
            err_msg_lines = [
                "Accelerator has no Lambda Labs SKU."
            ]
            err_msg_lines.append("NEUTRAL NAME: {}".format(accel_spec.model))
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise LlValidationError(err_msg) from None

        is_cluster = False
        if interconnect is not None:
            if interconnect.kind in _INFINIBAND_KINDS:
                is_cluster = True

        rtnval = LlResolutionResult(instance_type_slug=slug,
                                    is_cluster=is_cluster,
                                    neutral_name=accel_spec.model)
        return rtnval

    def resolve_instance_type(self, *, instance, ) -> Optional[LlResolutionResult]:
        """
            Resolve a :class:`CloudInstance` onto a Lambda Labs slug.

            When the instance carries accelerators the first accelerator is
            resolved via the catalog; otherwise the instance ``size`` field
            is taken to already be a Lambda Labs slug.

            :param instance: The neutral :class:`CloudInstance`.

            :returns: An :class:`LlResolutionResult`, or ``None`` when the
                instance carries neither accelerators nor a usable size.

            :raises: :class:`LlValidationError` when an accelerator has no
                Lambda Labs SKU.
        """
        accelerators = instance.accelerators
        if accelerators is not None and len(accelerators) > 0:
            first = accelerators[0]
            rtnval = self.accelerator_to_instance_type(
                accel_spec=first, interconnect=instance.interconnect
            )
            return rtnval

        size = instance.size
        if size is None or len(size) == 0:
            rtnval = None
            return rtnval

        is_cluster = False
        if instance.interconnect is not None:
            if instance.interconnect.kind in _INFINIBAND_KINDS:
                is_cluster = True

        rtnval = LlResolutionResult(instance_type_slug=size,
                                    is_cluster=is_cluster,
                                    neutral_name=size)
        return rtnval
