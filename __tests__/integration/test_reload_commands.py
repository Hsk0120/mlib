"""一時コピーの mlib で、コマンドの明示公開・追加漏れ検査・再読み込みを確かめる。

別の mayapy プロセスで一時コピーを読み込むため、シーンと作業中の mlib ファイルは変更しない。
GUI の Maya では新しい Maya が起動してしまうので、mayapy で実行したときだけ動かす。
"""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

#: 別プロセスで実行する検証。argv[1] は一時コピーの親フォルダー、argv[2] は _tools。
_SCRIPT = r'''
import ast
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
from check_mlib_exports import check
import maya.standalone
maya.standalone.initialize(name="python")
import mlib
from importlib import reload
# 登録表を空にした直接root reloadでも、標準型の明示対応表から再構築する。
mlib.Node._registry.clear()
mlib.Plug._registry.clear()
reload(mlib)
assert isinstance(mlib.getNode("persp"), mlib.Transform)
assert isinstance(mlib.getPlug("persp.tx"), mlib.DoubleLinearPlug)
mlib.reload()
assert mlib.core is sys.modules["mlib.core"]
assert mlib.util is sys.modules["mlib.util"]
assert callable(mlib.cmds.ls)
assert mlib.ls is mlib.cmds.ls
commands = Path(sys.argv[1]) / "mlib" / "cmds"
package = commands.parent
command_init = commands / "__init__.py"
root_init = package / "__init__.py"
original_cmds = command_init.read_text(encoding="utf-8")
original_root = root_init.read_text(encoding="utf-8")

def publish(path, statement, name, target="__all__"):
    """一時コピーの通常importと明示の公開一覧(cmdsは__all__、ルートは_names)へ同じ公開名を追加する。"""
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    node = next(node for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(item, ast.Name) and item.id == target for item in node.targets))
    names = ast.literal_eval(node.value) + [name]
    lines = text.splitlines()
    end_line = getattr(node, "end_lineno", None) or node.value.elts[-1].lineno
    while "]" not in lines[end_line - 1]:
        end_line += 1
    lines[node.lineno - 1:end_line] = [statement, target + " = " + repr(names)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

# 旧版を読み込み済みのセッションから移行しても再公開名を残さない。
mlib.Node = mlib.Node
mlib.createNode = mlib.cmds.createNode
mlib.__all__ += ["Node", "createNode"]
mlib.reload()
# クラスはルートの__getattr__で毎回取得し、モジュール属性には残さない。
assert "Node" not in vars(mlib)
assert mlib.createNode is mlib.cmds.createNode
assert not hasattr(mlib, "NODE_REGISTRY")
assert mlib.Node._registry is not None
assert mlib.Plug._registry is not None
for name in ("getNode", "getPlug", "createNode", "ls", "delete", "duplicate", "select"):
    assert callable(getattr(mlib.cmds, name))

path = commands / "exampleCommand.py"
path.write_text("def exampleCommand():\n    return 1\n", encoding="utf-8")
mlib.reload()
# 通常のimportは親パッケージに実装モジュールを置く場合がある。
# 公開関数と__all__への追加は、__init__.pyで明示するまで発生しない。
assert "exampleCommand" not in mlib.cmds.__all__
assert not callable(getattr(mlib.cmds, "exampleCommand", None))
assert not hasattr(mlib, "exampleCommand")
assert {"E015", "E016"}.issubset({issue.code for issue in check(package)})

publish(command_init, "from .exampleCommand import exampleCommand", "exampleCommand")
publish(root_init, "from .cmds import exampleCommand", "exampleCommand", "_names")
assert not check(package), check(package)
mlib.reload()
assert mlib.exampleCommand() == 1
assert mlib.exampleCommand is mlib.cmds.exampleCommand

path.write_text("def exampleCommand():\n    return 2026\n", encoding="utf-8")
mlib.reload()
assert mlib.exampleCommand() == 2026
assert mlib.exampleCommand is mlib.cmds.exampleCommand

path.write_text("def differentName():\n    return None\n", encoding="utf-8")
assert {"E009", "E014"}.issubset({issue.code for issue in check(package)})

path.write_text("def exampleCommand():\n    return 30000\n", encoding="utf-8")
mlib.reload()
assert mlib.cmds.exampleCommand() == 30000
command_init.write_text(original_cmds, encoding="utf-8")
root_init.write_text(original_root, encoding="utf-8")
path.unlink()
mlib.reload()
assert not hasattr(mlib.cmds, "exampleCommand")
assert not hasattr(mlib, "exampleCommand")
assert not check(package), check(package)

(commands / "_hidden.py").write_text("def _hidden():\n    return 1\n", encoding="utf-8")
(commands / "helper.py").write_text("from os import getcwd as helper\n", encoding="utf-8")
mlib.reload()
assert "_hidden" not in mlib.cmds.__all__
assert "helper" not in mlib.cmds.__all__
assert "E014" in {issue.code for issue in check(package)}
(commands / "helper.py").unlink()
(commands / "reload.py").write_text("def reload():\n    return 'command'\n", encoding="utf-8")
mlib.reload()
assert "reload" not in mlib.cmds.__all__
assert callable(mlib.reload)
assert "E015" in {issue.code for issue in check(package)}
publish(command_init, "from .reload import reload", "reload")
mlib.reload()
assert mlib.cmds.reload() == "command"
assert mlib.reload is not mlib.cmds.reload
assert callable(mlib.reload)
assert not check(package), check(package)
command_init.write_text(original_cmds, encoding="utf-8")
(commands / "reload.py").unlink()
mlib.reload()
print("PASS: explicit commands, omitted export detection, modification, removal, definition errors, root exports")
'''


def _is_mayapy():
    """別プロセスとして起動しても GUI が開かない mayapy かどうか。"""
    return Path(sys.executable).stem.lower() == "mayapy"


@unittest.skipUnless(_is_mayapy(), "runs only from mayapy (a GUI Maya would start another Maya)")
class ReloadCommandsTest(unittest.TestCase):
    """一時パッケージを別プロセスで読み込み、公開 API と再読み込みを検証する。"""

    def test_explicit_commands_and_reload(self):
        source = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix="mlib_commands_") as directory:
            shutil.copytree(source, Path(directory) / "mlib", ignore=shutil.ignore_patterns(
                "_docs", "_tools", "__tests__", "__pycache__"))
            script_path = Path(directory) / "verify.py"
            script_path.write_text(_SCRIPT, encoding="utf-8")
            result = subprocess.run([sys.executable, str(script_path), directory, str(source / "_tools")],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    universal_newlines=True, timeout=300)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("PASS:", result.stdout)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
