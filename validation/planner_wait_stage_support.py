"""Import the diagnostic helper from its evidence directory for mechanism tests."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('wait_stage_diagnostics',
    Path(__file__).parent / 'planner-wait-stage/diagnostics.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
project = module.project
StderrProjection = module.StderrProjection
