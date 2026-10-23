"""Report JSON must survive a Windows GBK stdout, including arbitrary Docker logs."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_runtime
import validate_runtime


class RuntimeCLIEncodingTests(unittest.TestCase):
    def capture_gbk(self, module, operation, argv, report):
        output = io.BytesIO()
        stream = io.TextIOWrapper(output, encoding="gbk")
        try:
            with patch('delivery.evaluate',return_value={'delivery_accepted':True}), patch.object(module, operation, return_value=report), patch("sys.argv", argv), contextlib.redirect_stdout(stream):
                self.assertEqual(module.main(), 0)
            stream.flush()
            self.assertEqual(json.loads(output.getvalue().decode("gbk")), report)
        finally:
            stream.detach()

    def test_validate_report_with_unencodable_log(self):
        self.capture_gbk(validate_runtime, "validate", ["validate_runtime.py", "candidate"],
                         {"status": "execution_passed", "log": "日志 \ufffd 🧪"})

    def test_prepare_report_with_unencodable_log(self):
        self.capture_gbk(prepare_runtime, "prepare", ["prepare_runtime.py", "candidate", "--job-id", "job", "--tool-bindings", "bindings.json"],
                         {"status": "prepared", "log": "日志 \ufffd 🧪"})

    def test_retry_cli_forwards_only_explicit_budget_overrides(self):
        with patch('delivery.evaluate',return_value={'delivery_accepted':True}), patch.object(validate_runtime,'validate',return_value={'status':'execution_passed'}) as operation, \
             patch('sys.argv',['validate_runtime.py','candidate','--total-seconds','2400','--repair-reserve-seconds','300']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(validate_runtime.main(),0)
        self.assertEqual(operation.call_args.kwargs['budget'],{'total_seconds':2400,'repair_reserve_seconds':300})

    def test_history_repair_is_an_explicit_non_budget_option(self):
        with patch('delivery.evaluate',return_value={'delivery_accepted':True}), patch.object(validate_runtime,'validate',return_value={'status':'execution_passed'}) as operation, \
             patch('sys.argv',['validate_runtime.py','candidate','--repair-from-history']),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(validate_runtime.main(),0)
        self.assertEqual(operation.call_args.kwargs,{'repair_from_history':True})


if __name__ == "__main__":
    unittest.main()
