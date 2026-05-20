"""
    .. module:: plannedactionintent
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PlannedActionIntent enum for provisioning plans.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from enum import Enum


class PlannedActionIntent(Enum):
    """
        Discriminator for a single planned action against a resource.

        CREATE — resource is absent from the venue and will be created.
        UPDATE — resource exists with a different shape and will be updated.
        SKIP   — resource exists with a matching shape; no mutation needed.
        DELETE — resource exists but is no longer present in the spec.
    """

    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"
    DELETE = "delete"
