"""
    .. module:: test_venue_python_env_wiring
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Proves every venue user-data renderer honours
               ``CloudInstance.python_environments`` through the shared
               bootstrap composer, and still passes a raw script through.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import base64
import unittest

import yaml

from ccai.interfaces.pythonenvspec import PythonEnvironmentSpec
from ccai.interfaces.vpnjoinspec import VPNJoinSpec

from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair

from ccai.provisioning.venues.crusoe.crusoeuserdatarenderer import CrusoeUserDataRenderer
from ccai.provisioning.venues.digitalocean.douserdatarenderer import DoUserDataRenderer
from ccai.provisioning.venues.equinix_metal.metaluserdatarenderer import MetalUserDataRenderer
from ccai.provisioning.venues.hetzner.hetzneruserdatarenderer import HetznerUserDataRenderer
from ccai.provisioning.venues.hyperv.hvcloudinitrenderer import HvCloudInitRenderer
from ccai.provisioning.venues.lambdalabs.lluserdatarenderer import LlUserDataRenderer
from ccai.provisioning.venues.libvirt.lvseedisobuilder import LvSeedIsoBuilder
from ccai.provisioning.venues.linode.linodeuserdatarenderer import LinodeUserDataRenderer
from ccai.provisioning.venues.nebius.nebiususerdatarenderer import NebiusUserDataRenderer
from ccai.provisioning.venues.nutanix.ntxcloudinitrenderer import NtxCloudInitRenderer
from ccai.provisioning.venues.proxmox.pvecloudinitrenderer import PveCloudInitRenderer
from ccai.provisioning.venues.vsphere.vsguestcustomrenderer import VsGuestCustomRenderer
from ccai.provisioning.venues.vultr.vultruserdatarenderer import VultrUserDataRenderer
from ccai.provisioning.venues.xcpng.xencloudinitrenderer import XenCloudInitRenderer


_SCRIPT_PATH = "/etc/ccai/python-env/opt-venvs-app.sh"


def _spec() -> PythonEnvironmentSpec:
    rtnval = PythonEnvironmentSpec(path="/opt/venvs/app", packages=["rich>=13"])
    return rtnval


def _instance(**overrides) -> CloudInstance:
    kwargs = {
        "name": "agent-01", "profile_ref": "profile",
        "image": CloudImage(family="ubuntu", version="24.04", architecture="x86_64"),
        "size": "general.small", "subnet": "subnet", "keypair": "kp",
    }
    kwargs.update(overrides)
    rtnval = CloudInstance(**kwargs)
    return rtnval


def _vpn() -> VPNJoinSpec:
    rtnval = VPNJoinSpec(provider="tailscale", control_plane_credential="ts",
                         hostname_template="{instance_name}", advertise_tags=["tag:lab"])
    return rtnval


def _parsed(document: str) -> dict:
    assert document.startswith("#cloud-config"), document[:40]
    rtnval = yaml.safe_load(document)
    return rtnval


def _assert_python_wired(case: unittest.TestCase, parsed: dict) -> None:
    case.assertIn("python3-venv", parsed["packages"])
    case.assertIn([_SCRIPT_PATH], parsed["runcmd"])
    case.assertIn(_SCRIPT_PATH, [w["path"] for w in parsed["write_files"]])
    return


class SimpleRendererWiringTests(unittest.TestCase):
    """
        Renderers that return a ``#cloud-config`` string (or "" / None).
    """

    def _render_all(self, instance: CloudInstance, authkey: str = "") -> dict:
        rtnval = {
            "crusoe": CrusoeUserDataRenderer().render(instance=instance, authkey=authkey),
            "digitalocean": DoUserDataRenderer().render(instance=instance, authkey=authkey),
            "equinix": MetalUserDataRenderer().render(instance=instance, authkey=authkey),
            "hetzner": HetznerUserDataRenderer.render(instance=instance, authkey=authkey),
            "lambdalabs": LlUserDataRenderer().render(
                instance=instance, authkey=authkey, rendered_hostname=instance.name),
            "nebius": NebiusUserDataRenderer().render(instance=instance, authkey=authkey),
            "vultr": VultrUserDataRenderer().render_body(instance=instance, authkey=authkey),
            "xcpng": XenCloudInitRenderer()._user_data_body(
                spec_vm=instance, vpn_join=instance.vpn_join, authkey=authkey,
                rendered_hostname=instance.name),
        }
        return rtnval

    def test_python_environments_reach_every_simple_renderer(self) -> None:
        outputs = self._render_all(_instance(python_environments=[_spec()]))
        for venue, document in outputs.items():
            with self.subTest(venue=venue):
                _assert_python_wired(self, _parsed(document))
        return

    def test_raw_script_alone_still_passes_through_verbatim(self) -> None:
        outputs = self._render_all(_instance(user_data_script="#!/bin/sh\necho hi"))
        for venue, document in outputs.items():
            with self.subTest(venue=venue):
                self.assertEqual(document, "#!/bin/sh\necho hi")
        return

    def test_nothing_declared_yields_empty_or_none(self) -> None:
        outputs = self._render_all(_instance())
        for venue, document in outputs.items():
            with self.subTest(venue=venue):
                self.assertIn(document, ("", None))
        return

    def test_vpn_python_and_script_compose_in_order(self) -> None:
        instance = _instance(vpn_join=_vpn(), python_environments=[_spec()],
                             user_data_script="echo done")
        outputs = self._render_all(instance, authkey="tskey-x")
        for venue, document in outputs.items():
            with self.subTest(venue=venue):
                parsed = _parsed(document)
                runcmd = parsed["runcmd"]
                self.assertIn(["/etc/tailscale/bringup.sh"], runcmd)
                self.assertLess(runcmd.index(["/etc/tailscale/bringup.sh"]),
                                runcmd.index([_SCRIPT_PATH]))
                self.assertEqual(runcmd[-1], ["sh", "-c", "echo done"])
        return


class LinodeWiringTests(unittest.TestCase):

    def test_render_instance_encodes_python_environments(self) -> None:
        encoded = LinodeUserDataRenderer().render_instance(
            instance=_instance(python_environments=[_spec()]))
        document = base64.b64decode(encoded).decode("utf-8")
        _assert_python_wired(self, _parsed(document))
        return

    def test_render_instance_none_when_nothing_declared(self) -> None:
        self.assertIsNone(LinodeUserDataRenderer().render_instance(instance=_instance()))
        return


class DocumentBuilderWiringTests(unittest.TestCase):
    """
        Renderers that own a document (hostname, ssh keys) and merge the
        bootstrap fragment into it.
    """

    def test_libvirt_seed_iso_merges_python_fragment(self) -> None:
        keypair = CloudKeyPair(name="kp", public_key_material="ssh-ed25519 AAAA test")
        document = LvSeedIsoBuilder().render_user_data(
            instance=_instance(python_environments=[_spec()]),
            keypairs=[keypair], authkey="", rendered_hostname="agent-01")
        parsed = _parsed(document)
        _assert_python_wired(self, parsed)
        self.assertEqual(parsed["hostname"], "agent-01")
        self.assertEqual(parsed["ssh_authorized_keys"], ["ssh-ed25519 AAAA test"])
        return

    def test_nutanix_merges_python_fragment_and_raw_script(self) -> None:
        encoded = NtxCloudInitRenderer().render(
            instance=_instance(python_environments=[_spec()], user_data_script="echo hi"),
            keypairs=[], authkey="", rendered_hostname="agent-01")
        parsed = _parsed(base64.b64decode(encoded).decode("utf-8"))
        _assert_python_wired(self, parsed)
        self.assertEqual(parsed["runcmd"][-1], ["sh", "-c", "echo hi"])
        return

    def test_nutanix_raw_script_only_keeps_previous_shape(self) -> None:
        encoded = NtxCloudInitRenderer().render(
            instance=_instance(user_data_script="echo hi"),
            keypairs=[], authkey="", rendered_hostname="agent-01")
        parsed = _parsed(base64.b64decode(encoded).decode("utf-8"))
        self.assertEqual(parsed["runcmd"], [["sh", "-c", "echo hi"]])
        self.assertNotIn("packages", parsed)
        return

    def test_proxmox_body_merges_python_fragment(self) -> None:
        keypair = CloudKeyPair(name="kp", public_key_material="ssh-ed25519 AAAA test")
        body = PveCloudInitRenderer.render_body(
            instance=_instance(python_environments=[_spec()]),
            keypairs=[keypair], rendered_hostname="agent-01", authkey="")
        parsed = _parsed(body)
        _assert_python_wired(self, parsed)
        self.assertEqual(parsed["ssh_authorized_keys"], ["ssh-ed25519 AAAA test"])
        return

    def test_proxmox_raw_script_only_keeps_bash_runcmd(self) -> None:
        body = PveCloudInitRenderer.render_body(
            instance=_instance(user_data_script="echo hi"),
            keypairs=[], rendered_hostname="agent-01", authkey="")
        parsed = _parsed(body)
        self.assertEqual(parsed["runcmd"], [["bash", "-c", "echo hi"]])
        return

    def test_proxmox_nothing_declared_yields_none(self) -> None:
        body = PveCloudInitRenderer.render_body(
            instance=_instance(), keypairs=[], rendered_hostname="agent-01", authkey="")
        self.assertIsNone(body)
        return

    def test_vsphere_linux_user_data_merges_python_fragment(self) -> None:
        customization = VsGuestCustomRenderer().render(
            instance=_instance(python_environments=[_spec()]))
        parsed = _parsed(customization.cloud_init_user_data)
        _assert_python_wired(self, parsed)
        return

    def test_hyperv_build_iso_merges_python_fragment(self) -> None:
        payload = HvCloudInitRenderer().build_iso(
            instance_name="agent-01", image_family="ubuntu", ssh_keys=[],
            user_data="echo hi", python_environments=[_spec()])
        parsed = _parsed(payload.iso_files["user-data"])
        _assert_python_wired(self, parsed)
        self.assertEqual(parsed["runcmd"][-1], ["sh", "-c", "echo hi"])
        self.assertTrue(parsed["package_update"])
        return

    def test_hyperv_build_iso_without_python_has_no_packages_key(self) -> None:
        payload = HvCloudInitRenderer().build_iso(
            instance_name="agent-01", image_family="ubuntu", ssh_keys=["k"])
        parsed = _parsed(payload.iso_files["user-data"])
        self.assertNotIn("packages", parsed)
        return


if __name__ == "__main__":
    unittest.main()
