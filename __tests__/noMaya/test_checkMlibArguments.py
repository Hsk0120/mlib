"""Mayaを起動せず、引数の表との突き合わせ(``_tools/check_mlib_arguments.py``。A001〜A015)と整形を確かめる。"""

import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import check_mlib_arguments as tool

Argument = tool.Argument

#: キーワード専用と決めた名前を、既定値つきの位置引数で受ける(A001)。
KEYWORD_AS_POSITIONAL = """
    class Item:
        def get(self, kind="a"):
            \"\"\"取得する。

            Args:
                kind (str): 種類。既定は ``"a"``。
            \"\"\"
"""
#: 同じ名前の引数の既定値が2通りある(表にあれば A002、無ければ A004)。
TWO_DEFAULTS = """
    class Item:
        def first(self, *, depth=1):
            \"\"\"1つ目。

            Args:
                depth (int): 深さ。既定は1。
            \"\"\"

        def second(self, *, depth=2):
            \"\"\"2つ目。

            Args:
                depth (int): 深さ。既定は2。
            \"\"\"
"""
#: bool の既定値を持つ位置引数(A003)。
BOOL_POSITIONAL = """
    class Item:
        def run(self, value, quiet=False):
            \"\"\"実行する。

            Args:
                value (int): 値。
                quiet (bool): Trueなら表示しない。既定はFalse。
            \"\"\"
"""
#: 同じ名前を、位置とキーワード専用の両方で受ける(A004)。
TWO_KINDS = """
    class Item:
        def first(self, depth=1):
            \"\"\"1つ目。

            Args:
                depth (int): 深さ。既定は1。
            \"\"\"

        def second(self, *, depth=1):
            \"\"\"2つ目。

            Args:
                depth (int): 深さ。既定は1。
            \"\"\"
"""
#: docstring が直せる形で崩れている(A010 の None・A011・A012・A014・A015)。
FIXABLE = """
    def write(value, worldSpace=False, *, fast=False, ws=False, name=None, check=False):
        \"\"\"書き込む。

        Args:
            value (float): 値。
            name (str): 名前。Noneなら付けない
            ws (bool): worldSpaceの別名。
            check (bool): 古い文。
            worldSpace (bool): Trueならワールド空間。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
        \"\"\"
"""
FIXED = """
    def write(value, worldSpace=False, *, name=None, fast=False, check=False, ws=False):
        \"\"\"書き込む。

        Args:
            value (float): 値。
            worldSpace (bool): Trueならワールド空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。
            name (str | None): 名前。Noneなら付けない。既定はNone。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): 新しい文。既定はFalse。
        \"\"\"
"""
#: ``--fix`` の確認に使う表。
FIX_TABLE = {
    "fast": Argument("fast", kind="keyword", default="False", text="TrueはUndoなしのOpenMaya更新。既定False。"),
    "check": Argument("check", kind="keyword", default="False", text="新しい文。既定はFalse。", variants={"古い文。": "新しい文。既定はFalse。"}),
    "ws": Argument("ws", kind="keyword", text="worldSpaceの短縮名。", whole=True),
    "worldSpace": Argument("worldSpace", kind="positional", default="False"),
}


class ArgumentCheckTest(unittest.TestCase):
    """小さなパッケージを作り、検査の項目と表の効き方を確かめる。"""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / "package"
        self.root.mkdir()
        self.patch("PACKAGE_ROOT", self.root)
        self.patch("RST_PATH", self.root / "_docs" / "source" / "arguments.rst")
        self.patch("ARGUMENTS", {})
        self.patch("BOOL_POSITIONAL_ALLOWED", {})

    def patch(self, name, value):
        patcher = mock.patch.object(tool, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, source, name="module.py"):
        path = self.root / name
        path.write_text(textwrap.dedent(source).lstrip("\n"), encoding="utf-8", newline="\n")
        return path

    def codes(self, source=None):
        if source is not None:
            self.write(source)
        return [violation.code for violation in tool.check(tool.collect(self.root))]

    def test_keyword_name_received_by_position_is_reported(self):
        tool.ARGUMENTS["kind"] = Argument("種類", kind="keyword", default=tool.VARIES, reason="種類ごと")
        self.assertEqual(self.codes(KEYWORD_AS_POSITIONAL), ["A001"])

    def test_kind_allowance_removes_the_report(self):
        tool.ARGUMENTS["kind"] = Argument("種類", kind="keyword", kindAllowed={"Item.get": "主な値"})
        self.assertEqual(self.codes(KEYWORD_AS_POSITIONAL), [])

    def test_required_argument_may_be_positional(self):
        tool.ARGUMENTS["kind"] = Argument("種類", kind="keyword")
        self.assertEqual(self.codes(KEYWORD_AS_POSITIONAL.replace('kind="a"', "kind").replace(' 既定は ``"a"``。', "")), [])

    def test_default_that_differs_from_the_table_is_reported(self):
        tool.ARGUMENTS["depth"] = Argument("深さ", kind="keyword", default="1")
        self.assertEqual(self.codes(TWO_DEFAULTS), ["A002"])

    def test_default_allowance_and_varies_remove_the_report(self):
        tool.ARGUMENTS["depth"] = Argument("深さ", kind="keyword", default="1", defaultAllowed={"Item.second": "理由"})
        self.assertEqual(self.codes(TWO_DEFAULTS), [])
        tool.ARGUMENTS["depth"] = Argument("深さ", kind="keyword", default=tool.VARIES, reason="理由")
        self.assertEqual(self.codes(), [])

    def test_bool_positional_argument_is_reported(self):
        self.assertEqual(self.codes(BOOL_POSITIONAL), ["A003"])

    def test_bool_positional_is_allowed_by_the_tables(self):
        tool.BOOL_POSITIONAL_ALLOWED["Item.run"] = {"quiet": "理由"}
        self.assertEqual(self.codes(BOOL_POSITIONAL), [])
        tool.BOOL_POSITIONAL_ALLOWED.clear()
        tool.ARGUMENTS["quiet"] = Argument("表示しない", kind="positional", default="False")
        self.assertEqual(self.codes(), [])

    def test_untabled_name_with_two_kinds_or_defaults_is_reported(self):
        self.assertEqual(self.codes(TWO_KINDS), ["A004"])
        self.assertEqual(self.codes(TWO_DEFAULTS), ["A004"])

    def test_stale_table_entries_are_reported(self):
        tool.ARGUMENTS["missing"] = Argument("無い名前")
        tool.ARGUMENTS["kind"] = Argument("種類", kind="keyword", kindAllowed={"Item.get": "主な値", "Other.get": "もう無い"})
        tool.BOOL_POSITIONAL_ALLOWED["Item.run"] = {"quiet": "もう無い"}
        self.assertEqual(self.codes(KEYWORD_AS_POSITIONAL), ["A005", "A005", "A005"])

    def test_docstring_problems_are_reported(self):
        self.patch("ARGUMENTS", dict(FIX_TABLE))
        self.assertEqual(sorted(set(self.codes(FIXABLE))), ["A010", "A011", "A012", "A014", "A015"])

    def test_documented_default_that_differs_is_reported(self):
        source = BOOL_POSITIONAL.replace("既定はFalse。", "既定はTrue。").replace("value, quiet=False", "value, *, quiet=False")
        self.assertEqual(self.codes(source), ["A011"])

    def test_documented_type_that_differs_from_the_table_is_reported(self):
        tool.ARGUMENTS["value"] = Argument("値", type="float")
        self.assertEqual(self.codes(BOOL_POSITIONAL.replace("value, quiet=False", "value, *, quiet=False")), ["A013"])

    def test_sentinel_default_is_read_from_pick_alias(self):
        source = """
            def create(name=_UNSET, *, flag=_UNSET, n=_UNSET):
                \"\"\"作る。

                Args:
                    name (str | None): 名前。
                    n (str | None): nameの短縮名。
                    flag (bool): Mayaのフラグ。
                \"\"\"
                name = _pick_alias(name, n, "name", "n", default=None)
        """
        self.write(source)
        function = tool.collect(self.root)[0]
        self.assertEqual({param.name: param.default for param in function.params}, {"name": "None", "n": "_UNSET", "flag": "_UNSET"})
        self.assertEqual(function.aliases(), {"n": "name"})
        # 番兵のままの引数(Maya のフラグ)と短縮名は、既定値の記述を求めない。
        self.assertEqual(self.codes(), ["A011"])

    def test_private_and_core_definitions_are_not_checked(self):
        self.write(BOOL_POSITIONAL.replace("def run", "def _run"))
        (self.root / "core").mkdir()
        self.write(BOOL_POSITIONAL, "core/module.py")
        self.assertEqual(self.codes(), [])

    def test_fix_rewrites_docstring_and_keyword_order(self):
        self.patch("ARGUMENTS", dict(FIX_TABLE))
        path = self.write(FIXABLE)
        self.assertEqual(tool.fix(tool.collect(self.root)), 1)
        self.assertEqual(path.read_text(encoding="utf-8"), textwrap.dedent(FIXED).lstrip("\n"))
        self.assertEqual(self.codes(), [])
        # もう一度かけても変わらない。
        self.assertEqual(tool.fix(tool.collect(self.root)), 0)

    def test_fix_keeps_line_endings(self):
        self.patch("ARGUMENTS", dict(FIX_TABLE))
        path = self.root / "module.py"
        path.write_bytes(textwrap.dedent(FIXABLE).lstrip("\n").replace("\n", "\r\n").encode("utf-8"))
        tool.fix(tool.collect(self.root))
        self.assertEqual(path.read_bytes(), textwrap.dedent(FIXED).lstrip("\n").replace("\n", "\r\n").encode("utf-8"))

    def test_fix_does_not_change_what_callers_see(self):
        """位置引数の順・名前・既定値は ``--fix`` で変わらない(キーワード専用の並びだけが変わる)。"""
        self.patch("ARGUMENTS", dict(FIX_TABLE))
        self.write(FIXABLE)
        before = tool.collect(self.root)[0]
        tool.fix(tool.collect(self.root))
        after = tool.collect(self.root)[0]

        def shape(function):
            positional = [(p.name, p.default) for p in function.params if p.kind == "positional"]
            return positional, sorted((p.name, p.default) for p in function.params if p.kind == "keyword")

        self.assertEqual(shape(before), shape(after))

    def test_rst_page_is_written_and_checked(self):
        self.patch("ARGUMENTS", dict(FIX_TABLE))
        self.write(FIXED)
        tool.RST_PATH.parent.mkdir(parents=True)
        self.assertEqual(self.codes(), [])
        self.assertFalse(tool.is_rst_current(tool.collect(self.root)))
        tool.write_rst(tool.collect(self.root), tool.RST_PATH)
        self.assertTrue(tool.is_rst_current(tool.collect(self.root)))
        text = tool.RST_PATH.read_text(encoding="utf-8")
        self.assertIn(".. _argument-fast:", text)
        self.assertIn(":func:`write <package.module.write>`", text)


class HelperTest(unittest.TestCase):
    """署名と docstring を読む補助。"""

    def test_split_head(self):
        self.assertEqual(tool.split_head("name (str | None): 名前。"), ("", "name", "str | None", "名前。"))
        self.assertEqual(tool.split_head("**kwargs: フラグ。"), ("**", "kwargs", None, "フラグ。"))
        self.assertEqual(tool.split_head("call (Callable[[int], (str)]): 関数。"), ("", "call", "Callable[[int], (str)]", "関数。"))
        self.assertIsNone(tool.split_head("ただの文。"))

    def test_type_problem(self):
        self.assertEqual(tool.type_problem("str", "None"), "None")
        self.assertIsNone(tool.type_problem("str | None", "None"))
        self.assertIsNone(tool.type_problem("object", "None"))
        self.assertEqual(tool.type_problem("int", "True"), "bool")
        self.assertEqual(tool.type_problem("str", "3"), "数")
        self.assertEqual(tool.type_problem("int", "'a'"), "str")
        self.assertIsNone(tool.type_problem("dict[str, int | None]", "{}"))

    def test_noted_default(self):
        self.assertEqual(tool.noted_default("説明。既定False。"), "False")
        self.assertEqual(tool.noted_default('単位。既定は ``"deg"``。'), '"deg"')
        self.assertEqual(tool.noted_default("既定値は3。"), "3")
        self.assertIsNone(tool.noted_default("既定はcm。"))
        self.assertIsNone(tool.noted_default("説明だけ。"))
        self.assertTrue(tool.same_default('"deg"', "'deg'"))
        self.assertTrue(tool.same_default("1", "1.0"))
        self.assertFalse(tool.same_default("True", "False"))

    def test_format_default(self):
        self.assertEqual(tool.format_default("None"), "None")
        self.assertEqual(tool.format_default("1e-10"), "1e-10")
        self.assertEqual(tool.format_default("'deg'"), ' ``"deg"``')
        self.assertEqual(tool.format_default("(0, 1, 0)"), " ``(0, 1, 0)``")


if __name__ == "__main__":
    unittest.main()
