"""
run_tests.py — Test runner that executes all test functions in tests/
Runs cleanly with or without pytest installed.
"""

import sys
import inspect
import traceback
from pathlib import Path
from types import ModuleType

# Add project root and src to sys.path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

# If pytest is not installed, provide a lightweight mock so test files can import it
try:
    import pytest
except ImportError:
    mock_pytest = ModuleType("pytest")
    def fixture(func=None, **kwargs):
        if func is not None:
            return func
        return lambda f: f
    mock_pytest.fixture = fixture
    sys.modules["pytest"] = mock_pytest

def run_all_tests():
    test_dir = root_dir / "tests"
    test_files = sorted(test_dir.glob("test_*.py"))

    total = 0
    passed = 0
    failed = 0
    errors = []

    print(f"\n{'='*70}\nRunning FinOps Intelligence Test Suite\n{'='*70}")

    for tfile in test_files:
        module_name = tfile.stem
        print(f"\n📂 Suite: {module_name}")
        
        # Load module
        import importlib.util
        spec = importlib.util.spec_from_file_location(module_name, str(tfile))
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            print(f"  ❌ Error importing {module_name}: {e}")
            traceback.print_exc()
            errors.append((module_name, "IMPORT_ERROR", str(e)))
            continue

        # Look for test functions
        test_funcs = [
            (name, func) for name, func in inspect.getmembers(mod, inspect.isfunction)
            if name.startswith("test_")
        ]

        for name, func in test_funcs:
            total += 1
            # Check for fixtures
            sig = inspect.signature(func)
            params = {}
            if "sample_billing_df" in sig.parameters and hasattr(mod, "sample_billing_df"):
                params["sample_billing_df"] = mod.sample_billing_df()
            if "tmp_path" in sig.parameters:
                import tempfile
                params["tmp_path"] = Path(tempfile.mkdtemp())

            try:
                func(**params)
                passed += 1
                print(f"  ✅ {name}")
            except Exception as e:
                failed += 1
                print(f"  ❌ {name} -> {e}")
                errors.append((module_name, name, traceback.format_exc()))

    print(f"\n{'='*70}")
    print(f"Test Summary: {passed}/{total} PASSED ({failed} FAILED)")
    print(f"{'='*70}\n")

    if errors:
        print("Failure Details:")
        for mod, name, tb in errors:
            print(f"\n--- {mod} :: {name} ---\n{tb}")
        sys.exit(1)
    else:
        print("🎉 ALL TESTS PASSED SUCCESSFULLY!\n")
        sys.exit(0)

if __name__ == "__main__":
    run_all_tests()
