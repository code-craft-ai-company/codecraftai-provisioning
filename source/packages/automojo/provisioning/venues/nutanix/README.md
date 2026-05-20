# Nutanix AHV Provisioning Venue

`NutanixCloudProvisioner` realises the neutral cloud resource model on a
Nutanix AHV cluster fronted by Prism Central, through the v3 REST API
surfaced by [`automojo-interop-nutanix`](../../../../../../../automojo-interop-nutanix).

## Lifecycle

The venue implements the five-verb
[`CloudProvisioner` lifecycle](../../../../../../specs/cloud-provisioner-lifecycle/design.md):
`validate`, `plan`, `apply`, `destroy`, `inventory`.  Every method accepts
an `aspects` bundle and propagates it to the interop client; mutating
Prism calls return an `ergon` task handle that is awaited via its poll
loop with the supplied aspect timeouts.

## Mapping

| Neutral model | Nutanix primitive | Notes |
| --- | --- | --- |
| `CloudNetwork` | Flow VPC | `POST /vpcs` |
| `CloudSubnet` | Prism subnet (VLAN) | `cidr` → `ip_config` |
| `CloudSecurityGroup` | Flow security policy | rule-set keyed by name |
| `CloudKeyPair` | cloud-init `ssh_authorized_keys` | injected into `user_data` |
| `CloudImage` | registered Prism image | resolved by catalog name |
| `CloudInstance` | VM cloned from image | `size` → vCPU/RAM via the resolver |
| `CloudStorageVolume` | volume group | `size_gb` → `disk_size_mib` |
| `VPNJoinSpec` | base64 `guest_customization.cloud_init.user_data` | rendered by the [M6 cloud-init renderer](../../cloudinit/vpncloudinitrenderer.py) |
| Tags | Prism Categories + Values | round-trip identity |
| `CloudObjectBucket` | Nutanix Objects (extension) | `validate`-error unless configured |
| `CloudLoadBalancer` | unsupported | `validate`-error |
| `CloudDnsRecord` | unsupported | `validate`-error |
| `CloudSharedFilesystem` | Nutanix Files share | attach-only (`existing_id` required) |

## Idempotency and ownership

Every venue-side entity carries a stable `<spec-name>-<run-id-short>`
name and the `automojo-run-id` Prism Category.  Plan lists resources by
name; apply is read-before-create; destroy reverses apply and is gated
by `aspects.confirm`.  VPN-joined VMs are de-registered from the VPN
control plane on destroy via `IVPNControlPlane.delete_device`.

## See also

- [cloud-resource-model](../../../../../../specs/cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../../../../../../specs/cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../../../../../../specs/vpn-join-spec/design.md)
- `automojo-interop-nutanix/Agents.md`
