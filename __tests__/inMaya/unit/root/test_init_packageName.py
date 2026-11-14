"""mlib本体の配置名変更と、文書内の名前反映を検証する。"""

import ast
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PackageNameTest(unittest.TestCase):
    """他パッケージなしで本体の名前解決・編集・reloadを検証する。"""

    def test_no_absolute_package_imports(self):
        root = Path(__file__).resolve().parents[4]
        for path in root.rglob("*.py"):
            if any(part in {"_docs", "__tests__", "__pycache__", ".venv", ".mayapy-site"} for part in path.parts):
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    names = [node.module or ""]
                for name in names:
                    self.assertFalse(name == "mlib" or name.startswith(("mlib.", "mlib_")), f"{path}:{node.lineno} {name}")

    def test_core_renamed_without_external_packages(self):
        if Path(sys.executable).stem.lower() != "mayapy":
            self.skipTest("Requires a separate mayapy process")
        root = Path(__file__).resolve().parents[4]
        with tempfile.TemporaryDirectory(prefix="mlib_core_name_") as temporary:
            folder = Path(temporary)
            for name in ("renamed_lib", "studio_lib"):
                shutil.copytree(
                    str(root), str(folder / name), ignore=shutil.ignore_patterns("__tests__", "_docs", "_tools", ".git", ".github", "__pycache__", "*.pyc")
                )
            script = r"""
import importlib
import importlib.abc
import sys
class RejectOriginal(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mlib" or fullname.startswith(("mlib.", "mlib_")):
            raise AssertionError("Original package imported: " + fullname)
sys.meta_path.insert(0, RejectOriginal())
sys.path.insert(0, sys.argv[1])
import maya.standalone
maya.standalone.initialize(name="python")
from maya import cmds
try:
    for name in ("renamed_lib", "studio_lib"):
        core = importlib.import_module(name)
        node = core.createNode("transform")
        node.getPlug("tx").set(3)
        cmds.undo()
        assert node.getPlug("tx").get() == 0
        node.getPlug("translate").set((1, 2, 3), fast=True)
        assert tuple(node.getTranslation()) == (1, 2, 3)
        previous = core.nodes.Node
        core.reload()
        assert previous is not core.nodes.Node
        assert isinstance(core.getNode(node.getFullName()), core.nodes.Node)
finally:
    maya.standalone.uninitialize()
"""
            path = folder / "smoke.py"
            path.write_text(script, encoding="utf8")
            result = subprocess.run([sys.executable, str(path), temporary], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout.decode("utf8", errors="replace"))


if __name__ == "__main__":
    unittest.main()
