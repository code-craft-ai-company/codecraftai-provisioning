"""
    .. module:: hvhardware
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HvHardware — resolved Hyper-V VM hardware shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


class HvHardware:
    """
        Resolved hardware shape for a Hyper-V VM.

        Carries the processor count, startup memory and root-disk size that
        a neutral ``size`` hint resolved to.
    """

    def __init__(self, *, processor_count: int, memory_startup_bytes: int,
                 disk_bytes: int) -> None:
        """
            Construct an HvHardware.

            :param processor_count: Virtual processor count; > 0.
            :param memory_startup_bytes: Startup memory in bytes; > 0.
            :param disk_bytes: Root disk size in bytes; > 0.
        """
        self.processor_count: int = processor_count
        self.memory_startup_bytes: int = memory_startup_bytes
        self.disk_bytes: int = disk_bytes
        return
