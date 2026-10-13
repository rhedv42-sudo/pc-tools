"""Tests für Herstellererkennung, Zustandsberechnung, Übersetzung und Helfer-Whitelist."""
import unittest

from tests import helpers  # noqa: F401
from pctools import helper, i18n, oui
from pctools.health import compute_health


class OuiTest(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(oui.lookup("b8:27:eb:11:22:33", use_system=False), "Raspberry Pi")
        self.assertEqual(oui.lookup("38-10-D5-AA-BB-CC", use_system=False), "AVM (FRITZ!)")
        self.assertEqual(oui.lookup("00:0c:29:00:00:01", use_system=False), "VMware (virtuell)")
        self.assertEqual(oui.lookup("", use_system=False), "")
        self.assertEqual(oui.lookup("zz", use_system=False), "")

    def test_random(self):
        self.assertTrue(oui.is_random("da:a1:19:00:00:01"))
        self.assertFalse(oui.is_random("b8:27:eb:00:00:01"))

    def test_table_sane(self):
        self.assertGreater(len(oui.BUILTIN), 300)
        self.assertTrue(all(len(k) == 6 and int(k, 16) >= 0 for k in oui.BUILTIN))


class HealthTest(unittest.TestCase):
    def test_perfect(self):
        r = compute_health({"disks": [{"mount": "/", "percent": 40, "avail": 10}], "updates": 0,
                            "security_updates": 0, "failed": 0, "firewall": True, "reboot": False})
        self.assertEqual(r["score"], 100)
        self.assertEqual(r["light"], "green")
        self.assertEqual(r["findings"], [])

    def test_problems(self):
        r = compute_health({"disks": [{"mount": "/", "percent": 96, "avail": 1}, {"mount": "/home", "percent": 91, "avail": 1},
                                      {"mount": "/snap/x", "percent": 100, "avail": 0, "readonly": True}],
                            "updates": 12, "security_updates": 3, "failed": 1, "firewall": False, "reboot": True,
                            "smart": [{"device": "/dev/sda", "passed": False, "warnings": []}],
                            "mem_total": 100, "mem_available": 5, "swap_total": 100, "swap_free": 10})
        self.assertEqual(r["score"], 0)
        self.assertEqual(r["light"], "red")
        self.assertEqual(r["findings"][0]["severity"], "crit")
        self.assertFalse(any("/snap/x" in f["title"] for f in r["findings"]))

    def test_yellow(self):
        r = compute_health({"updates": 3, "firewall": False, "reboot": True, "failed": 0})
        self.assertEqual(r["score"], 100 - 3 - 10 - 10)
        self.assertEqual(r["light"], "yellow")
        r = compute_health({"updates": 1, "firewall": True, "reboot": True, "failed": 0})
        self.assertEqual((r["score"], r["light"]), (87, "green"))


class I18nTest(unittest.TestCase):
    def test_placeholders_and_fallback(self):
        i18n.set_language("xx-XX")
        self.assertEqual(i18n.current_language(), "de-DE")
        self.assertEqual(i18n.t("{0} von {1}", 1, 2), "1 von 2")
        self.assertEqual(i18n.t("Text {0} {5}", "a"), "Text a {5}")

    def test_lang_files(self):
        import json
        d = i18n.lang_dir()
        for code, _ in i18n.LANGUAGES:
            data = json.loads((d / ("%s.json" % code)).read_text(encoding="utf-8"))
            self.assertIn("meta", data)
            self.assertIn("strings", data)
        i18n.set_language("en-US")          # leere Übersetzungen -> Deutsch
        self.assertEqual(i18n.t("Übersicht") in ("Übersicht", "Overview"), True)
        i18n.set_language("de-DE")


class HelperWhitelistTest(unittest.TestCase):
    def test_rejects(self):
        for argv in ([], ["rm", "-rf", "/"], ["restart-unit", "a;reboot.service"], ["restart-unit", "x.service", "y"],
                     ["restart-unit", "x.service\n"], ["clean", "pkgcache", "home"], ["upgrade", "everything"],
                     ["refresh", "extra"], ["smart", "/dev/sda"]):
            self.assertIsNone(helper.resolve(argv), argv)

    def test_accepts(self):
        for argv in (["refresh"], ["upgrade", "system", "snap"], ["clean", "journal"], ["maintain"],
                     ["restart-unit", "cups.service"], ["smart"], ["enable-ufw"], ["enable-fstrim"]):
            self.assertTrue(callable(helper.resolve(argv)), argv)

    def test_main_rejects_without_running(self):
        self.assertEqual(helper.main(["bogus"]), 2)


if __name__ == "__main__":
    unittest.main()
