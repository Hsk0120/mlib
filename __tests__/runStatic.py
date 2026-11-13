"""Mayaを起動せず、検査ツールと static/ のテストを実行する。"""
from pathlib import Path
import subprocess
import sys
import unittest

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent / "_tools"


def main():
    """公開・レイアウト検査と static/test_*.py を順に実行する。"""
    sys.path.insert(0, str(TESTS_DIR))
    sys.path.insert(0, str(TOOLS_DIR))
    failures = 0
    for filename, arguments in [("check_mlib_exports.py", []), ("check_mlib_layout.py", ["--check"])]:
        result = subprocess.run([sys.executable, str(TOOLS_DIR / filename)] + arguments)
        failures += result.returncode != 0
    suite = unittest.defaultTestLoader.discover(str(TESTS_DIR / "static"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 1 if failures or not result.wasSuccessful() else 0


if __name__ == "__main__":
    sys.exit(main())
