"""Mayaを起動せず、パッケージ全体を読む検査(上書き・同じ名前のメソッド・引数の型。L090・L094〜L096)を確かめる。"""

import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import check_mlib_layout as layout

#: 上書きで引数を変えた2ファイルのパッケージ(L090)。
OVERRIDE_FILES = {
    "base.py": """
        class Base:
            def run(self, value):
                pass
    """,
    "child.py": """
        from .base import Base


        class Child(Base):
            def run(self, other):
                pass
    """,
}
#: キーワード専用で既定値つきの引数を足すだけの上書き(L090 にならない)。
EXTENSION_FILES = {
    "base.py": OVERRIDE_FILES["base.py"],
    "child.py": """
        from .base import Base


        class Child(Base):
            def run(self, value, *, fast=False):
                pass
    """,
}
#: 親子でない2つのクラスで、同じ名前の公開メソッドの引数名が違うパッケージ(L094)。
SIBLING_FILES = {
    "first.py": """
        class First:
            def apply(self, value):
                pass
    """,
    "second.py": """
        class Second:
            def apply(self, amount):
                pass
    """,
}
#: 同じ名前の引数で、docstring の型の種類が違うパッケージ(L095)。
ARGUMENT_FILES = {
    "first.py": '''
        class First:
            def scale(self, count):
                """拡大する。

                Args:
                    count (int): 回数。
                """
    ''',
    "second.py": '''
        class Second:
            def shift(self, count):
                """ずらす。

                Args:
                    count (str): 名前。
                """
    ''',
}


class PackageCheckTest(unittest.TestCase):
    """小さなパッケージを作り、``check_package`` の項目と許可表の効き方を確かめる。"""

    def setUp(self):
        # 本物の許可表の項目が L096 として混ざらないよう、空の表から始める。
        for name in ("OVERRIDE_ALLOWED", "SIBLING_ALLOWED", "ARGUMENT_ALLOWED"):
            patcher = mock.patch.object(layout, name, {})
            patcher.start()
            self.addCleanup(patcher.stop)

    def check(self, files):
        """ファイルの辞書からパッケージを作って検査し、(コード, 文言) の並びを返す。"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "package"
            root.mkdir()
            (root / "__init__.py").write_text("", encoding="utf-8")
            paths = [root / "__init__.py"]
            for name, text in files.items():
                path = root / name
                path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")
                paths.append(path)
            return [(v.code, v.message) for v in layout.check_package(root, paths)]

    def codes(self, files):
        return sorted(code for code, _message in self.check(files))

    def test_override_with_other_arguments_is_reported(self):
        """上書きの引数が基底と違うと L090 になり、文言にクラスと違いを書く。"""
        result = self.check(OVERRIDE_FILES)
        self.assertEqual([code for code, _ in result], ["L090"])
        self.assertIn("Child.run", result[0][1])
        self.assertIn("Base.run", result[0][1])
        self.assertIn("無い: value", result[0][1])

    def test_override_that_only_adds_keyword_arguments_is_allowed(self):
        """キーワード専用で既定値つきの引数を足すだけなら L090 にならない。"""
        self.assertEqual(self.codes(EXTENSION_FILES), [])

    def test_override_allowance_removes_the_report(self):
        """OVERRIDE_ALLOWED に書いた上書きは L090 にならず、使われるので L096 にもならない。"""
        layout.OVERRIDE_ALLOWED["Child.run"] = "試験用の理由"
        self.assertEqual(self.codes(OVERRIDE_FILES), [])

    def test_unused_override_allowance_is_reported(self):
        """もう違いが無い上書きの許可は L096 になる(無い名前も同じ)。"""
        layout.OVERRIDE_ALLOWED["Child.run"] = "試験用の理由"
        layout.OVERRIDE_ALLOWED["Missing.run"] = "試験用の理由"
        result = self.check(EXTENSION_FILES)
        self.assertEqual([code for code, _ in result], ["L096", "L096"])
        self.assertTrue(any("Child.run" in message for _, message in result))
        self.assertTrue(any("Missing.run" in message for _, message in result))

    def test_siblings_with_other_argument_names_are_reported(self):
        """親子でないクラスの同じ名前の公開メソッドで、引数名が違うと L094 になる。"""
        result = self.check(SIBLING_FILES)
        self.assertEqual([code for code, _ in result], ["L094"])
        self.assertIn("apply", result[0][1])

    def test_sibling_allowance_removes_the_report(self):
        """SIBLING_ALLOWED にクラスを書くと L094 にならず、使われるので L096 にもならない。"""
        layout.SIBLING_ALLOWED["apply"] = {"Second": "試験用の理由"}
        self.assertEqual(self.codes(SIBLING_FILES), [])

    def test_unused_sibling_allowance_is_reported(self):
        """引数名がそろったのに残っている許可は L096 になる。"""
        layout.SIBLING_ALLOWED["apply"] = {"Second": "試験用の理由"}
        same = dict(SIBLING_FILES, **{"second.py": SIBLING_FILES["second.py"].replace("amount", "value")})
        result = self.check(same)
        self.assertEqual([code for code, _ in result], ["L096"])
        self.assertIn("SIBLING_ALLOWED", result[0][1])

    def test_argument_types_that_differ_are_informational(self):
        """同じ名前の引数で型の種類が違うと L095 になり、L095 は情報として扱う。"""
        result = self.check(ARGUMENT_FILES)
        self.assertEqual([code for code, _ in result], ["L095"])
        self.assertIn("count", result[0][1])
        self.assertIn("L095", layout.INFORMATIONAL)

    def test_argument_allowance_removes_the_report(self):
        """ARGUMENT_ALLOWED に書いたメソッドは L095 にならず、使われるので L096 にもならない。"""
        layout.ARGUMENT_ALLOWED["count"] = {"Second.shift": "試験用の理由"}
        self.assertEqual(self.codes(ARGUMENT_FILES), [])
        layout.ARGUMENT_ALLOWED["count"] = {"Second.*": "試験用の理由"}
        self.assertEqual(self.codes(ARGUMENT_FILES), [])

    def test_unused_argument_allowance_is_reported(self):
        """型がそろったのに残っている許可は L096 になる。"""
        layout.ARGUMENT_ALLOWED["count"] = {"Second.shift": "試験用の理由"}
        same = dict(ARGUMENT_FILES, **{"second.py": ARGUMENT_FILES["second.py"].replace("count (str)", "count (int)")})
        result = self.check(same)
        self.assertEqual([code for code, _ in result], ["L096"])
        self.assertIn("ARGUMENT_ALLOWED", result[0][1])


if __name__ == "__main__":
    unittest.main()
