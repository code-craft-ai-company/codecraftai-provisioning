# Vultr Cloud Provisioner

`VultrCloudProvisioner` realises the neutral cloud-resource model on Vultr.

Vultr publishes a clean REST API at `https://api.vultr.com/v2` and has no
first-party Python SDK, so the venue calls the API directly via `requests`
with Bearer authentication (the same direct-API pattern the AWS venue uses
with `boto3`).  There is no separate interop package.

## Mapping

| Neutral model        | Vultr resource              |
| -------------------- | --------------------------- |
| `CloudNetwork`       | VPC 2.0 (`/vpc2`)           |
| `CloudSubnet`        | folded into VPC 2.0         |
| `CloudSecurityGroup` | Firewall Group + rules      |
| `CloudKeyPair`       | SSH Key (`/ssh-keys`)       |
| `CloudImage`         | OS id resolved via `/os`    |
| `CloudInstance`      | Instance (`/instances`)     |
| `CloudInstance.accelerators` | Cloud GPU plan id   |
| `CloudStorageVolume` | Block Storage (`/blocks`)   |
| `CloudObjectBucket`  | Object Storage subscription |
| `CloudDnsRecord`     | Domain record               |
| `VPNJoinSpec`        | base64 `user_data`          |
| Tags                 | `["key=value", ...]` strings |

## Unsupported

- `CloudInterconnect(kind != NONE)` — Vultr has no HPC interconnect; rejected
  at `validate`.
- `CloudSharedFilesystem` of the WEKA/Lustre class — rejected at `validate`.

## Lifecycle

`validate` / `plan` / `apply` / `destroy` / `inventory`.  Apply runs
VPC → Firewall → SSH Key → Instance → Block Storage → Object Storage → DNS;
destroy reverses that order and de-registers VPN devices through the optional
`IVPNControlPlane`.  All reads are owner-tagged read-before-create so
`apply ∘ apply` is the identity.

## See Also

- [cloud resource model](../../model/cloud/)
- [cloud-init renderer (vpn-join)](../../cloudinit/vpncloudinitrenderer.py)
- `codecraftai-credentials` — `VultrApiKeyCredential`
