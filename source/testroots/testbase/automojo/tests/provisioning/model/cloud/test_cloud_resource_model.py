"""
    .. module:: test_cloud_resource_model
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Unit + property tests for the cloud resource model layer.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import ipaddress
import unittest

from hypothesis import given, settings, strategies as st

from ccai.provisioning.model.exceptions import (
    SchemaValidationError, SchemaSemanticError
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
from ccai.provisioning.model.cloud.cloudingressrule import CloudIngressRule
from ccai.provisioning.model.cloud.cloudegressrule import CloudEgressRule
from ccai.provisioning.model.cloud.cloudsecuritygroup import CloudSecurityGroup
from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudstoragevolume import CloudStorageVolume
from ccai.provisioning.model.cloud.cloudobjectbucket import CloudObjectBucket
from ccai.provisioning.model.cloud.cloudloadbalancer import CloudLoadBalancer
from ccai.provisioning.model.cloud.cloudloadbalancerlistener import (
    CloudLoadBalancerListener
)
from ccai.provisioning.model.cloud.storageclass import StorageClass
from ccai.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from ccai.provisioning.model.cloud.cloudresourcekind import CloudResourceKind
from ccai.provisioning.model.cloud.cloudresourceprofile import (
    CloudResourceProfile, resolve_kind, model_class_for_kind
)
from ccai.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from ccai.provisioning.model.cloud.validators import (
    cidrs_overlap, subnet_contained_in_network
)
from ccai.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec


def _basic_image() -> CloudImage:
    rtnval = CloudImage(family="ubuntu", version="24.04", architecture="x86_64")
    return rtnval


class CloudVenueTests(unittest.TestCase):

    def test_optional_fields_default(self) -> None:
        venue = CloudVenue(name="lab", provider="fake", region="r1",
                           credential="cred")
        self.assertIsNone(venue.account)
        self.assertIsNone(venue.endpoint)
        self.assertEqual(venue.settings, {})
        return

    def test_settings_default_not_shared(self) -> None:
        venue_a = CloudVenue(name="a", provider="fake", region="r1",
                             credential="cred")
        venue_b = CloudVenue(name="b", provider="fake", region="r1",
                             credential="cred")
        venue_a.settings["key"] = "value"
        self.assertEqual(venue_b.settings, {})
        return

    def test_accepts_account_endpoint_settings(self) -> None:
        venue = CloudVenue(name="azure-lab", provider="azure", region="eastus",
                           credential="azure-cred", account="sub-0001",
                           endpoint="https://vcenter.lab",
                           settings={"native_key": "native_value"})
        self.assertEqual(venue.account, "sub-0001")
        self.assertEqual(venue.endpoint, "https://vcenter.lab")
        self.assertEqual(venue.settings, {"native_key": "native_value"})
        return


class CloudNetworkTests(unittest.TestCase):

    def test_roundtrip(self) -> None:
        net = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16", region="us-east-1",
                           tags={"env": "prod"})
        as_dict = net.to_dict()
        rebuilt = CloudNetwork.from_dict(as_dict)
        self.assertEqual(net, rebuilt)
        return

    def test_rejects_bad_cidr(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudNetwork(name="vpc", cidr="not-a-cidr", region="r")
        return

    def test_rejects_empty_name(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudNetwork(name="", cidr="10.0.0.0/16", region="r")
        return

    def test_rejects_oversize_name(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudNetwork(name="a" * 64, cidr="10.0.0.0/16", region="r")
        return


class CloudSubnetTests(unittest.TestCase):

    def test_roundtrip(self) -> None:
        sub = CloudSubnet(name="sub-a", network="vpc-a", cidr="10.0.1.0/24",
                          zone="us-east-1a", public=True)
        rebuilt = CloudSubnet.from_dict(sub.to_dict())
        self.assertEqual(sub, rebuilt)
        return


class SecurityGroupTests(unittest.TestCase):

    def test_security_group_with_rules_roundtrip(self) -> None:
        ingress = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                                   source_cidrs=["0.0.0.0/0"], description="ssh")
        egress = CloudEgressRule(protocol="all", from_port=0, to_port=65535,
                                 dest_cidrs=["0.0.0.0/0"], description="all out")
        sg = CloudSecurityGroup(name="sg-a", network="vpc-a",
                                ingress_rules=[ingress], egress_rules=[egress])
        rebuilt = CloudSecurityGroup.from_dict(sg.to_dict())
        self.assertEqual(sg, rebuilt)
        return

    def test_ingress_rule_rejects_inverted_port_range(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudIngressRule(protocol="tcp", from_port=443, to_port=80,
                             source_cidrs=["0.0.0.0/0"])
        return

    def test_ingress_rule_rejects_no_source(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudIngressRule(protocol="tcp", from_port=22, to_port=22)
        return

    def test_egress_rule_rejects_no_destination(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudEgressRule(protocol="tcp", from_port=22, to_port=22)
        return


class KeyPairAndImageTests(unittest.TestCase):

    def test_keypair_rejects_empty_material(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudKeyPair(name="kp", public_key_material="")
        return

    def test_image_rejects_unknown_architecture(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            CloudImage(family="ubuntu", version="24.04", architecture="ppc64")
        return

    def test_image_rejects_unknown_family(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            CloudImage(family="gentoo", version="24.04",
                       architecture="x86_64")
        return

    def test_image_rejects_malformed_version(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            CloudImage(family="ubuntu", version="rolling",
                       architecture="x86_64")
        return

    def test_image_normalizes_family_and_architecture(self) -> None:
        img = CloudImage(family="amazonlinux", version="2",
                         architecture="amd64")
        self.assertEqual(img.family, "amazon-linux")
        self.assertEqual(img.architecture, "x86_64")
        return

    def test_image_roundtrip(self) -> None:
        img = _basic_image()
        rebuilt = CloudImage.from_dict(img.to_dict())
        self.assertEqual(img, rebuilt)
        return


class CloudInstanceTests(unittest.TestCase):

    def test_optional_slots_default_none(self) -> None:
        inst = CloudInstance(name="host-1", profile_ref="profile-a",
                             image=_basic_image(), size="m5.large",
                             subnet="sub-a")
        self.assertIsNone(inst.vpn_join)
        self.assertIsNone(inst.accelerators)
        self.assertIsNone(inst.interconnect)
        self.assertIsNone(inst.placement_group)
        self.assertIsNone(inst.shared_fs_mounts)
        self.assertEqual(inst.preemption_policy, PreemptionPolicy.FAIL.value)
        return

    def test_twingate_non_connector_fails_semantic(self) -> None:
        vpn = VPNJoinSpec(provider="twingate",
                          control_plane_credential="tw-cp",
                          hostname_template="host-{index}",
                          connector_only=True)
        # forge a non-connector spec by mutating the field after construction
        vpn.connector_only = False
        with self.assertRaises(SchemaSemanticError):
            CloudInstance(name="host-1", profile_ref="profile-a",
                          image=_basic_image(), size="m5.large",
                          subnet="sub-a", vpn_join=vpn)
        return

    def test_instance_roundtrip(self) -> None:
        inst = CloudInstance(name="host-1", profile_ref="profile-a",
                             image=_basic_image(), size="m5.large",
                             subnet="sub-a",
                             preemption_policy=PreemptionPolicy.REACQUIRE)
        rebuilt = CloudInstance.from_dict(inst.to_dict())
        self.assertEqual(inst.name, rebuilt.name)
        self.assertEqual(inst.preemption_policy, rebuilt.preemption_policy)
        self.assertEqual(inst.image, rebuilt.image)
        return


class StorageBucketLBDnsTests(unittest.TestCase):

    def test_storage_volume_rejects_zero_size(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudStorageVolume(name="v", size_gb=0, storage_class="standard")
        return

    def test_bucket_roundtrip(self) -> None:
        b = CloudObjectBucket(name="bucket-a", region="us-east-1",
                              versioning=True)
        rebuilt = CloudObjectBucket.from_dict(b.to_dict())
        self.assertEqual(b, rebuilt)
        return

    def test_lb_rejects_unknown_scheme(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudLoadBalancer(name="lb", scheme="weirdo")
        return

    def test_dns_record_rejects_unknown_type(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudDnsRecord(zone="example.com", name="www",
                           record_type="NOPE", values=["1.2.3.4"],
                           ttl_seconds=60)
        return


class StorageClassTests(unittest.TestCase):

    def test_storage_class_member_values_are_lowercase_names(self) -> None:
        for member in StorageClass:
            self.assertEqual(member.value, member.name.lower())
        return

    def test_storage_class_default_is_standard(self) -> None:
        volume = CloudStorageVolume(name="v", size_gb=10)
        self.assertEqual(volume.storage_class, StorageClass.STANDARD)
        return

    def test_volume_accepts_enum_storage_class(self) -> None:
        volume = CloudStorageVolume(name="v", size_gb=10,
                                    storage_class=StorageClass.PERFORMANCE)
        self.assertEqual(volume.storage_class, StorageClass.PERFORMANCE)
        return

    def test_volume_coerces_string_storage_class(self) -> None:
        volume = CloudStorageVolume(name="v", size_gb=10,
                                    storage_class="archive")
        self.assertEqual(volume.storage_class, StorageClass.ARCHIVE)
        return

    def test_volume_coerces_mixed_case_string(self) -> None:
        volume = CloudStorageVolume(name="v", size_gb=10,
                                    storage_class="Balanced")
        self.assertEqual(volume.storage_class, StorageClass.BALANCED)
        return

    def test_volume_rejects_unknown_storage_class_string(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            CloudStorageVolume(name="v", size_gb=10, storage_class="gp3")
        return


class CloudLoadBalancerListenerTests(unittest.TestCase):

    def test_listener_construction(self) -> None:
        listener = CloudLoadBalancerListener(protocol="HTTP", port=80,
                                             target_port=8080)
        self.assertEqual(listener.protocol, "HTTP")
        self.assertEqual(listener.port, 80)
        self.assertEqual(listener.target_port, 8080)
        self.assertIsNone(listener.tls_certificate_ref)
        return

    def test_listener_roundtrip(self) -> None:
        listener = CloudLoadBalancerListener(protocol="HTTPS", port=443,
                                             target_port=8443,
                                             tls_certificate_ref="cert-1")
        rebuilt = CloudLoadBalancerListener.from_dict(listener.to_dict())
        self.assertEqual(listener, rebuilt)
        return

    def test_listener_rejects_unknown_protocol(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudLoadBalancerListener(protocol="FTP", port=21,
                                      target_port=21)
        return

    def test_listener_rejects_out_of_range_port(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudLoadBalancerListener(protocol="TCP", port=70000,
                                      target_port=80)
        return

    def test_load_balancer_accepts_typed_listeners(self) -> None:
        listener = CloudLoadBalancerListener(protocol="TCP", port=6379,
                                             target_port=6379)
        lb = CloudLoadBalancer(name="lb-a", scheme="internal",
                               listeners=[listener])
        self.assertEqual(len(lb.listeners), 1)
        self.assertEqual(lb.listeners[0].protocol, "TCP")
        return


class VenueStorageClassMappingTests(unittest.TestCase):

    def test_aws_volume_class_mapping(self) -> None:
        from ccai.provisioning.venues.aws.resources.volumemanager import (
            map_storage_class
        )
        self.assertEqual(
            map_storage_class(storage_class=StorageClass.STANDARD), "gp3")
        self.assertEqual(
            map_storage_class(storage_class=StorageClass.BALANCED), "gp3")
        self.assertEqual(
            map_storage_class(storage_class=StorageClass.PERFORMANCE), "io2")
        self.assertEqual(
            map_storage_class(storage_class=StorageClass.ARCHIVE), "st1")
        return

    def test_azure_volume_class_mapping(self) -> None:
        from ccai.provisioning.venues.azure.resources.diskmanager import (
            map_storage_class
        )
        self.assertEqual(
            map_storage_class(storage_class=StorageClass.STANDARD),
            "StandardSSD_LRS")
        self.assertEqual(
            map_storage_class(storage_class=StorageClass.PERFORMANCE),
            "Premium_LRS")
        self.assertEqual(
            map_storage_class(storage_class=StorageClass.ARCHIVE),
            "Standard_LRS")
        return

    def test_gcp_volume_class_mapping(self) -> None:
        from ccai.provisioning.venues.google.resources.diskmanager import (
            resolve_disk_type
        )
        self.assertEqual(
            resolve_disk_type(storage_class=StorageClass.STANDARD), "pd-ssd")
        self.assertEqual(
            resolve_disk_type(storage_class=StorageClass.BALANCED),
            "pd-balanced")
        self.assertEqual(
            resolve_disk_type(storage_class=StorageClass.ARCHIVE),
            "pd-standard")
        return


class ResourceProfileTests(unittest.TestCase):

    def test_resource_profile_dispatches_to_correct_class(self) -> None:
        net_payload = {
            "name": "vpc-a", "cidr": "10.0.0.0/16", "region": "us-east-1",
            "tags": [],
        }
        prof = CloudResourceProfile(name="p-net",
                                    kind=CloudResourceKind.NETWORK,
                                    payload=net_payload)
        dispatched = prof.dispatch()
        self.assertIsInstance(dispatched, CloudNetwork)
        self.assertEqual(dispatched.name, "vpc-a")
        return

    def test_resource_profile_rejects_unknown_kind(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudResourceProfile(name="p", kind="nope")
        return

    def test_resource_profile_rejects_bad_payload(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudResourceProfile(name="p", kind="network",
                                 payload={"name": "n", "cidr": "bad",
                                          "region": "r"})
        return


# ---------------- property tests ----------------


_VALID_PROTOCOLS = ["tcp", "udp", "icmp", "all"]


@st.composite
def cidr_in_network_strategy(draw):
    base_octet = draw(st.integers(min_value=10, max_value=10))
    prefix = draw(st.integers(min_value=8, max_value=16))
    network = ipaddress.IPv4Network((base_octet << 24, prefix), strict=False)
    sub_prefix = draw(st.integers(min_value=prefix + 1, max_value=24))
    subnets = list(network.subnets(new_prefix=sub_prefix))
    pick = draw(st.integers(min_value=0, max_value=len(subnets) - 1))
    subnet = subnets[pick]
    return str(network), str(subnet)


@st.composite
def sibling_subnets_strategy(draw):
    prefix = 16
    network = ipaddress.IPv4Network((10 << 24, prefix), strict=False)
    sub_prefix = draw(st.integers(min_value=20, max_value=24))
    all_subnets = list(network.subnets(new_prefix=sub_prefix))
    n_pick = draw(st.integers(min_value=2, max_value=min(5, len(all_subnets))))
    indices = draw(st.lists(
        st.integers(min_value=0, max_value=len(all_subnets) - 1),
        min_size=n_pick, max_size=n_pick, unique=True
    ))
    chosen = [str(all_subnets[i]) for i in indices]
    return str(network), chosen


class CloudResourcePropertyTests(unittest.TestCase):

    @settings(max_examples=50, deadline=None)
    @given(cidr_in_network_strategy())
    def test_property_subnet_contained_in_network(self, pair) -> None:
        net_cidr, sub_cidr = pair
        self.assertTrue(
            subnet_contained_in_network(subnet_cidr=sub_cidr,
                                        network_cidr=net_cidr)
        )
        return

    @settings(max_examples=50, deadline=None)
    @given(sibling_subnets_strategy())
    def test_property_sibling_subnets_no_overlap(self, generated) -> None:
        _net_cidr, subs = generated
        for i in range(len(subs)):
            for j in range(i + 1, len(subs)):
                self.assertFalse(
                    cidrs_overlap(cidr_a=subs[i], cidr_b=subs[j])
                )
        return

    @settings(max_examples=50, deadline=None)
    @given(
        st.sampled_from(_VALID_PROTOCOLS),
        st.integers(min_value=0, max_value=65535),
        st.integers(min_value=0, max_value=65535),
    )
    def test_property_ingress_egress_pair_roundtrip(self, protocol, a, b) -> None:
        lo = min(a, b)
        hi = max(a, b)
        ingress = CloudIngressRule(protocol=protocol, from_port=lo, to_port=hi,
                                   source_cidrs=["10.0.0.0/8"])
        egress = CloudEgressRule(protocol=protocol, from_port=lo, to_port=hi,
                                 dest_cidrs=["10.0.0.0/8"])
        rebuilt_in = CloudIngressRule.from_dict(ingress.to_dict())
        rebuilt_out = CloudEgressRule.from_dict(egress.to_dict())
        self.assertEqual(ingress, rebuilt_in)
        self.assertEqual(egress, rebuilt_out)
        return

    def test_property_resource_profile_dispatch_total(self) -> None:
        # Every CloudResourceKind value must resolve to exactly one class.
        seen = set()
        for kind in CloudResourceKind:
            cls = model_class_for_kind(kind=resolve_kind(value=kind))
            seen.add(cls)
        self.assertEqual(len(seen), len(list(CloudResourceKind)))
        return


# Per-class builders mapping a hypothesis-drawn seed to a valid instance.
def _build_network(seed: int):
    rtnval = CloudNetwork(name="net-{}".format(seed),
                          cidr="10.{}.0.0/16".format(seed % 256),
                          region="region-{}".format(seed),
                          tags={"env": "test"})
    return rtnval


def _build_subnet(seed: int):
    rtnval = CloudSubnet(name="sub-{}".format(seed), network="net-a",
                         cidr="10.{}.1.0/24".format(seed % 256),
                         zone="zone-{}".format(seed), public=(seed % 2 == 0))
    return rtnval


def _build_ingress(seed: int):
    rtnval = CloudIngressRule(protocol="tcp", from_port=seed % 1000,
                              to_port=(seed % 1000) + 1,
                              source_cidrs=["10.0.0.0/8"],
                              description="ing-{}".format(seed))
    return rtnval


def _build_egress(seed: int):
    rtnval = CloudEgressRule(protocol="udp", from_port=seed % 1000,
                             to_port=(seed % 1000) + 1,
                             dest_cidrs=["10.0.0.0/8"],
                             description="egr-{}".format(seed))
    return rtnval


def _build_security_group(seed: int):
    rtnval = CloudSecurityGroup(name="sg-{}".format(seed), network="net-a",
                                ingress_rules=[_build_ingress(seed)],
                                egress_rules=[_build_egress(seed)])
    return rtnval


def _build_keypair(seed: int):
    rtnval = CloudKeyPair(name="kp-{}".format(seed),
                          public_key_material="ssh-ed25519 AAAAseed{}".format(seed))
    return rtnval


def _build_image(seed: int):
    rtnval = CloudImage(family="ubuntu", version="24.{}".format(seed % 12),
                        architecture="x86_64", owner="owner-{}".format(seed))
    return rtnval


def _build_instance(seed: int):
    rtnval = CloudInstance(name="inst-{}".format(seed),
                           profile_ref="prof-{}".format(seed),
                           image=_basic_image(),
                           size="size-{}".format(seed),
                           subnet="sub-a", public_ip=(seed % 2 == 0))
    return rtnval


def _build_volume(seed: int):
    rtnval = CloudStorageVolume(name="vol-{}".format(seed),
                                size_gb=(seed % 500) + 1, storage_class="standard")
    return rtnval


def _build_bucket(seed: int):
    rtnval = CloudObjectBucket(name="bkt-{}".format(seed),
                               region="region-{}".format(seed),
                               versioning=(seed % 2 == 0))
    return rtnval


def _build_load_balancer(seed: int):
    rtnval = CloudLoadBalancer(name="lb-{}".format(seed), scheme="internal",
                               target_instance_names=["inst-a"])
    return rtnval


def _build_dns_record(seed: int):
    rtnval = CloudDnsRecord(zone="example.com", name="rec-{}".format(seed),
                            record_type="A", values=["10.0.0.1"],
                            ttl_seconds=(seed % 3600) + 1)
    return rtnval


_MODEL_CLASS_BUILDERS = (
    (CloudNetwork, _build_network),
    (CloudSubnet, _build_subnet),
    (CloudIngressRule, _build_ingress),
    (CloudEgressRule, _build_egress),
    (CloudSecurityGroup, _build_security_group),
    (CloudKeyPair, _build_keypair),
    (CloudImage, _build_image),
    (CloudInstance, _build_instance),
    (CloudStorageVolume, _build_volume),
    (CloudObjectBucket, _build_bucket),
    (CloudLoadBalancer, _build_load_balancer),
    (CloudDnsRecord, _build_dns_record),
)


class AllModelClassesPropertyTests(unittest.TestCase):

    @settings(max_examples=60, deadline=None)
    @given(st.integers(min_value=0, max_value=100000))
    def test_property_all_model_classes_roundtrip(self, seed) -> None:
        # Every cloud model class must satisfy from_dict(to_dict(x)) == x.
        for model_cls, builder in _MODEL_CLASS_BUILDERS:
            original = builder(seed)
            rebuilt = model_cls.from_dict(original.to_dict())
            self.assertEqual(
                original, rebuilt,
                "{} failed round-trip for seed {}".format(
                    model_cls.__name__, seed
                )
            )
        return


class FlatDictTagsTests(unittest.TestCase):

    def test_tags_default_to_empty_dict(self) -> None:
        net = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16", region="r")
        self.assertEqual(net.tags, {})
        return

    def test_tags_accept_flat_dict(self) -> None:
        net = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16", region="r",
                           tags={"env": "lab", "team": "infra"})
        self.assertEqual(net.tags, {"env": "lab", "team": "infra"})
        return

    def test_tags_roundtrip_as_flat_dict(self) -> None:
        net = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16", region="r",
                           tags={"env": "lab"})
        rebuilt = CloudNetwork.from_dict(net.to_dict())
        self.assertEqual(rebuilt.tags, {"env": "lab"})
        return


class RuleProtocolEnumTests(unittest.TestCase):

    def test_ingress_rule_protocol_coerces_string(self) -> None:
        rule = CloudIngressRule(protocol="TCP", from_port=22, to_port=22,
                                source_cidrs=["0.0.0.0/0"])
        self.assertEqual(rule.protocol, "tcp")
        return

    def test_egress_rule_protocol_coerces_enum(self) -> None:
        from ccai.provisioning.model.cloud.networkprotocol import (
            NetworkProtocol
        )
        rule = CloudEgressRule(protocol=NetworkProtocol.ALL,
                               from_port=0, to_port=65535,
                               dest_cidrs=["0.0.0.0/0"])
        self.assertEqual(rule.protocol, "all")
        return

    def test_rule_rejects_unknown_protocol(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            CloudIngressRule(protocol="sctp", from_port=22, to_port=22,
                             source_cidrs=["0.0.0.0/0"])
        return


if __name__ == "__main__":
    unittest.main()
