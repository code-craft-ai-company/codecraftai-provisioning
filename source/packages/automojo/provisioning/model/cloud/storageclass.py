"""
    .. module:: storageclass
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Enum describing the venue-neutral storage class of a block volume.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from enum import Enum


class StorageClass(str, Enum):
    """
        Venue-neutral storage class for a block storage volume.

        - STANDARD: general-purpose SSD; the default.
        - BALANCED: cost / performance balanced SSD.
        - PERFORMANCE: high-IOPS / provisioned SSD.
        - ARCHIVE: cold / HDD / throughput-optimised storage.
    """
    STANDARD = "standard"
    BALANCED = "balanced"
    PERFORMANCE = "performance"
    ARCHIVE = "archive"
