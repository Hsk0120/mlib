"""Mayaを起動せず、``noMaya/`` のテストを実行する。

リント(``_tools/check_mlib_exports.py``・``_tools/check_mlib_layout.py --check``)は
``_tools/format_mlib.bat`` が実行する。同じ検査を2経路で持たないため、ここでは行わない。
"""

import contextlib
import os
import shutil
import sys
import tempfile
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
    temporary = _use_local_temp()
    try:
        suite = unittest.defaultTestLoader.discover(str(TESTS_DIR / "noMaya"), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        if temporary is not None:
            shutil.rmtree(str(temporary), ignore_errors=True)
            with contextlib.suppress(OSError):
                # ほかの実行が使っていなければ(空なら)、置き場所のフォルダーも消す。
                (TOOLS_DIR / ".temp").rmdir()
    return 0 if result.wasSuccessful() else 1


def _use_local_temp():
    """テストが作る一時ファイルの置き場所を、mlibの ``_tools/.temp`` の中(Gitの対象外)にする。

    システムの一時フォルダーは、このフォルダーと別のドライブにあることがある(別のドライブどうしでは相対パスを
    作れない)。``__tests__`` の中へ作ると、検査のツールがテストのファイルとして扱ってしまうので、``_tools`` の中へ作る。
    書き込めないときは何も変えず、システムの一時フォルダーのまま続ける。

    Returns:
        Path | None: 作った一時フォルダー(終わったら消す)。作れなかったときはNone。
    """
    try:
        (TOOLS_DIR / ".temp").mkdir(exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="noMaya-", dir=str(TOOLS_DIR / ".temp")))
    except OSError:
        return None
    os.environ["TEMP"] = os.environ["TMP"] = str(temporary)
    tempfile.tempdir = str(temporary)
    return temporary


if __name__ == "__main__":
    sys.exit(main())
