"""Storage arithmetic and short-read transport; never access Docker/models."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

path=Path(__file__).resolve().parents[2]/'validation/deepseek-api/measure_shared_tool_paths.py'
spec=importlib.util.spec_from_file_location('shared_path_metrics',path)
metrics=importlib.util.module_from_spec(spec);spec.loader.exec_module(metrics)


class StorageMetricsTests(unittest.TestCase):
    def test_business_timing_includes_authored_interface_mapped_checks(self):
        report={'cases':[{'name':'chemistry','layer':'behavior','origin':'model_proposed'},
                         {'name':'original-file-check','layer':'interface','origin':'authored_check'},
                         {'name':'help','layer':'interface','origin':'model_proposed'}],
                'case_wall_seconds':{'chemistry':2,'original-file-check':3,'help':1}}
        self.assertEqual(metrics.case_timings(report),{'model_behavior_cases':2,'authored_business_checks':3,
                                                       'business_cases':5,'all_cases':6})

    def test_unknown_layer_usage_is_not_reported_as_zero(self):
        a={'summary':metrics.storage_summary({'LayersSize':-1}), 'filesystem_used_bytes':None}
        b={'summary':metrics.storage_summary({'LayersSize':42}), 'filesystem_used_bytes':100}
        self.assertIsNone(metrics.storage_delta(a,b)['image_layers_bytes'])
        self.assertIsNone(metrics.storage_delta(a,b)['desktop_filesystem_used_bytes'])

    def test_layer_delta_does_not_sum_image_virtual_sizes(self):
        a={'summary':metrics.storage_summary({'LayersSize':100,'Images':[{'Id':'same','Size':100}]}),'filesystem_used_bytes':500}
        b={'summary':metrics.storage_summary({'LayersSize':101,'Images':[{'Id':'same','Size':100},{'Id':'new','Size':101}]}),'filesystem_used_bytes':480}
        delta=metrics.storage_delta(a,b)
        self.assertEqual(delta['image_layers_bytes'],1)
        self.assertEqual(delta['new_image_ids'],['new'])
        self.assertEqual(delta['desktop_filesystem_used_bytes'],-20)

    def test_fragmented_named_pipe_response_is_buffered(self):
        body=json.dumps({'LayersSize':123}).encode()
        response=b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'+hex(len(body))[2:].encode()+b'\r\n'+body+b'\r\n0\r\n\r\n'
        class Fragmented(io.RawIOBase):
            def __init__(self):self.remaining=response;self.request=b''
            def readable(self):return True
            def readinto(self,b):
                n=min(3,len(b),len(self.remaining));b[:n]=self.remaining[:n];self.remaining=self.remaining[n:];return n
            def write(self,b):self.request+=b;return len(b)
        stream=Fragmented()
        with patch('builtins.open',return_value=stream):
            self.assertEqual(metrics.engine_df('npipe:////./pipe/test-engine'),{'LayersSize':123})
        self.assertTrue(stream.request.startswith(b'GET /system/df '))


if __name__=='__main__':unittest.main()
