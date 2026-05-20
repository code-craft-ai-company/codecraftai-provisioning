# Design — libvirt / KVM Provisioner

## Overview

`LibvirtCloudProvisioner` realises the neutral resource model on a libvirt host
(or several, addressed by per-URI connections) using the `libvirt-python`
native bindings — there is no REST involved.  The bindings are wrapped by
`automojo-interop-libvirt`, which owns connection lifecycle, XML
construction/parsing, and the cloud-init seed-ISO builder.

libvirt has no notion of tags; the provisioner uses an XML metadata block under
a custom namespace (`https://automationmojo.com/provisioning/v1`) to record
the `automojo-run-id` and neutral tags.  Querying by tag is implemented as
"list all Domains, parse metadata, filter".

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `automojo-interop-libvirt/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              LibvirtCloudProvisioner                         │
│  provisioning/venues/libvirt/libvirtcloudprovisioner.py      │
└────┬───────────────────┬────────────────────┬───────────────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│LvDomainXml  │  │LvMetadataTrans   │  │LvSeedIsoBuilder      │
│builder      │  │ neutral↔metadata │  │ user-data + meta-data│
└─────────────┘  └──────────────────┘  └──────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│        LibvirtClient (automojo-interop-libvirt)              │
│   connections / networks / storage_pools / volumes / domains │
│   libvirt-python native bindings                             │
└──────────────────────────────────────────────────────────────┘
```

Native binding call paths used by `apply`:

- `conn.listAllNetworks()` / `conn.networkDefineXML(xml)` + `.create()`
- `conn.listAllStoragePools()` / `conn.storagePoolDefineXML(xml)` + `.create()`
- `pool.listAllVolumes()` / `pool.createXMLFrom(xml, backing_vol)` for
  backing-chain clone
- `conn.listAllDomains()` / `conn.defineXML(xml)` + `.create()`
- QEMU guest agent via `dom.qemuAgentCommand(...)` for IP discovery
- Seed ISO uploaded as a volume in the configured `cloudinit` pool

---

## Mapping Table

| Neutral model | libvirt primitive | Notes |
| --- | --- | --- |
| `apod` envelope | connection URI | one URI per venue instance. |
| `CloudNetwork` | libvirt Network (NAT or bridged) | XML-defined; isolated mode also supported. |
| `CloudSubnet` | DHCP range inside Network XML | recorded in metadata. |
| `CloudSecurityGroup` | (no native) | warning at validate; rules become iptables on the host (out of scope). |
| `CloudKeyPair` | injected into seed ISO `user-data` `ssh_authorized_keys`. |
| `CloudImage` | base-image volume in configured pool | `ubuntu/24.04` → `ubuntu-24.04-server-cloudimg-amd64.img`. |
| `CloudInstance` | Domain | `size` → `<vcpu>` + `<memory>` + disk size. |
| `CloudInterconnect` | unsupported | `validate`-error. |
| `CloudStorageVolume` | qcow2 volume + Domain disk attach. |
| `CloudObjectBucket` | unsupported | `validate`-error. |
| `CloudLoadBalancer` | unsupported | `validate`-error. |
| `CloudDnsRecord` | external | warn today. |
| `CloudSharedFilesystem(*, existing_id)` | virtio-9p / NFS attach | attach-only. |
| `VPNJoinSpec` | seed ISO `user-data` `runcmd`. |
| Tags | XML `<metadata><automojo:tags>` | round-trip identity. |

---

## Module Layout

```
source/packages/automojo/provisioning/venues/libvirt/
├── __init__.py
├── libvirtcloudprovisioner.py
├── lvdomainxmlbuilder.py
├── lvmetadatatranslator.py        # neutral tags ↔ XML metadata
├── lvseedisobuilder.py            # cidata ISO build
├── lvplanbuilder.py
├── lvapplystages.py
├── lvdestroystages.py
├── lvinventory.py
└── lverrors.py
```

---

## Idempotency

Every Domain/Network/Volume has a stable name derived from
`<spec-name>-<run-id-short>`; pre-create lookups by name distinguish CREATE
from SKIP.  Domain XML reconfigure uses `virDomainUpdateDeviceFlags` for
hot-pluggable device changes; vCPU/RAM hot-plug honoured when the guest
supports it; otherwise UPDATE-by-recreate gated on `aspects.confirm`.

---

## Testing Strategy

- `MockLibvirtConnection` returns deterministic XML and supports the subset of
  the API surface used.
- Property tests: idempotent apply, inverse destroy, metadata round-trip
  identity for tag sets containing namespaces/colons/whitespace.
- Validate-table tests confirm rejections.
- Seed-ISO builder tested independently — content hash determinism is
  asserted across runs.
- Live runs gated by `RUN_LIVE_LIBVIRT=1` against a local `qemu:///system`.
