import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from creation_pipeline.runtime import planner


class PlannerFixtureBytesTests(unittest.TestCase):
    def test_model_material_preserves_crlf_bytes_corresponding_to_inventory_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'source'; source.mkdir()
            raw=b'CCO\r\n'
            (source/'fixture.smi').write_bytes(raw)
            response={'action':'read','requested_files':['fixture.smi'],'reason':'repeat known read'}
            with patch.object(planner.model_call,'call',return_value=(response,{})) as model:
                with self.assertRaises(planner.PlanningError):
                    planner.plan(source,{'script':'fixture.smi'},root/'audit',planner.options({}),None)
            prompt=model.call_args.args[0]
            self.assertIn(json.dumps(raw.decode('utf-8')),prompt)
            inventory=json.loads((root/'audit/inventory.json').read_text())
            self.assertEqual(inventory['files']['fixture.smi']['sha256'],hashlib.sha256(raw).hexdigest())
            metadata=json.loads((root/'audit/materials.json').read_text())
            self.assertEqual(metadata['used_chars'],len(raw.decode('utf-8')))
