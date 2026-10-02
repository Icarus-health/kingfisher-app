"""Exercise fail-closed input handling without requesting calendar permission."""
import json
from pathlib import Path
import subprocess
import unittest


class CalendarReaderTests(unittest.TestCase):
    def test_rejects_writes_missing_selection_and_unbounded_windows(self):
        binary = Path(__file__).resolve().parents[1] / "build/kingfisher-calendar"
        cases = [
            ("delete", {}), ("events", {}),
            ("events", {"calendar_ids": [], "start": "2026-09-07T00:00:00Z",
                        "end": "2026-09-08T00:00:00Z"}),
            ("events", {"calendar_ids": ["synthetic"], "start": "2026-09-07T00:00:00Z",
                        "end": "2027-09-08T00:00:00Z"}),
        ]
        for command, payload in cases:
            with self.subTest(command=command, payload=payload):
                result = subprocess.run([str(binary), command], input=json.dumps(payload),
                                        text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(json.loads(result.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
