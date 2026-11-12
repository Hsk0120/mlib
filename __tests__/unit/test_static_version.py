"""Maya不要で、mlibの版番号が_version.pyだけにあり、Versionとして読めることを検証する。"""

import importlib.util
from pathlib import Path
import re
import unittest

_MLIB_ROOT = Path(__file__).resolve().parents[2]


def _read_version():
    """mlib/_version.pyの__version__を、mlibをimportせずに読む。"""
    text = (_MLIB_ROOT / "_version.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    return match.group(1) if match else None


def _load_version_class():
    """mlib.common.versionをパッケージ初期化(Maya依存)を通さずに読み込む。"""
    path = _MLIB_ROOT / "common" / "version.py"
    spec = importlib.util.spec_from_file_location("_mlib_static_version", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Version


class VersionConsistencyTest(unittest.TestCase):
    """_version.pyの版番号と、__init__.pyからの読み込みを確かめる。"""

    def setUp(self):
        self.version = _read_version()
        self.assertIsNotNone(self.version, "__version__ が mlib/_version.py にない")

    def test_version_is_a_release_number(self):
        """__version__ は数字3桁の版で、mlib.Version として構築できる。"""
        self.assertRegex(self.version, r"^\d+\.\d+\.\d+$")
        Version = _load_version_class()
        self.assertEqual(Version(self.version), Version(self.version.split(".")))
        self.assertEqual(Version(self.version).suffix, "")

    def test_init_imports_version(self):
        """__init__.py は版番号を直接書かず、_version.py から読み込む。"""
        text = (_MLIB_ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^from \._version import __version__$")
        self.assertNotRegex(text, r"(?m)^__version__\s*=")

    def test_version_is_not_exported(self):
        """__version__ は __all__(明示した _names とクラス名)に入れない。"""
        text = (_MLIB_ROOT / "__init__.py").read_text(encoding="utf-8")
        match = re.search(r"^_names\s*=\s*\[(.*?)\]", text, re.S | re.M)
        self.assertIsNotNone(match)
        self.assertNotIn("__version__", match.group(1))
        self.assertRegex(text, r"(?m)^__all__ = _names \+ sorted\(_classes\)$")


if __name__ == "__main__":
    unittest.main()
