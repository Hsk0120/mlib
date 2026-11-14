"""本体テストの探索範囲・指定ミスで空の成功を返さないこと・テストファイルの名前の規則を検証する。"""

import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import runAll


class DiscoveryTest(unittest.TestCase):
    def test_failures_keep_tracebacks_and_passed_output_stays_in_log(self):
        """値不一致・例外を保存/表示し、成功したファイルの出力は表示しない。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = root / "cases"
            cases.mkdir()
            bodies = {
                "test_pass.py": 'print("passed output only in log")\nself.assertEqual(5, 5)',
                "test_fail.py": "self.assertEqual(5, 10)",
                "test_error.py": 'raise RuntimeError("failure detail example")',
            }
            for name, body in bodies.items():
                source = (
                    "import unittest\nclass Example(unittest.TestCase):\n"
                    "    def test_example(self):\n        " + body.replace("\n", "\n        ") + '\nif __name__ == "__main__":\n    unittest.main()\n'
                )
                (cases / name).write_text(source, encoding="utf-8")
            terminal = io.StringIO()
            with mock.patch.object(runAll, "LOG_DIR", root / "logs"), contextlib.redirect_stdout(terminal):
                result = runAll.run_all(directories=[cases])
            self.assertFalse(result["ok"])
            self.assertEqual(result["tests_run"], 3)
            self.assertEqual(result["failed"], ["test_error.py", "test_fail.py"])
            self.assertEqual([row["file"] for row in result["failure_details"]], result["failed"])
            text = terminal.getvalue()
            self.assertIn("AssertionError: 5 != 10", text)
            self.assertIn("RuntimeError: failure detail example", text)
            self.assertIn(str(cases / "test_fail.py"), text)
            self.assertIn(str(result["log_path"]), text)
            self.assertNotIn("passed output only in log", text)
            self.assertIn("passed output only in log", result["log_path"].read_text(encoding="utf-8"))

    def test_unit_and_integration_can_run_separately(self):
        files = runAll.discover_test_files(suite="unit")
        self.assertTrue(files)
        root = Path(runAll.__file__).parent / "inMaya/unit"
        self.assertTrue(all(root in path.parents for path in files))
        self.assertEqual(files, sorted(files, key=str))
        integration = runAll.discover_test_files(suite="integration")
        self.assertTrue(integration)
        self.assertFalse(set(files) & set(integration))
        self.assertEqual(set(files + integration), set(runAll.discover_test_files()))
        no_maya = Path(runAll.__file__).parent / "noMaya"
        self.assertFalse([path for path in files + integration if no_maya in path.parents])

    def test_selects_known_file_and_rejects_a_typo(self):
        files = runAll.discover_test_files(names=["test_dagNode_order.py"])
        self.assertEqual([path.name for path in files], ["test_dagNode_order.py"])
        # 同じ名前のファイルはフォルダー付きの相対パスで1つに絞れる。
        both = runAll.discover_test_files(names=["test_file.py"])
        self.assertEqual(len(both), 2)
        files = runAll.discover_test_files(names=["json/test_file.py"])
        self.assertEqual([path.parent.name for path in files], ["json"])
        with self.assertRaises(ValueError):
            runAll.discover_test_files(names=["test_does_not_exist.py"])


#: mlib のパッケージ。inMaya/unit/ の下に同じ名前のフォルダーを置く(root は mlib 直下のモジュール)。
_PACKAGES = ("cmds", "nodes", "plugs", "components", "maths", "common", "core", "json", "root")
#: inMaya/integration/ のファイル名の先頭に書く観点。
_VIEWS = ("naming", "units", "fast", "parity", "undo", "errors", "interop", "performance", "workflow", "reload", "compat")
#: 名前に使わない語(何を確かめるかが分からない語・作業の経緯を表す語)。
_BANNED = ("spec", "refactoring", "consolidated", "changes", "additions", "backlog", "misc", "api", "contracts")
_NAME = re.compile(r"^test_([a-z][A-Za-z0-9]*)(?:_([a-z][A-Za-z0-9]*))?\.py$")


class FileNamingTest(unittest.TestCase):
    """テストファイルの置き場所と名前が README の規則に従う。"""

    def setUp(self):
        self.tests = Path(runAll.__file__).resolve().parent
        self.mlib = self.tests.parent

    def _targets(self, package):
        """inMaya/unit/<package>/ のファイル名に書ける対象(ソースのファイル名。先頭の _ は除く)。"""
        folder = self.mlib if package == "root" else self.mlib / package
        names = {path.stem.lstrip("_") for path in folder.glob("*.py")} - {""}
        return names | {"init"}

    def _check(self, path, targets):
        relative = path.relative_to(self.tests).as_posix()
        match = _NAME.match(path.name)
        self.assertTrue(match, relative + ": test_<対象>[_<話題>].py の形にする")
        for part in filter(None, match.groups()):
            self.assertFalse([word for word in _BANNED if part.lower().startswith(word)], relative)
        self.assertIn(match.group(1), targets, relative + ": 対象がソースに無い")

    def test_unit_files_name_a_source_module(self):
        unit = self.tests / "inMaya/unit"
        folders = sorted(path.name for path in unit.iterdir() if path.is_dir() and not path.name.startswith("__"))
        self.assertEqual(set(folders) - set(_PACKAGES), set())
        self.assertFalse(list(unit.glob("*.py")), "inMaya/unit/ 直下には置かない")
        for package in folders:
            targets = self._targets(package)
            for path in sorted((unit / package).glob("*.py")):
                with self.subTest(path=path.name, package=package):
                    self._check(path, targets)

    def test_integration_files_start_with_a_view(self):
        integration = self.tests / "inMaya/integration"
        self.assertFalse(
            [path for path in integration.iterdir() if path.is_dir() and not path.name.startswith("__")], "inMaya/integration/ にはフォルダーを作らない"
        )
        for path in sorted(integration.glob("*.py")):
            with self.subTest(path=path.name):
                self._check(path, _VIEWS)

    def test_noMaya_files_follow_the_same_form(self):
        for path in sorted((self.tests / "noMaya").glob("*.py")):
            with self.subTest(path=path.name):
                match = _NAME.match(path.name)
                self.assertTrue(match, path.name)
                for part in filter(None, match.groups()):
                    self.assertFalse([word for word in _BANNED if part.lower().startswith(word)], path.name)


if __name__ == "__main__":
    unittest.main()
