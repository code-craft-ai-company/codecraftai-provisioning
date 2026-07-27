"""
    .. module:: _mockclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MockXenClient — an in-memory stand-in for the XCP-ng interop
        :class:`XenClient`, exposing the same api-group surface so the venue
        provisioner can be exercised without any XAPI traffic.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.interop.xen.model.xennetwork import XenNetwork
from ccai.interop.xen.model.xenstoragerepository import (
    XenStorageRepository
)
from ccai.interop.xen.model.xenvbd import XenVbd
from ccai.interop.xen.model.xenvdi import XenVdi
from ccai.interop.xen.model.xenvif import XenVif
from ccai.interop.xen.model.xenvm import XenVm
from ccai.interop.xen.model.xenvmtemplate import XenVmTemplate


class _DoneHandle:
    """
        Minimal task-handle stand-in whose :meth:`wait` is an immediate
        no-op, used by the mock VMs group for async-shaped operations.
    """

    def wait(self, *, aspects: Any) -> None:
        """
            Return immediately; the mock completes operations synchronously.

            :param aspects: Behaviour control (unused).
        """
        _ = aspects
        return


class _MockTemplatesGroup:
    """ Mock of the XenClient ``Templates`` api-group. """

    def __init__(self, *, owner: "MockXenClient") -> None:
        """
            Construct a templates group.

            :param owner: The owning :class:`MockXenClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[XenVmTemplate]:
        """
            Enumerate the seeded templates.

            :param aspects: Behaviour control (unused).

            :returns: The template list.
        """
        _ = aspects
        rtnval = list(self._owner.templates.values())
        return rtnval


class _MockNetworksGroup:
    """ Mock of the XenClient ``Networks`` api-group. """

    def __init__(self, *, owner: "MockXenClient") -> None:
        """
            Construct a networks group.

            :param owner: The owning :class:`MockXenClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[XenNetwork]:
        """
            Enumerate the seeded networks.

            :param aspects: Behaviour control (unused).

            :returns: The network list.
        """
        _ = aspects
        rtnval = list(self._owner.networks.values())
        return rtnval

    def get_by_name_label(self, *, name_label: str,
                          aspects: Any) -> List[XenNetwork]:
        """
            Return networks whose ``name_label`` matches.

            :param name_label: The network name_label to match.
            :param aspects: Behaviour control (unused).

            :returns: The matching network list.
        """
        _ = aspects
        rtnval = [n for n in self._owner.networks.values()
                  if n.name_label == name_label]
        return rtnval


class _MockSrGroup:
    """ Mock of the XenClient ``Sr`` api-group. """

    def __init__(self, *, owner: "MockXenClient") -> None:
        """
            Construct an SR group.

            :param owner: The owning :class:`MockXenClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[XenStorageRepository]:
        """
            Enumerate the seeded storage repositories.

            :param aspects: Behaviour control (unused).

            :returns: The SR list.
        """
        _ = aspects
        rtnval = list(self._owner.srs.values())
        return rtnval


class _MockVdiGroup:
    """ Mock of the XenClient ``Vdi`` api-group. """

    def __init__(self, *, owner: "MockXenClient") -> None:
        """
            Construct a VDI group.

            :param owner: The owning :class:`MockXenClient`.
        """
        self._owner = owner
        return

    def list(self, *, sr_uuid: Optional[str] = None,
             aspects: Any = None) -> List[XenVdi]:
        """
            Enumerate VDIs, optionally filtered by SR.

            :param sr_uuid: Optional SR uuid filter.
            :param aspects: Behaviour control (unused).

            :returns: The VDI list.
        """
        _ = aspects
        out: List[XenVdi] = []
        for vdi in self._owner.vdis.values():
            if sr_uuid is not None and vdi.sr_uuid != sr_uuid:
                continue
            out.append(vdi)
        rtnval = out
        return rtnval

    def create(self, *, spec: Any, aspects: Any) -> XenVdi:
        """
            Create a VDI (idempotent by name_label on the target SR).

            :param spec: The :class:`XenVdiSpec`.
            :param aspects: Behaviour control (unused).

            :returns: The created or pre-existing VDI.
        """
        _ = aspects
        for vdi in self._owner.vdis.values():
            if vdi.name_label == spec.name_label and vdi.sr_uuid == spec.sr_uuid:
                rtnval = vdi
                return rtnval
        self._owner.create_calls = self._owner.create_calls + 1
        uuid = self._owner.alloc(prefix="vdi")
        vdi = XenVdi(uuid=uuid, name_label=spec.name_label,
                     name_description=spec.name_description,
                     sr_uuid=spec.sr_uuid, virtual_size=spec.virtual_size)
        self._owner.vdis[uuid] = vdi
        rtnval = vdi
        return rtnval

    def delete(self, *, vdi_uuid: str, aspects: Any) -> None:
        """
            Destroy a VDI by uuid (idempotent).

            :param vdi_uuid: The VDI uuid.
            :param aspects: Behaviour control (unused).
        """
        _ = aspects
        if vdi_uuid in self._owner.vdis:
            del self._owner.vdis[vdi_uuid]
        return


class _MockVbdsGroup:
    """ Mock of the XenClient ``Vbds`` api-group. """

    def __init__(self, *, owner: "MockXenClient") -> None:
        """
            Construct a VBDs group.

            :param owner: The owning :class:`MockXenClient`.
        """
        self._owner = owner
        return

    def list(self, *, vm_uuid: Optional[str] = None,
             aspects: Any = None) -> List[XenVbd]:
        """
            Enumerate VBDs, optionally filtered by VM.

            :param vm_uuid: Optional VM uuid filter.
            :param aspects: Behaviour control (unused).

            :returns: The VBD list.
        """
        _ = aspects
        out: List[XenVbd] = []
        for vbd in self._owner.vbds.values():
            if vm_uuid is not None and vbd.vm_uuid != vm_uuid:
                continue
            out.append(vbd)
        rtnval = out
        return rtnval

    def attach(self, *, spec: Any, aspects: Any) -> XenVbd:
        """
            Attach a VDI to a VM through a VBD (idempotent by VM/VDI).

            :param spec: The :class:`XenVbdSpec`.
            :param aspects: Behaviour control (unused).

            :returns: The created or pre-existing VBD.
        """
        _ = aspects
        for vbd in self._owner.vbds.values():
            if vbd.vm_uuid == spec.vm_uuid and vbd.vdi_uuid == spec.vdi_uuid:
                rtnval = vbd
                return rtnval
        uuid = self._owner.alloc(prefix="vbd")
        vbd = XenVbd(uuid=uuid, vm_uuid=spec.vm_uuid, vdi_uuid=spec.vdi_uuid,
                     userdevice=spec.userdevice, bootable=spec.bootable)
        self._owner.vbds[uuid] = vbd
        rtnval = vbd
        return rtnval


class _MockVifsGroup:
    """ Mock of the XenClient ``Vifs`` api-group. """

    def __init__(self, *, owner: "MockXenClient") -> None:
        """
            Construct a VIFs group.

            :param owner: The owning :class:`MockXenClient`.
        """
        self._owner = owner
        return

    def list(self, *, vm_uuid: Optional[str] = None,
             aspects: Any = None) -> List[XenVif]:
        """
            Enumerate VIFs, optionally filtered by VM.

            :param vm_uuid: Optional VM uuid filter.
            :param aspects: Behaviour control (unused).

            :returns: The VIF list.
        """
        _ = aspects
        out: List[XenVif] = []
        for vif in self._owner.vifs.values():
            if vm_uuid is not None and vif.vm_uuid != vm_uuid:
                continue
            out.append(vif)
        rtnval = out
        return rtnval

    def attach(self, *, spec: Any, aspects: Any) -> XenVif:
        """
            Attach a VM to a network through a VIF (idempotent).

            :param spec: The :class:`XenVifSpec`.
            :param aspects: Behaviour control (unused).

            :returns: The created or pre-existing VIF.
        """
        _ = aspects
        for vif in self._owner.vifs.values():
            if (vif.vm_uuid == spec.vm_uuid
                    and vif.network_uuid == spec.network_uuid
                    and vif.device == spec.device):
                rtnval = vif
                return rtnval
        uuid = self._owner.alloc(prefix="vif")
        vif = XenVif(uuid=uuid, vm_uuid=spec.vm_uuid,
                     network_uuid=spec.network_uuid, device=spec.device,
                     mac=spec.mac)
        self._owner.vifs[uuid] = vif
        rtnval = vif
        return rtnval


class _MockVmsGroup:
    """ Mock of the XenClient ``Vms`` api-group. """

    def __init__(self, *, owner: "MockXenClient") -> None:
        """
            Construct a VMs group.

            :param owner: The owning :class:`MockXenClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[XenVm]:
        """
            Enumerate the non-template VMs.

            :param aspects: Behaviour control (unused).

            :returns: The VM list.
        """
        _ = aspects
        rtnval = list(self._owner.vms.values())
        return rtnval

    def clone_from_template(self, *, template_uuid: str, spec: Any,
                            aspects: Any) -> tuple:
        """
            Clone a VM from a template (idempotent by name_label).

            :param template_uuid: The source template uuid.
            :param spec: The :class:`XenVmCloneSpec`.
            :param aspects: Behaviour control (unused).

            :returns: A tuple ``(XenVm, handle-or-None)``.
        """
        _ = aspects
        for vm in self._owner.vms.values():
            if vm.name_label == spec.name_label:
                rtnval = (vm, None)
                return rtnval
        self._owner.clone_calls = self._owner.clone_calls + 1
        uuid = self._owner.alloc(prefix="vm")
        vm = XenVm(
            uuid=uuid, name_label=spec.name_label,
            name_description=spec.name_description, power_state="Halted",
            vcpus_max=spec.vcpus_max if spec.vcpus_max is not None else 1,
            memory_static_max=(spec.memory_bytes
                               if spec.memory_bytes is not None else 0),
            is_a_template=False, is_control_domain=False,
            other_config=dict(spec.other_config), tags=list(spec.tags))
        self._owner.vms[uuid] = vm
        self._owner.xenstore[uuid] = dict(spec.xenstore_data)
        rtnval = (vm, _DoneHandle())
        return rtnval

    def start(self, *, vm_uuid: str, aspects: Any) -> _DoneHandle:
        """
            Start a VM, moving it to the Running power state.

            :param vm_uuid: The VM uuid.
            :param aspects: Behaviour control (unused).

            :returns: A completed task handle.
        """
        _ = aspects
        if vm_uuid in self._owner.vms:
            self._owner.vms[vm_uuid].power_state = "Running"
        self._owner.start_calls = self._owner.start_calls + 1
        rtnval = _DoneHandle()
        return rtnval

    def clean_shutdown(self, *, vm_uuid: str, aspects: Any) -> _DoneHandle:
        """
            Cleanly shut down a VM, moving it to the Halted power state.

            :param vm_uuid: The VM uuid.
            :param aspects: Behaviour control (unused).

            :returns: A completed task handle.
        """
        _ = aspects
        if vm_uuid in self._owner.vms:
            self._owner.vms[vm_uuid].power_state = "Halted"
        rtnval = _DoneHandle()
        return rtnval

    def destroy(self, *, vm_uuid: str, aspects: Any) -> None:
        """
            Destroy a VM by uuid (idempotent).

            :param vm_uuid: The VM uuid.
            :param aspects: Behaviour control (unused).
        """
        _ = aspects
        if vm_uuid in self._owner.vms:
            del self._owner.vms[vm_uuid]
        if vm_uuid in self._owner.xenstore:
            del self._owner.xenstore[vm_uuid]
        return


class MockXenClient:
    """
        In-memory stand-in for the ``codecraftai-interop-xen`` :class:`XenClient`.

        Holds deterministic dictionaries for templates, networks, SRs, VMs,
        VDIs, VBDs and VIFs and exposes the same lazily-constructed api-group
        property surface so the venue provisioner can be exercised without
        any XAPI traffic.  Mutating calls update the in-memory state so apply
        / destroy idempotence can be observed.
    """

    def __init__(self) -> None:
        """
            Construct a MockXenClient with one Template, one Network, and
            one shared SR with ample free capacity.
        """
        self._counter = 0
        self.clone_calls = 0
        self.create_calls = 0
        self.start_calls = 0

        self.templates: Dict[str, XenVmTemplate] = {
            "tmpl-ubuntu": XenVmTemplate(
                uuid="tmpl-ubuntu",
                name_label="Ubuntu 22.04 (64-bit) Template",
                name_description="", os_version_hint="ubuntu"),
        }
        self.networks: Dict[str, XenNetwork] = {
            "net-lab": XenNetwork(uuid="net-lab", name_label="lab-net",
                                  name_description="", bridge="xenbr0",
                                  mtu=1500),
        }
        self.srs: Dict[str, XenStorageRepository] = {
            "sr-shared": XenStorageRepository(
                uuid="sr-shared", name_label="Shared NFS", type="nfs",
                physical_size=2 * 1024 * 1024 * 1024 * 1024,
                physical_utilisation=0, shared=True),
        }
        self.vms: Dict[str, XenVm] = {}
        self.vdis: Dict[str, XenVdi] = {}
        self.vbds: Dict[str, XenVbd] = {}
        self.vifs: Dict[str, XenVif] = {}
        self.xenstore: Dict[str, Dict[str, str]] = {}

        self._templates_group = _MockTemplatesGroup(owner=self)
        self._networks_group = _MockNetworksGroup(owner=self)
        self._sr_group = _MockSrGroup(owner=self)
        self._vdi_group = _MockVdiGroup(owner=self)
        self._vbds_group = _MockVbdsGroup(owner=self)
        self._vifs_group = _MockVifsGroup(owner=self)
        self._vms_group = _MockVmsGroup(owner=self)
        return

    def alloc(self, *, prefix: str) -> str:
        """
            Allocate a deterministic uuid.

            :param prefix: The uuid prefix.

            :returns: A unique uuid string.
        """
        self._counter = self._counter + 1
        rtnval = "{}-{}".format(prefix, self._counter)
        return rtnval

    @property
    def Templates(self) -> _MockTemplatesGroup:
        """
            Return the mock Templates api-group.

            :returns: The templates group.
        """
        rtnval = self._templates_group
        return rtnval

    @property
    def Networks(self) -> _MockNetworksGroup:
        """
            Return the mock Networks api-group.

            :returns: The networks group.
        """
        rtnval = self._networks_group
        return rtnval

    @property
    def Sr(self) -> _MockSrGroup:
        """
            Return the mock Sr api-group.

            :returns: The SR group.
        """
        rtnval = self._sr_group
        return rtnval

    @property
    def Vdi(self) -> _MockVdiGroup:
        """
            Return the mock Vdi api-group.

            :returns: The VDI group.
        """
        rtnval = self._vdi_group
        return rtnval

    @property
    def Vbds(self) -> _MockVbdsGroup:
        """
            Return the mock Vbds api-group.

            :returns: The VBDs group.
        """
        rtnval = self._vbds_group
        return rtnval

    @property
    def Vifs(self) -> _MockVifsGroup:
        """
            Return the mock Vifs api-group.

            :returns: The VIFs group.
        """
        rtnval = self._vifs_group
        return rtnval

    @property
    def Vms(self) -> _MockVmsGroup:
        """
            Return the mock Vms api-group.

            :returns: The VMs group.
        """
        rtnval = self._vms_group
        return rtnval


class RecordingVpnControlPlane:
    """
        Minimal ``IVPNControlPlane`` test double recording the device ids
        passed to :meth:`delete_device`.
    """

    def __init__(self, *, minted_authkey: str = "tskey-mock-0001") -> None:
        """
            Construct a RecordingVpnControlPlane.

            :param minted_authkey: The auth key handed to the apply stage.
        """
        self.minted_authkey = minted_authkey
        self.deleted_device_ids: List[str] = []
        return

    def delete_device(self, *, device_id: str, aspects: Any) -> None:
        """
            Record a device-id de-registration.

            :param device_id: The VPN device id.
            :param aspects: Behaviour control (unused).
        """
        _ = aspects
        self.deleted_device_ids.append(device_id)
        return
