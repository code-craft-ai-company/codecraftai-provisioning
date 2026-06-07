# libvirt / KVM Provisioning Venue

`LibvirtCloudProvisioner` realises the neutral cloud-resource model on a
libvirt-managed hypervisor host (KVM / QEMU) using the `libvirt-python`
native bindings surfaced by `codecraftai-interop-libvirt`. There is no REST
transport — libvirt speaks a binary RPC.

## Lifecycle

The provisioner implements the five-verb `CloudProvisioner` lifecycle:

- **validate** — shape + semantic checks, no remote I/O. Rejects object
  buckets, load balancers, DNS records, non-`NONE` HPC interconnects, and
  managed (non-`existing_id`) shared filesystems.
- **plan** — reads venue state, emits `CREATE` / `SKIP` / `UPDATE`.
- **apply** — match-then-act, idempotent. Networks define+start → volumes
  create → boot-volume clone + seed-ISO build → domain define+start.
- **destroy** — reverse-order teardown gated on `aspects.confirm`.
- **inventory** — enumerates run-id-tagged domains.

## Mapping

| Neutral model | libvirt primitive |
| --- | --- |
| `CloudNetwork` | libvirt virtual network (NAT) |
| `CloudInstance` | Domain (defined from XML; boot disk cloned from a base cloud-image) |
| `CloudStorageVolume` | qcow2 volume in a storage pool |
| `CloudKeyPair` | cloud-init `ssh_authorized_keys` in the seed ISO |
| `VPNJoinSpec` | cloud-init NoCloud `user-data` (rendered by the M6 renderer) |
| Tags + run id | XML `<metadata>` block under the ccai namespace |
| `CloudObjectBucket` / `CloudLoadBalancer` / `CloudDnsRecord` | unsupported — validate-error |

## Run-id metadata

libvirt has no native tags. The provisioner embeds the run id and the
neutral tag list inside the Domain XML `<metadata>` block under the
namespace `https://code-craft.ai/provisioning/v1`. `plan` and
`inventory` filter by parsing that block; tag round-tripping is the
identity.

## See also

- `codecraftai-provisioning/specs/cloud-resource-model/design.md`
- `codecraftai-provisioning/specs/cloud-provisioner-lifecycle/design.md`
- `codecraftai-provisioning/specs/vpn-join-spec/design.md`
- `codecraftai-interop-libvirt/Agents.md`
