"""Modellprüfung liest keine Transkripte und akzeptiert keine Teilmodelle."""
from pathlib import Path
import tempfile
import unittest
from discover_mac import whisper_models


class DiscoveryTests(unittest.TestCase):
    def test_complete_partial_and_unrelated_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            complete = root / 'whisperkit/models/argmaxinc/whisperkit-coreml/complete'
            partial = root / 'whisperkit/models/argmaxinc/whisperkit-coreml/partial'
            for name in ('AudioEncoder', 'TextDecoder', 'MelSpectrogram'):
                (complete / (name + '.mlmodelc')).mkdir(parents=True)
            (partial / 'AudioEncoder.mlmodelc').mkdir(parents=True)
            (root / 'RecordedMeetings/private.mlmodelc').mkdir(parents=True)
            models = {item['name']: item for item in whisper_models(root)}
            self.assertEqual(set(models), {'complete', 'partial'})
            self.assertTrue(models['complete']['components_present'])
            self.assertFalse(models['partial']['components_present'])

    def test_missing_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(whisper_models(Path(directory) / 'missing'), [])
