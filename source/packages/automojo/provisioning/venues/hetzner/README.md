# Hetzner Cloud Venue

`HetznerCloudProvisioner` realises the venue-neutral cloud resource model on
Hetzner Cloud through the `hcloud` SDK.  It is a concrete
`CloudProvisioner` and implements the five-verb lifecycle:
`validate / plan / apply / destroy / inventory`.

## Cross-references

- Resource model — `specs/cloud-resource-model/design.md`
- Provisioner lifecycle — `specs/cloud-provisioner-lifecycle/design.md`
- VPN join spec — `specs/vpn-join-spec/design.md`
- Hetzner credential — `automojo-credentials` `HetznerApiTokenCredential`

## Mapping

| Neutral model        | Hetzner resource | Notes                                  |
| -------------------- | ---------------- | -------------------------------------- |
| `CloudNetwork`       | Network          | `cidr` -> `ip_range`.                  |
| `CloudSubnet`        | Subnet on Network| `cidr` -> `ip_range`.                  |
| `CloudSecurityGroup` | Firewall         | ingress rules -> firewall rules.       |
| `CloudKeyPair`       | SSH Key          | dedup by name.                         |
| `CloudInstance`      | Server           | `size` -> server-type slug.            |
| `CloudStorageVolume` | Volume           | attach-after-create.                   |
| `CloudDnsRecord`     | Hetzner DNS      | zone resolved by `zone`.               |
| `VPNJoinSpec`        | cloud-init       | rendered into Server `user_data`.      |
| Tags                 | Hetzner labels   | round-trip identity for conformant in. |

## Honest gaps (validate-errors)

- `CloudObjectBucket` — Hetzner Cloud has no S3-class object storage.
- `CloudInterconnect(kind != NONE)` — no HPC interconnect fabric.
- `CloudSharedFilesystem(kind in {LUSTRE,WEKA,VAST,GPFS,EFS,FILESTORE})` —
  no managed WEKA/Lustre-class shared filesystem.

## Testing

The `hcloud` SDK is imported lazily.  Unit tests inject a `MockHetznerClient`
through the `client` constructor argument and never reach the real API.
Live runs are gated by `RUN_LIVE_HETZNER=1`.
