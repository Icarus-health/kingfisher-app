"""Fail-closed-Eingaben des Fahrzeit-Adapters, ohne Netz und ohne Kartenabfrage.

UNGEPRÜFT auf einem Mac: Ohne gebaute Datei (`bash scripts/build_route_reader.sh`) werden die Fälle übersprungen.
"""
import json
import subprocess
import unittest
from pathlib import Path

BINARY = Path(__file__).resolve().parents[1] / "build/kingfisher-route"


@unittest.skipUnless(BINARY.is_file(), "build/kingfisher-route ist nicht gebaut")
class RouteReaderTests(unittest.TestCase):
    def test_rejects_other_commands_and_incomplete_input(self):
        cases = [
            ("delete", {}), ("route", {}), ("route", {"von": "", "nach": "Mainz", "verkehrsmittel": "auto"}),
            ("route", {"von": "Wiesbaden", "nach": "Mainz", "verkehrsmittel": "rakete"}),
            ("route", {"von": "x" * 400, "nach": "Mainz", "verkehrsmittel": "auto"}),
        ]
        for command, payload in cases:
            with self.subTest(command=command, payload=payload):
                result = subprocess.run([str(BINARY), command], input=json.dumps(payload),
                                        text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(json.loads(result.stdout)["ok"])
                self.assertNotIn("Wiesbaden", result.stdout)


if __name__ == "__main__":
    unittest.main()
