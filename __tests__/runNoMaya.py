"""Mayaを起動せず、``noMaya/`` のテストを実行する。

リント(``_tools/check_mlib_exports.py``・``_tools/check_mlib_layout.py --check``)は
``_tools/verify.bat`` が実行する。同じ検査を2経路で持たないため、ここでは行わない。
"""

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent / "_tools"


def main():
    """``noMaya/test_*.py`` を実行し、終了コードを返す。

    Returns:
        int: 1件でも失敗すれば1、すべて成功なら0。
    """
    # noMaya/ のテストは support/ と _tools/ のスクリプトをimportする。
    sys.path.insert(0, str(TESTS_DIR))
    sys.path.insert(0, str(TOOLS_DIR))
    suite = unittest.defaultTestLoader.discover(str(TESTS_DIR / "noMaya"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
