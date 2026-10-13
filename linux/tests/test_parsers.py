"""Tests der Parser für Systemausgaben (ohne echte Systemaufrufe)."""
import json
import unittest

from tests import helpers  # noqa: F401  (setzt sys.path)
from pctools import cleanup, network, security, services, sysinfo, updates
from pctools.autostart import is_enabled, parse_desktop, set_line


class OsReleaseTest(unittest.TestCase):
    def test_ubuntu(self):
        text = 'NAME="Ubuntu"\nVERSION_ID="24.04"\nID=ubuntu\nID_LIKE=debian\nPRETTY_NAME="Ubuntu 24.04.1 LTS"\n# Kommentar\n'
        osr = sysinfo.parse_os_release(text)
        self.assertEqual(osr["ID"], "ubuntu")
        self.assertEqual(osr["PRETTY_NAME"], "Ubuntu 24.04.1 LTS")
        self.assertEqual(sysinfo.distro_family(osr), "debian")

    def test_families(self):
        cases = {'ID=fedora\n': "fedora", 'ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n': "suse",
                 'ID=arch\n': "arch", 'ID=linuxmint\nID_LIKE="ubuntu debian"\n': "debian",
                 'ID=endeavouros\nID_LIKE=arch\n': "arch", 'ID=rocky\nID_LIKE="rhel centos fedora"\n': "fedora",
                 'ID=gentoo\n': "unknown"}
        for text, fam in cases.items():
            self.assertEqual(sysinfo.distro_family(sysinfo.parse_os_release(text)), fam, text)

    def test_escaped_quotes(self):
        osr = sysinfo.parse_os_release('PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nBROKEN="abc\n')
        self.assertEqual(osr["PRETTY_NAME"], "Debian GNU/Linux 12 (bookworm)")
        self.assertIn("BROKEN", osr)


class DfTest(unittest.TestCase):
    DF = """Filesystem     Type     1-blocks         Used    Available Capacity Mounted on
/dev/nvme0n1p2 ext4  500107862016 460000000000  40107862016      92% /
tmpfs          tmpfs   8000000000      1000000   7999000000       1% /run
/dev/nvme0n1p1 vfat     536870912     6291456    530579456       2% /boot/efi
/dev/sdb1      btrfs 2000000000000 100000000000 1900000000000      5% /mnt/Meine Daten
"""

    def test_parse(self):
        rows = sysinfo.parse_df(self.DF)
        self.assertEqual(len(rows), 3)                 # tmpfs wird ausgelassen
        self.assertEqual(rows[0]["mount"], "/")
        self.assertEqual(rows[0]["percent"], 92)
        self.assertEqual(rows[2]["mount"], "/mnt/Meine Daten")
        self.assertEqual(rows[2]["fstype"], "btrfs")

    def test_garbage(self):
        self.assertEqual(sysinfo.parse_df(""), [])
        self.assertEqual(sysinfo.parse_df("header\nkaputt"), [])


class LsblkTest(unittest.TestCase):
    def test_tree(self):
        data = {"blockdevices": [{"name": "nvme0n1", "type": "disk", "size": 512110190592, "children": [
            {"name": "nvme0n1p1", "type": "part", "fstype": "vfat", "mountpoint": "/boot/efi"},
            {"name": "nvme0n1p2", "type": "part", "fstype": "crypto_LUKS", "mountpoint": None, "children": [
                {"name": "luks-abc", "type": "crypt", "fstype": "btrfs", "mountpoint": "/"}]}]}]}
        devs = sysinfo.parse_lsblk_json(json.dumps(data))
        self.assertEqual([d["name"] for d in devs], ["nvme0n1", "nvme0n1p1", "nvme0n1p2", "luks-abc"])
        self.assertEqual(devs[3]["parent"], "nvme0n1p2")
        self.assertEqual(devs[3]["depth"], 2)
        self.assertEqual(sysinfo.parse_lsblk_json("kein json"), [])


class UpdatesTest(unittest.TestCase):
    def test_apt(self):
        text = """Listing...
firefox/jammy-updates,jammy-security 120.0+build2-0ubuntu0.22.04.1 amd64 [upgradable from: 119.0+build2-0ubuntu0.22.04.1]
libc6/noble-updates 2.39-0ubuntu8.3 amd64 [upgradable from: 2.39-0ubuntu8.2]
WARNING: apt does not have a stable CLI interface.
"""
        pkgs = updates.parse_apt_upgradable(text)
        self.assertEqual(len(pkgs), 2)
        self.assertEqual(pkgs[0]["name"], "firefox")
        self.assertTrue(pkgs[0]["security"])
        self.assertFalse(pkgs[1]["security"])
        self.assertEqual(pkgs[1]["old"], "2.39-0ubuntu8.2")

    def test_dnf(self):
        text = """Last metadata expiration check: 0:10:22 ago on Mon 13 Oct 2026.

kernel.x86_64                    6.11.4-301.fc41          updates
firefox.x86_64                   131.0.3-1.fc41           updates
a-very-long-package-name-that-wraps.noarch
                                 1.2.3-1.fc41             updates
Obsoleting Packages
grub2-tools.x86_64               1:2.06-1                 updates
"""
        pkgs = updates.parse_dnf_check_update(text)
        self.assertEqual([p["name"] for p in pkgs], ["kernel", "firefox", "a-very-long-package-name-that-wraps"])
        self.assertEqual(pkgs[0]["new"], "6.11.4-301.fc41")

    def test_zypper(self):
        text = """S | Repository     | Name | Current Version | Available Version | Arch
--+----------------+------+-----------------+-------------------+-------
v | Main Update    | curl | 8.0-1.1         | 8.1-1.1           | x86_64
"""
        pkgs = updates.parse_zypper_lu(text)
        self.assertEqual(pkgs, [{"name": "curl", "new": "8.1-1.1", "old": "8.0-1.1", "repo": "Main Update", "security": False}])

    def test_pacman(self):
        pkgs = updates.parse_pacman_updates("linux 6.11.1.arch1-1 -> 6.11.2.arch1-1\nfirefox 130.0-1 -> 131.0-1\n")
        self.assertEqual(len(pkgs), 2)
        self.assertEqual(pkgs[0]["new"], "6.11.2.arch1-1")

    def test_flatpak_snap(self):
        self.assertEqual(updates.parse_flatpak_updates("org.gimp.GIMP\t2.10.38\tflathub\n")[0]["name"], "org.gimp.GIMP")
        snap = "Name     Version  Rev   Size   Publisher  Notes\nfirefox  131.0    5000  280MB  mozilla**  -\n"
        self.assertEqual(updates.parse_snap_refresh_list(snap)[0]["new"], "131.0")
        self.assertEqual(updates.parse_snap_refresh_list("All snaps up to date."), [])


class CleanupTest(unittest.TestCase):
    def test_apt_autoremove(self):
        text = "NOTE: This is only a simulation!\nRemv linux-image-6.8.0-40-generic [6.8.0-40.40]\nRemv libfoo1 [1.0]\n"
        self.assertEqual(cleanup.parse_apt_autoremove(text), ["linux-image-6.8.0-40-generic", "libfoo1"])

    def test_snap_disabled(self):
        text = "Name  Version Rev  Tracking  Publisher Notes\ncore  16-2.61 16928 latest/stable canonical** core,disabled\ncore  16-2.62 17200 latest/stable canonical** core\n"
        self.assertEqual(cleanup.parse_snap_disabled(text), [("core", "16928")])


class SsTest(unittest.TestCase):
    TEXT = """Netid State  Recv-Q Send-Q Local Address:Port  Peer Address:Port Process
udp   UNCONN 0      0      127.0.0.53%lo:53         0.0.0.0:*     users:(("systemd-resolve",pid=600,fd=13))
udp   UNCONN 0      0            0.0.0.0:5353       0.0.0.0:*
tcp   LISTEN 0      4096         0.0.0.0:22         0.0.0.0:*     users:(("sshd",pid=900,fd=3))
tcp   LISTEN 0      4096            [::]:22            [::]:*     users:(("sshd",pid=900,fd=4))
tcp   LISTEN 0      511        127.0.0.1:631        0.0.0.0:*
tcp   ESTAB  0      0        192.168.1.5:40000   1.2.3.4:443
"""

    def test_parse(self):
        ports = security.parse_ss(self.TEXT)
        by_port = {(p["proto"], p["port"]): p for p in ports}
        self.assertTrue(by_port[("tcp", 22)]["public"])
        self.assertEqual(by_port[("tcp", 22)]["process"], "sshd")
        self.assertFalse(by_port[("tcp", 631)]["public"])
        self.assertFalse(by_port[("udp", 53)]["public"])
        self.assertNotIn(("tcp", 40000), by_port)
        self.assertEqual(sum(1 for p in ports if p["port"] == 22), 1)   # IPv4/IPv6 zusammengefasst


class SshdTest(unittest.TestCase):
    def test_first_wins(self):
        conf = security.parse_sshd_config(["PasswordAuthentication no\n", "PermitRootLogin yes\nPasswordAuthentication yes\nMatch User x\nPermitRootLogin no\n"])
        self.assertEqual(conf["passwordauthentication"], "no")
        self.assertEqual(conf["permitrootlogin"], "yes")


class ServicesTest(unittest.TestCase):
    def test_failed(self):
        text = "cups.service loaded failed failed CUPS Scheduler\n● bad@x.service loaded failed failed Bad\nkaputt\n"
        units = services.parse_failed(text)
        self.assertEqual([u["unit"] for u in units], ["cups.service", "bad@x.service"])
        self.assertEqual(units[0]["description"], "CUPS Scheduler")

    def test_unit_pattern(self):
        self.assertTrue(services.UNIT_RX.fullmatch("NetworkManager-wait-online.service"))
        for bad in ("a;b.service", "x.service\n", "-x.service", "../x.service", "x.socket"):
            self.assertIsNone(services.UNIT_RX.fullmatch(bad), bad)


class NetworkParseTest(unittest.TestCase):
    def test_ping(self):
        text = "3 packets transmitted, 3 received, 0% packet loss, time 2003ms\nrtt min/avg/max/mdev = 0.410/0.523/0.700/0.120 ms\n"
        self.assertEqual(network.parse_ping(text), {"sent": 3, "received": 3, "avg_ms": 0.523})
        self.assertEqual(network.parse_ping("")["received"], 0)

    def test_neigh(self):
        data = [{"dst": "192.168.1.1", "lladdr": "38:10:D5:00:00:01", "state": ["REACHABLE"]},
                {"dst": "192.168.1.9", "state": ["FAILED"]},
                {"dst": "192.168.1.7", "lladdr": "aa:bb:cc:dd:ee:ff", "state": ["INCOMPLETE"]}]
        self.assertEqual(network.parse_ip_neigh_json(json.dumps(data)), {"192.168.1.1": "38:10:d5:00:00:01"})

    def test_proc_arp(self):
        text = ("IP address       HW type     Flags       HW address            Mask     Device\n"
                "192.168.1.1      0x1         0x2         b8:27:eb:12:34:56     *        eth0\n"
                "192.168.1.50     0x1         0x0         00:00:00:00:00:00     *        eth0\n")
        self.assertEqual(network.parse_proc_arp(text), {"192.168.1.1": "b8:27:eb:12:34:56"})

    def test_nmcli_split(self):
        self.assertEqual(network.split_nmcli(r"yes:Mein\:WLAN:80:6:130 Mbit/s:WPA2"),
                         ["yes", "Mein:WLAN", "80", "6", "130 Mbit/s", "WPA2"])

    def test_guess_and_findings(self):
        self.assertEqual(network.guess_type([9100, 80], ""), "Drucker")
        self.assertEqual(network.guess_type([80], "AVM (FRITZ!)", is_gateway=True), "Router / Gateway")
        h = {"ports": [23, 21, 445], "smb1": True, "type": "", "is_gateway": False}
        sev = sorted(f["severity"] for f in network.host_findings(h))
        self.assertEqual(sev, ["crit", "crit", "warn"])

    def test_report_escapes(self):
        res = {"network": "192.168.1.0/24", "gateway": "192.168.1.1", "time": 0, "devices": [
            {"ip": "192.168.1.2", "hostname": "<script>x</script>", "type": "PC", "mac": "", "vendor": "",
             "ports": [22], "smb1": False, "findings": []}]}
        html = network.report_html(res)
        self.assertNotIn("<script>x", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("@media print", html)


class AutostartTest(unittest.TestCase):
    def test_desktop(self):
        text = "[Desktop Entry]\nName=Test\nExec=test --x\nX-GNOME-Autostart-enabled=false\n[Desktop Action new]\nName=Other\n"
        e = parse_desktop(text)
        self.assertEqual(e["Name"], "Test")
        self.assertFalse(is_enabled(e))
        out = set_line(text, "Hidden", "true")
        self.assertIn("Hidden=true\n[Desktop Action new]", out)
        self.assertTrue(set_line(out, "Hidden", "false").count("Hidden=") == 1)


if __name__ == "__main__":
    unittest.main()
