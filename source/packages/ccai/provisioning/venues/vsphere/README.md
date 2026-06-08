# VSphere Venue Provisioner

`VSphereCloudProvisioner` realises the neutral cloud-resource model on
VMware vSphere / vCenter through the rebuilt `VSphereClient` in
[`codecraftai-interop-vsphere`](../../../../../../../codecraftai-interop-vsphere).

## Lifecycle

The venue implements the five-verb `CloudProvisioner` contract from
[`cloud-provisioner-lifecycle`](../../../../../specs/cloud-provisioner-lifecycle/design.md):
`validate` / `plan` / `apply` / `destroy` / `inventory`.  Every method
accepts `Aspects`; every long-running vCenter task is awaited through the
task handle's `wait(aspects=...)` inside the `VSphereOps` facade.

## Neutral model mapping

| Neutral model | vSphere realisation |
| --- | --- |
| `CloudNetwork` | Distributed Virtual Switch (reused by name) |
| `CloudSubnet` | Distributed Port Group carrying a VLAN id |
| `CloudSecurityGroup` | NSX-T SG when NSX is present; otherwise out of scope (M14) |
| `CloudKeyPair` | injected into guest-customisation cloud-init `users:` |
| `CloudImage` | Content Library item (tag lookup) or folder VM template |
| `CloudInstance` | VM — Content Library clone or `VmCreateSpec` build |
| `CloudStorageVolume` | virtual disk on a `find_datastore_with_free_gb` datastore |
| `CloudObjectBucket` | **validate-error** — no native object storage |
| `CloudLoadBalancer` | **validate-error** when NSX is absent |
| `CloudInterconnect` (kind != NONE) | **validate-error** — no HPC fabric |
| `CloudSharedFilesystem` (managed) | **validate-error** unless `existing_id` (NFS attach) |
| `CloudDnsRecord` | **validate-error** — vCenter has no DNS authority |
| `VPNJoinSpec` | Tailscale bootstrap via guest-customisation cloud-init |
| tags | vSphere Categories + Tags (round-trip identity) |

## See also

- [cloud-resource-model](../../../../../specs/cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../../../../../specs/cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../../../../../specs/vpn-join-spec/design.md)
- `codecraftai-interop-vsphere` — the vSphere REST client this venue consumes
