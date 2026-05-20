"""
    .. module:: _mockclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MockLibvirtClient — an in-memory stand-in for the libvirt
               interop client used by the venue test suite.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List

from automojo.interop.libvirt.model.libvirtdomaininfo import LibvirtDomainInfo
from automojo.interop.libvirt.model.libvirtnetwork import LibvirtNetwork
from automojo.interop.libvirt.model.libvirtvolume import LibvirtVolume

from automojo.provisioning.venues.libvirt.lvdomainxmlbuilder import (
    LvDomainXmlBuilder
)


class _MockNetworksGroup:
    """
        In-memory stand-in for the interop ``NetworksGroup``.
    """

    def __init__(self, *, owner: "MockLibvirtClient") -> None:
        """
            Construct a _MockNetworksGroup.

            :param owner: The owning :class:`MockLibvirtClient`.
        """
        self._owner = owner
        return

    def list_networks(self, *, aspects: Any) -> List[LibvirtNetwork]:
        """
            List the defined networks.

            :param aspects: Behaviour control (unused).

            :returns: The network list.
        """
        rtnval = list(self._owner.networks_state.values())
        return rtnval

    def define_network(self, *, spec: Any, aspects: Any) -> LibvirtNetwork:
        """
            Define a network from a spec, idempotently by name.

            :param spec: The :class:`LibvirtNetworkSpec`.
            :param aspects: Behaviour control (unused).

            :returns: The defined or pre-existing network record.
        """
        existing = self._owner.networks_state.get(spec.name, None)
        if existing is not None:
            rtnval = existing
            return rtnval
        self._owner.define_network_calls = (
            self._owner.define_network_calls + 1
        )
        uuid = self._owner.next_id(prefix="net")
        record = LibvirtNetwork(name=spec.name, uuid=uuid, active=False,
                                forward_mode=spec.forward_mode,
                                bridge=spec.bridge_name)
        self._owner.networks_state[spec.name] = record
        rtnval = record
        return rtnval

    def start_network(self, *, name: str, aspects: Any) -> None:
        """
            Start a defined network (idempotent).

            :param name: The network name.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        existing = self._owner.networks_state.get(name, None)
        if existing is not None:
            existing.active = True
        return

    def stop_network(self, *, name: str, aspects: Any) -> None:
        """
            Stop a running network (idempotent).

            :param name: The network name.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        existing = self._owner.networks_state.get(name, None)
        if existing is not None:
            existing.active = False
        return

    def undefine_network(self, *, name: str, aspects: Any) -> None:
        """
            Undefine a network (idempotent).

            :param name: The network name.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        if name in self._owner.networks_state:
            del self._owner.networks_state[name]
        return


class _MockVolumesGroup:
    """
        In-memory stand-in for the interop ``VolumesGroup``.
    """

    def __init__(self, *, owner: "MockLibvirtClient") -> None:
        """
            Construct a _MockVolumesGroup.

            :param owner: The owning :class:`MockLibvirtClient`.
        """
        self._owner = owner
        return

    def list_volumes(self, *, pool_name: str,
                     aspects: Any) -> List[LibvirtVolume]:
        """
            List the volumes in a pool.

            :param pool_name: The pool name.
            :param aspects: Behaviour control (unused).

            :returns: The volume list for the pool.
        """
        pool = self._owner.volumes_state.get(pool_name, {})
        rtnval = list(pool.values())
        return rtnval

    def create_volume(self, *, pool_name: str, spec: Any,
                      aspects: Any) -> LibvirtVolume:
        """
            Create a volume in a pool, idempotently by name.

            :param pool_name: The pool name.
            :param spec: The :class:`LibvirtVolumeSpec`.
            :param aspects: Behaviour control (unused).

            :returns: The created or pre-existing volume record.
        """
        pool = self._owner.volumes_state.setdefault(pool_name, {})
        existing = pool.get(spec.name, None)
        if existing is not None:
            rtnval = existing
            return rtnval
        self._owner.create_volume_calls = (
            self._owner.create_volume_calls + 1
        )
        path = "/var/lib/libvirt/{}/{}".format(pool_name, spec.name)
        record = LibvirtVolume(name=spec.name, pool_name=pool_name,
                               path=path,
                               capacity_bytes=spec.capacity_bytes,
                               allocation_bytes=0,
                               volume_format=spec.volume_format)
        pool[spec.name] = record
        rtnval = record
        return rtnval

    def delete_volume(self, *, pool_name: str, name: str,
                      aspects: Any) -> None:
        """
            Delete a volume by name (idempotent).

            :param pool_name: The pool name.
            :param name: The volume name.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        pool = self._owner.volumes_state.get(pool_name, {})
        if name in pool:
            del pool[name]
        return


class _MockDomainsGroup:
    """
        In-memory stand-in for the interop ``DomainsGroup``.
    """

    def __init__(self, *, owner: "MockLibvirtClient") -> None:
        """
            Construct a _MockDomainsGroup.

            :param owner: The owning :class:`MockLibvirtClient`.
        """
        self._owner = owner
        return

    def list_domains(self, *, aspects: Any) -> List[LibvirtDomainInfo]:
        """
            List the defined domains.

            :param aspects: Behaviour control (unused).

            :returns: The domain info list.
        """
        out: List[LibvirtDomainInfo] = []
        for record in self._owner.domains_state.values():
            out.append(record["info"])
        rtnval = out
        return rtnval

    def get_domain_xml(self, *, name: str, aspects: Any) -> str:
        """
            Return the persistent XML for a domain.

            :param name: The domain name.
            :param aspects: Behaviour control (unused).

            :returns: The domain XML string.
        """
        record = self._owner.domains_state[name]
        rtnval = record["xml"]
        return rtnval

    def define_domain(self, *, spec: Any, aspects: Any) -> LibvirtDomainInfo:
        """
            Define a domain from a spec, idempotently by name.

            :param spec: The :class:`LibvirtDomainSpec`.
            :param aspects: Behaviour control (unused).

            :returns: The defined or pre-existing domain info record.
        """
        existing = self._owner.domains_state.get(spec.name, None)
        if existing is not None:
            rtnval = existing["info"]
            return rtnval
        self._owner.define_domain_calls = (
            self._owner.define_domain_calls + 1
        )
        uuid = self._owner.next_id(prefix="dom")
        info = LibvirtDomainInfo(name=spec.name, uuid=uuid,
                                 state="shutoff", vcpus=spec.vcpus,
                                 memory_kib=spec.memory_kib,
                                 cpu_time_ns=0)
        metadata = ""
        if spec.metadata_xml is not None:
            metadata = spec.metadata_xml
        xml = ("<domain type='kvm'><name>{}</name><uuid>{}</uuid>"
               "<metadata>{}</metadata></domain>").format(
                   spec.name, uuid, metadata
               )
        self._owner.domains_state[spec.name] = {"info": info, "xml": xml}
        rtnval = info
        return rtnval

    def create_domain(self, *, name: str, aspects: Any) -> None:
        """
            Start a defined domain (idempotent).

            :param name: The domain name.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        record = self._owner.domains_state.get(name, None)
        if record is not None:
            record["info"].state = "running"
        return

    def destroy_domain(self, *, name: str, aspects: Any) -> None:
        """
            Force-power-off a domain (idempotent).

            :param name: The domain name.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        record = self._owner.domains_state.get(name, None)
        if record is not None:
            record["info"].state = "shutoff"
        return

    def undefine_domain(self, *, name: str, aspects: Any) -> None:
        """
            Undefine a domain (idempotent).

            :param name: The domain name.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        if name in self._owner.domains_state:
            del self._owner.domains_state[name]
        return


class MockLibvirtClient:
    """
        In-memory stand-in for :class:`LibvirtClient`.

        Holds deterministic dictionaries for networks, volumes (keyed by
        pool), and domains so the venue provisioner can be exercised
        without any native libvirt bindings.  Mutating calls update the
        in-memory state so apply / destroy idempotence can be observed.
        The four API groups are reachable through the same public
        attributes as the real client.
    """

    def __init__(self) -> None:
        """
            Construct an empty MockLibvirtClient.
        """
        self.networks_state: Dict[str, LibvirtNetwork] = {}
        self.volumes_state: Dict[str, Dict[str, LibvirtVolume]] = {}
        self.domains_state: Dict[str, Dict[str, Any]] = {}
        self._counter = 0
        self.define_network_calls = 0
        self.create_volume_calls = 0
        self.define_domain_calls = 0

        self.networks = _MockNetworksGroup(owner=self)
        self.volumes = _MockVolumesGroup(owner=self)
        self.domains = _MockDomainsGroup(owner=self)
        return

    def next_id(self, *, prefix: str) -> str:
        """
            Allocate a deterministic identifier.

            :param prefix: The identifier prefix.

            :returns: A new identifier string.
        """
        self._counter = self._counter + 1
        rtnval = "{}-{:08d}".format(prefix, self._counter)
        return rtnval

    def seed_base_image(self, *, pool: str, volume_name: str) -> None:
        """
            Seed a read-only base-image volume into the mock state.

            :param pool: The base-image pool name.
            :param volume_name: The base-image volume name.

            :returns: ``None``.
        """
        pool_state = self.volumes_state.setdefault(pool, {})
        path = "/var/lib/libvirt/{}/{}".format(pool, volume_name)
        pool_state[volume_name] = LibvirtVolume(
            name=volume_name, pool_name=pool, path=path,
            capacity_bytes=10 * 1024 * 1024 * 1024, allocation_bytes=0,
            volume_format="qcow2",
        )
        return


class RecordingVpnControlPlane:
    """
        Minimal ``IVPNControlPlane`` test double recording the device ids
        passed to :meth:`delete_device`.
    """

    def __init__(self, *, minted_authkey: str = "tskey-mock-0001") -> None:
        """
            Construct a RecordingVpnControlPlane.

            :param minted_authkey: The auth key handed to the apply
                stage.
        """
        self.minted_authkey = minted_authkey
        self.deleted_device_ids: List[str] = []
        return

    def delete_device(self, *, device_id: str, aspects: Any) -> None:
        """
            Record a device-id de-registration.

            :param device_id: The device id to de-register.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        self.deleted_device_ids.append(device_id)
        return
