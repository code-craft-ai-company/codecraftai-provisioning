"""
    .. module:: pipelinestage
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PipelineStage enum for the provisioning engine.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from enum import Enum


class PipelineStage(Enum):
    """
        Eight-stage provisioning pipeline.

        Stages run in declaration order; the engine never reorders them.
        Dry-run halts at the end of PLAN.
    """

    LOAD_VALIDATE = "load_validate"
    PLAN = "plan"
    APPLY_NETWORKING = "apply_networking"
    APPLY_COMPUTE = "apply_compute"
    APPLY_DNS_AND_STORAGE_AND_LB = "apply_dns_and_storage_and_lb"
    BOOTSTRAP_VPN = "bootstrap_vpn"
    VERIFY = "verify"
    EMIT_LANDSCAPE_INVENTORY = "emit_landscape_inventory"


PIPELINE_STAGE_ORDER = (
    PipelineStage.LOAD_VALIDATE,
    PipelineStage.PLAN,
    PipelineStage.APPLY_NETWORKING,
    PipelineStage.APPLY_COMPUTE,
    PipelineStage.APPLY_DNS_AND_STORAGE_AND_LB,
    PipelineStage.BOOTSTRAP_VPN,
    PipelineStage.VERIFY,
    PipelineStage.EMIT_LANDSCAPE_INVENTORY,
)
