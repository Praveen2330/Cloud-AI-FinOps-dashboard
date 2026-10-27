"""
run_tests.py — Test runner that executes all test functions in tests/
Invokes Pytest correctly when available, with a fallback lightweight runner.
"""

import sys
from pathlib import Path

# Add project root and src to sys.path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

def main():
    try:
        import pytest
        # Run tests directly through pytest runner with verbose output
        exit_code = pytest.main(["tests/", "-v"])
        sys.exit(exit_code)
    except ImportError:
        # Fallback runner if pytest is not installed in the current environment
        import inspect
        import traceback
        from types import ModuleType

        mock_pytest = ModuleType("pytest")
        def fixture(func=None, **kwargs):
            if func is not None:
                return func
            return lambda f: f
        mock_pytest.fixture = fixture
        sys.modules["pytest"] = mock_pytest

        test_dir = root_dir / "tests"
        test_files = sorted(test_dir.glob("test_*.py"))

        total = 0
        passed = 0
        failed = 0
        errors = []

        print(f"\n{'='*70}\nRunning FinOps Intelligence Test Suite (Standalone Runner)\n{'='*70}")

        for tfile in test_files:
            module_name = tfile.stem
            print(f"\n📂 Suite: {module_name}")

            import importlib.util
            spec = importlib.util.spec_from_file_location(module_name, str(tfile))
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
            except Exception as e:
                print(f"  ❌ Error importing {module_name}: {e}")
                errors.append((module_name, "IMPORT_ERROR", str(e)))
                continue

            test_funcs = [
                (name, func) for name, func in inspect.getmembers(mod, inspect.isfunction)
                if name.startswith("test_")
            ]

            for name, func in test_funcs:
                total += 1
                sig = inspect.signature(func)
                params = {}
                if "sample_billing_df" in sig.parameters and hasattr(mod, "sample_billing_df"):
                    fixture_fn = getattr(mod.sample_billing_df, "__wrapped__", mod.sample_billing_df)
                    params["sample_billing_df"] = fixture_fn()
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
            sys.exit(1)
        else:
            print("🎉 ALL TESTS PASSED SUCCESSFULLY!\n")
            sys.exit(0)

if __name__ == "__main__":
    main()
