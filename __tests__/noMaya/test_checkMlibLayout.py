"""Mayaを起動せず、クラス内依存を保つレイアウト整形を検証する。"""

import ast
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import check_mlib_layout as layout


class ClassDependencyLayoutTest(unittest.TestCase):
    """既知依存だけを分類し、元の文・実行順制約を保つ。"""

    def source(self, text):
        """試験用の字下げを除き、AST付きソースを返す。"""
        return layout.Source(Path("sample.py"), textwrap.dedent(text).strip() + "\n")

    def formatted(self, text):
        """内容不変・再整形不変・整形後の違反なしを共通検証する。"""
        before = self.source(text)
        fixed = layout.fix_text(before.path, "\n".join(before.lines) + "\n")
        after = layout.Source(before.path, fixed)
        self.assertEqual(layout.compare_snapshots(layout.snapshot_source(before), layout.snapshot_source(after)), [])
        self.assertEqual(layout.fix_text(before.path, fixed), fixed)
        self.assertEqual([str(v) for v in layout.check_source(after) if v.code not in layout.INFORMATIONAL], [])
        return fixed, after

    def test_method_signature_and_class_attribute_alias_stay_attached(self):
        """メソッドに付く署名代入と単純なクラス内別名は元の順序を保つ。"""
        fixed, after = self.formatted("""
            class Example:
                def _internal(self):
                    return None

                def ready(self):
                    return True

                ready.__signature__ = "signature"
                available = ready

                def __init__(self):
                    self.value = 1
        """)
        namespace = {}
        exec(fixed, namespace)
        self.assertTrue(namespace["Example"]().available())
        nodes = after.tree.body[0].body
        index = next(i for i, node in enumerate(nodes) if isinstance(node, ast.FunctionDef) and node.name == "ready")
        self.assertIsInstance(nodes[index + 1], ast.Assign)
        self.assertIsInstance(nodes[index + 2], ast.Assign)

    def test_property_setter_and_special_alias_keep_their_getters(self):
        """property setterと特殊メソッド別名を移動しても元定義へ結び付ける。"""
        fixed, after = self.formatted("""
            class Example:
                @property
                def value(self):
                    return self._value

                def other(self):
                    return None

                @value.setter
                def value(self, value):
                    self._value = value

                def __init__(self):
                    self._value = 3

                def __repr__(self):
                    return str(self._value)

                __str__ = __repr__
        """)
        namespace = {}
        exec(fixed, namespace)
        instance = namespace["Example"]()
        instance.value = 9
        self.assertEqual(instance.value, 9)
        self.assertEqual(str(instance), "9")
        nodes = after.tree.body[0].body
        getter = next(i for i, node in enumerate(nodes) if isinstance(node, ast.FunctionDef) and node.name == "value")
        self.assertEqual(nodes[getter + 1].name, "value")

    def test_type_checking_annotation_block_keeps_order_content_and_comments(self):
        """注釈専用のTYPE_CHECKINGブロックは文を保ったまま属性群へ置く。"""
        source = """
            class Example:
                def method(self):
                    return 1

                if TYPE_CHECKING:
                    # 宣言の順序は意味付きの値と短縮名を対応させる。
                    translate: "Translate"
                    t: "Translate"
                    scale: "Scale"

                marker = "kept"
        """
        original = self.source(source).tree.body[0].body[1]
        fixed, after = self.formatted(source)
        reordered = after.tree.body[0].body[0]
        self.assertEqual(ast.dump(original), ast.dump(reordered))
        namespace = {"TYPE_CHECKING": False}
        exec(fixed, namespace)
        self.assertEqual(namespace["Example"]().method(), 1)

    def test_qualified_type_checking_annotation_block_is_supported(self):
        """typing.TYPE_CHECKING表記でも単純な注釈だけを扱う。"""
        fixed, _ = self.formatted("""
            class Example:
                def method(self):
                    return 1

                if typing.TYPE_CHECKING:
                    value: int
        """)
        self.assertLess(fixed.index("if typing.TYPE_CHECKING:"), fixed.index("def method"))

    def test_unknown_decorator_or_default_class_reference_is_refused(self):
        """クラス内定義に依存する未知装飾や既定値の参照を許可しない。"""
        for decorator, default in (
            ("@unknown(isReady)", ""),
            ("@namespace.decorate(isReady)", ""),
            ("@decorate(isReady)", ", callback=isReady"),
            ("@decorate(isReady, static=isReady())", ""),
        ):
            with self.subTest(decorator=decorator, default=default):
                source = self.source(
                    """
                    class Example:
                        def isReady(self):
                            return True

                        DECORATOR
                        def ready(selfDEFAULT):
                            return True
                """.replace("DECORATOR", decorator).replace("DEFAULT", default)
                )
                with self.assertRaises(layout.Unsupported):
                    layout.classify_members(source.tree.body[0])
                self.assertIn("L023", [v.code for v in layout.check_source(source)])
                fixed = layout.Source(source.path, layout.fix_text(source.path, "\n".join(source.lines) + "\n"))
                self.assertEqual(ast.dump(source.tree), ast.dump(fixed.tree))

    def test_unknown_decorator_before_target_or_defined_in_class_is_refused(self):
        """参照先が後続する装飾やクラス内定義の装飾を安全扱いにしない。"""
        for text in (
            """
            class Example:
                @decorate(isReady)
                def ready(self):
                    return True

                def isReady(self):
                    return True
        """,
            """
            class Example:
                def decorate(self):
                    return None

                def isReady(self):
                    return True

                @decorate(isReady)
                def ready(self):
                    return True
        """,
        ):
            with self.subTest(text=text):
                source = self.source(text)
                with self.assertRaises(layout.Unsupported):
                    layout.classify_members(source.tree.body[0])

    def test_property_accessor_does_not_allow_other_class_dependencies(self):
        """propertyの既知依存に紛れた、別デコレータや既定値の参照も拒否する。"""
        for decorator, default in (("@unknown(isReady)", ""), ("", "=isReady")):
            with self.subTest(decorator=decorator, default=default):
                source = self.source(
                    """
                    class Example:
                        def isReady(self):
                            return True

                        @property
                        def value(self):
                            return 1

                        @value.setter
                        DECORATOR
                        def value(self, valueDEFAULT):
                            return None
                """.replace("DECORATOR", decorator).replace("DEFAULT", default)
                )
                with self.assertRaises(layout.Unsupported):
                    layout.classify_members(source.tree.body[0])

    def test_type_checking_runtime_statements_or_else_are_refused(self):
        """TYPE_CHECKINGでも値代入・import・定義やelseは対応範囲へ広げない。"""
        for body in ("value: int = 1", "import typing", "value = 1", "pass"):
            with self.subTest(body=body):
                source = self.source("class Example:\n    if TYPE_CHECKING:\n        " + body)
                with self.assertRaises(layout.Unsupported):
                    layout.classify_members(source.tree.body[0])
        source = self.source("""
            class Example:
                if TYPE_CHECKING:
                    value: int
                else:
                    value = 1
        """)
        with self.assertRaises(layout.Unsupported):
            layout.classify_members(source.tree.body[0])
        source = self.source("""
            class Example:
                if application.TYPE_CHECKING:
                    value: int
        """)
        with self.assertRaises(layout.Unsupported):
            layout.classify_members(source.tree.body[0])


class ModuleLayoutTest(unittest.TestCase):
    """ruffが見ない、定数・``__all__``・``if TYPE_CHECKING:`` の位置だけを検査する。"""

    def codes(self, text, filename="sample.py"):
        source = layout.Source(Path(filename), textwrap.dedent(text).strip() + "\n")
        return sorted({v.code for v in layout.check_source(source) if v.code in {"L004", "L005", "L006"}})

    def test_constants_and_literal_all_belong_before_the_definitions(self):
        """定数と文字列の並びの ``__all__`` は、どのファイルでも定義の前に置く。"""
        for filename in ("sample.py", "__init__.py"):
            with self.subTest(filename=filename):
                self.assertEqual(self.codes("def run():\n    pass\n\n\nLIMIT = 1", filename), ["L004"])
                self.assertEqual(self.codes('def run():\n    pass\n\n\n__all__ = ["run"]', filename), ["L005"])
                self.assertEqual(self.codes('__all__ = ["run"]\nLIMIT = 1\n\n\ndef run():\n    pass', filename), [])

    def test_assembled_all_keeps_its_place_after_the_definitions(self):
        """公開名を集めてから組み立てる ``__all__`` は、定義の後ろでもよい。"""
        self.assertEqual(self.codes("def run():\n    pass\n\n\n__all__ = _names + sorted(_classes)"), [])
        self.assertEqual(self.codes("def run():\n    pass\n\n\n__all__ = [*_names, *_classes]"), [])

    def test_type_checking_block_comes_after_the_imports(self):
        """``if TYPE_CHECKING:`` の後ろに通常のimportを置かない(ruffのE402は許す)。"""
        self.assertEqual(self.codes("import os\n\nif TYPE_CHECKING:\n    import json\n\nimport sys"), ["L006"])
        self.assertEqual(self.codes("import os\nimport sys\n\nif TYPE_CHECKING:\n    import json"), [])
        self.assertEqual(self.codes("import os\n\nif typing.TYPE_CHECKING:\n    import json\n\nimport sys"), ["L006"])


class ProjectRuleLayoutTest(unittest.TestCase):
    """内部名・例外・fast・docstring・Python版の規則を、ruffと重ならない範囲で検査する。"""

    def codes(self, text, filename="sample.py", prefix="L0"):
        source = layout.Source(Path(filename), textwrap.dedent(text).strip() + "\n")
        return sorted({v.code for v in layout.check_source(source) if v.code.startswith(prefix)})

    def only(self, text, code, filename="sample.py"):
        """指定したコードだけを抜き出す(他の規則の指摘を混ぜない)。"""
        return [c for c in self.codes(text, filename) if c == code]

    def test_banned_internal_prefixes_and_kept_protocol_names(self):
        """検証・判定・変換の内部名は規則の接頭辞に揃え、登録プロトコル名は維持する。"""
        for name in ("_check_data", "_validate_data", "_as_matrix", "_coerce_value", "_fast_set_value"):
            with self.subTest(name=name):
                self.assertEqual(self.only(f"def {name}(value):\n    pass", "L050"), ["L050"])
        for name in ("_require_data", "_validated_data", "_is_valid", "_has_input", "_resolve_input", "_set_value_fast", "_validate_inputs"):
            with self.subTest(name=name):
                self.assertEqual(self.only(f"def {name}(value):\n    pass", "L050"), [])

    def test_direct_is_banned_only_as_a_write_branch_name(self):
        """``_direct`` は書込みの分岐名としてだけ禁止し、「直接の子」のような語は許す。"""
        self.assertEqual(self.only("def _set_value_direct(value):\n    pass", "L050"), ["L050"])
        self.assertEqual(self.only("def _direct_children(node):\n    pass", "L050"), [])

    def test_function_set_uses_its_getter(self):
        """専用の取得メソッドがある function set は直接作らない。"""
        text = """
        class Example:
            def getName(self):
                return om2.MFnDependencyNode(self.mnode()).name()
        """
        self.assertEqual(self.only(text, "L051"), ["L051"])
        for body in ("return self._dependency_fn().name()", "return om2.MFnDependencyNode(other.mnode()).name()"):
            with self.subTest(body=body):
                self.assertEqual(self.only(f"class Example:\n    def getName(self):\n        {body}", "L051"), [])

    def test_function_set_getter_definitions_are_allowed(self):
        """取得メソッド自身(``mfn``・``_<kind>_fn``)は対象外。"""
        for name in ("mfn", "_dependency_fn"):
            with self.subTest(name=name):
                text = f"class Example:\n    def {name}(self):\n        return om2.MFnDependencyNode(self.mnode())"
                self.assertEqual(self.only(text, "L051"), [])

    def test_inner_import_needs_a_reason_comment(self):
        """関数内importは直前に理由を書き、連続した群は先頭の1つでよい。"""
        self.assertEqual(self.only("def run():\n    from .other import Thing\n    return Thing", "L052"), ["L052"])
        self.assertEqual(self.only("def run():\n    # 循環参照の回避。\n    from .other import Thing\n    return Thing", "L052"), [])
        self.assertEqual(self.only("def run():\n    # 循環参照の回避。\n    from .a import A\n    from .b import B\n    return A, B", "L052"), [])
        self.assertEqual(self.only("from .other import Thing\n\n\ndef run():\n    return Thing", "L052"), [])

    def test_exception_messages_are_english_f_strings(self):
        """例外の文言は英語で、f-string 1つにまとめる。"""
        self.assertEqual(self.only('def run(value):\n    raise TypeError("value must be a bool")', "L060"), [])
        self.assertEqual(self.only('def run(value):\n    raise TypeError("値はboolにしてください")', "L060"), ["L060"])
        self.assertEqual(self.only('def run(value):\n    raise ValueError("bad: " + str(value))', "L061"), ["L061"])
        self.assertEqual(self.only('def run(value):\n    raise ValueError(f"bad: {value}")', "L061"), [])

    def test_notify_and_raise_are_not_combined(self):
        """例外を送出する処理で logger.error を重ねない。"""
        self.assertEqual(self.only('def run():\n    logger.error("failed")\n    raise RuntimeError("failed")', "L062"), ["L062"])
        self.assertEqual(self.only('def run():\n    logger.warning("failed")\n    raise RuntimeError("failed")', "L062"), [])

    def test_undo_chunk_name_shape(self):
        """Undoチャンク名は ``mlib<Class><Method>`` の形にする。"""
        for name in ("mlibNode.setName", "mlib_node_set_name", "setName", "mlibsetName"):
            with self.subTest(name=name):
                self.assertEqual(self.only(f'def run():\n    with _edit_context("{name}", False):\n        pass', "L063"), ["L063"])
        self.assertEqual(self.only('def run():\n    with _edit_context("mlibNodeSetName", False):\n        pass', "L063"), [])

    def test_fast_must_be_validated_or_forwarded(self):
        """fast を受ける公開メソッドは、検証か転送のどちらかを必ず行う。"""
        text = "class Example:\n    def setValue(self, value, *, fast=False):\n        self._write(value)"
        self.assertEqual(self.only(text, "L064"), ["L064"])
        for body in ('_require_bool(fast, "fast")', 'with _edit_context("mlibExampleSetValue", fast):\n            pass', "self._write(value, fast=fast)"):
            with self.subTest(body=body):
                self.assertEqual(self.only(f"class Example:\n    def setValue(self, value, *, fast=False):\n        {body}", "L064"), [])

    def test_docstring_sections_raises_order_and_summary(self):
        """見出しの順・Raisesの並び・1行目の句点を検査する。"""
        good = '''
        def run(value):
            """値を設定する。

            Args:
                value (int): 値。

            Returns:
                None: 値を返さない。

            Raises:
                TypeError: valueがint以外の場合。
                ValueError: valueが負の場合。
                RuntimeError: シーンが更新を拒否した場合。
            """
        '''
        self.assertEqual(self.codes(good, prefix="L07"), [])
        swapped = good.replace("TypeError: valueがint以外の場合。", "ZZ").replace("ValueError: valueが負の場合。", "TypeError: valueがint以外の場合。")
        self.assertEqual(self.only(swapped.replace("ZZ", "ValueError: valueが負の場合。"), "L071"), ["L071"])
        self.assertEqual(self.only('def run():\n    """値を設定する"""', "L072"), ["L072"])

    def test_fast_docstring_uses_the_fixed_sentence(self):
        """fastの説明は固定文で始める。"""
        fixed = layout.FIXED_FAST_TEXT
        text = f'class Example:\n    def setValue(self, *, fast=False):\n        """設定する。\n\n        Args:\n            {fixed}\n        """\n        self._write(fast=fast)'
        self.assertEqual(self.only(text, "L073"), [])
        other = text.replace(fixed, "fast (bool): TrueはOpenMayaで直接更新する。")
        self.assertEqual(self.only(other, "L073"), ["L073"])

    def test_banned_terms_in_docstrings(self):
        """docstringの用語を揃える(番号・データ型名・コンパウンドアトリビュート)。"""
        for word in ("インデックス", "添字", "配列", "複合アトリビュート"):
            with self.subTest(word=word):
                self.assertEqual(self.only(f'def run():\n    """{word}を返す。"""', "L074"), ["L074"])
        self.assertEqual(self.only('def run():\n    """論理番号の list を返す。"""', "L074"), [])

    def test_public_constants_need_a_description(self):
        """公開定数は ``#:`` か直後の文字列で説明する。"""
        self.assertEqual(self.only("LIMIT = 1\n\n\ndef run():\n    pass", "L075"), ["L075"])
        self.assertEqual(self.only("#: 上限。\nLIMIT = 1\n\n\ndef run():\n    pass", "L075"), [])
        self.assertEqual(self.only('LIMIT = 1\n"""int: 上限。"""\n\n\ndef run():\n    pass', "L075"), [])
        self.assertEqual(self.only("_LIMIT = 1\n\n\ndef run():\n    pass", "L075"), [])

    def test_docstring_arguments_match_the_signature(self):
        """Args:の名前が引数と一致し、キーワード専用の順と可変長は問わない。"""
        good = '''
        def run(value, worldSpace=False, *, fast=False, ws=False, **space):
            """値を設定する。

            Args:
                value (int): 値。
                worldSpace (bool): ワールド空間。
                ws (bool): worldSpaceの短縮名。
                fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            """
        '''
        self.assertEqual(self.only(good, "L076"), [])
        extra = good.replace("                ws (bool)", "                depth (bool): 無い引数。\n                ws (bool)")
        self.assertEqual(self.only(extra, "L076"), ["L076"])
        lacking = good.replace("                worldSpace (bool): ワールド空間。\n", "")
        self.assertEqual(self.only(lacking, "L076"), ["L076"])
        wrapped = good.replace("                value (int): 値。", "                value (int): 値。詳しくは\n                    index: 番号ではない。")
        self.assertEqual(self.only(wrapped, "L076"), [])
        self.assertEqual(self.only('def run(value):\n    """値を設定する。"""', "L076"), [])

    def test_docstring_arguments_read_wrapped_types_and_first_arguments(self):
        """型が次の行へ折り返した項目を読み、self・clsは書いても省いてもよい。"""
        folded = '''
        def run(items):
            """保持する。

            Args:
                items (Iterable[Node | Plug | Component |
                    om2.MObject]): 対象。
            """
        '''
        self.assertEqual(self.only(folded, "L076"), [])
        for text in ('def _new(cls):\n    """作る。\n\n    Args:\n        cls (type): クラス。\n    """', 'def _new(cls):\n    """作る。"""'):
            with self.subTest(text=text):
                self.assertEqual(self.only(text, "L076"), [])
        method = 'class Example:\n    def run(self, value):\n        """設定する。\n\n        Args:\n            value (int): 値。\n        """'
        self.assertEqual(self.only(method, "L076"), [])

    def test_docstring_positional_arguments_keep_the_signature_order(self):
        """位置引数はdocstringでも署名と同じ順に書く。"""
        good = '''
        def run(first, second, *, fast=False):
            """設定する。

            Args:
                first (int): 1つ目。
                second (int): 2つ目。
                fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            """
        '''
        self.assertEqual(self.only(good, "L076"), [])
        swapped = good.replace(
            "                first (int): 1つ目。\n                second (int): 2つ目。",
            "                second (int): 2つ目。\n                first (int): 1つ目。",
        )
        self.assertEqual(self.only(swapped, "L076"), ["L076"])

    def test_docstring_template_follows_the_signature_and_body(self):
        """テンプレートは引数の並び・固定文・Returns/Raisesを署名と本文から決める。"""
        text = """
        def setPosition(value, worldSpace=False, *, fast=False, ws=False, **space):
            if value is None:
                raise TypeError("none")
            if not value:
                raise ValueError("empty")
            return value
        """
        node = ast.parse(textwrap.dedent(text).strip() + "\n").body[0]
        lines = layout.docstring_template(node)
        self.assertEqual(lines[0], layout.TEMPLATE_SUMMARY)
        self.assertEqual(
            [line.strip() for line in lines if line.startswith("    ")],
            [
                "value: TODO。",
                "worldSpace: TODO。",
                layout.FIXED_ARGUMENT_TEXTS["ws"],
                layout.FIXED_FAST_TEXT,
                "**space: TODO。",
                layout.TEMPLATE_MARK,
                "TypeError: TODO。",
                "ValueError: TODO。",
            ],
        )
        self.assertEqual(lines.index("Returns:") > lines.index("Args:"), True)

    def test_docstring_template_marks_generators_and_void_returns(self):
        """``yield`` はYields、値を返さない処理は固定文のReturnsにする。"""
        generator = ast.parse("def run(kind):\n    for item in kind:\n        yield item\n").body[0]
        self.assertEqual(layout.docstring_template(generator)[-2:], ["Yields:", "    " + layout.TEMPLATE_MARK])
        void = ast.parse("def run():\n    pass\n").body[0]
        self.assertEqual(layout.docstring_template(void)[-2:], ["Returns:", "    " + layout.FIXED_NO_RETURN_TEXT])

    def test_docstring_template_insertion_keeps_existing_docstrings(self):
        """docstringが無いdefにだけ入れ、本文を同じ行に書いたdefは対象にしない。"""
        text = 'def run(value):\n    return value\n\n\ndef kept():\n    """残す。"""\n    return 1\n\n\ndef oneline(): return 2\n'
        fixed, inserted = layout.insert_docstring_templates(layout.Source(Path("sample.py"), text))
        self.assertEqual([name for name, _ in inserted], ["run"])
        self.assertIn('"""残す。"""', fixed)
        self.assertEqual(fixed.count(layout.TEMPLATE_SUMMARY), 1)
        layout.Source(Path("sample.py"), fixed)

    def test_remaining_template_mark_is_informational(self):
        """埋め忘れた印はL077で報告し、違反としては数えない。"""
        text = f'def run():\n    """{layout.TEMPLATE_SUMMARY}\n\n    Returns:\n        {layout.FIXED_NO_RETURN_TEXT}\n    """'
        self.assertEqual(self.only(text, "L077"), ["L077"])
        self.assertIn("L077", layout.INFORMATIONAL)
        self.assertEqual(self.only(text.replace(layout.TEMPLATE_SUMMARY, "値を設定する。"), "L077"), [])

    def test_python_37_syntax_and_annotations(self):
        """Maya 2022(Python 3.7)で動かない書き方を検出する。"""
        for text in ("def run(values):\n    if (first := values[0]):\n        return first", "def run(value, /):\n    return value"):
            with self.subTest(text=text):
                self.assertEqual(self.only(text, "L080"), ["L080"])
        self.assertEqual(self.only('def run(value):\n    print(f"{value=}")', "L080"), ["L080"])
        self.assertEqual(self.only("def run(values: list[int]):\n    return values", "L080"), ["L080"])
        self.assertEqual(self.only("def run(value: int | str):\n    return value", "L080"), ["L080"])
        self.assertEqual(self.only('def run(values: "List[int]"):\n    return values', "L080"), [])

    def test_property_getter_does_not_query_maya(self):
        """propertyのgetterでMayaへ問い合わせない。"""
        for body in ("return cmds.nodeType(self._name)", "return om2.MFnDagNode(self._path).name()"):
            with self.subTest(body=body):
                self.assertEqual(self.only(f"class Example:\n    @property\n    def name(self):\n        {body}", "L081"), ["L081"])
        self.assertEqual(self.only("class Example:\n    @property\n    def index(self):\n        return self._index", "L081"), [])


class ModernPracticeLayoutTest(unittest.TestCase):
    """入力検証の候補、手動レビュー、明示的なassert修正の境界を確認する。"""

    def source(self, text, filename="sample.py"):
        return layout.Source(Path(filename), textwrap.dedent(text).strip() + "\n")

    def codes(self, text, filename="sample.py"):
        return [v.code for v in layout.check_source(self.source(text, filename)) if v.code in {"L040", "L041"}]

    def test_public_input_guards_and_constructors(self):
        """公開関数とconstructorの冒頭の引数検証を検出する。"""
        for text in (
            "def run(value):\n    assert value > 0",
            "class Example:\n    def __init__(self, value):\n        assert isinstance(value, int)",
            'def run(*, value):\n    """概要。"""\n    assert value is not None',
        ):
            with self.subTest(text=text):
                self.assertIn("L040", self.codes(text))
        self.assertIn("L040", self.codes("def run(value):\n    assert value", "__init__.py"))

    def test_internal_invariants_and_test_assertions_are_allowed(self):
        """内部関数・selfの状態・計算後の確認・テストは入力検証にしない。"""
        for text in (
            "def _run(value):\n    assert value",
            "class _Example:\n    def run(self, value):\n        assert value",
            "class Example:\n    def run(self, value):\n        assert self.ready",
            "def run(value):\n    result = convert(value)\n    assert result",
        ):
            with self.subTest(text=text):
                self.assertNotIn("L040", self.codes(text))
        for filename in ("test_example.py", "tests/example.py", "pkg/__tests__/example.py", "_internal.py"):
            self.assertNotIn("L040", self.codes("def run(value):\n    assert value", filename))

    def test_selected_assert_fix_keeps_message_and_other_invariants(self):
        """選んだassertだけを変え、後続の内部確認は保持する。"""
        source = self.source("""
            def run(value):
                assert isinstance(value, int), "整数を指定してください"
                result = value + 1
                assert result != 0
                return result
        """)
        fixed = layout.rewrite_input_asserts(source, [2], "TypeError")
        namespace = {}
        exec(compile(fixed, "sample.py", "exec", optimize=2), namespace)
        self.assertEqual(namespace["run"](2), 3)
        with self.assertRaisesRegex(TypeError, "整数を指定してください"):
            namespace["run"]("bad")
        self.assertIn("assert result != 0", fixed)
        self.assertNotIn("L040", self.codes(fixed))

    def test_assert_fix_message_is_evaluated_only_on_failure(self):
        """assertのメッセージ評価を失敗時1回のまま保つ。"""
        source = self.source("def run(value, message):\n    assert value > 0, message()\n    return value")
        fixed = layout.rewrite_input_asserts(source, [2], "ValueError")
        namespace = {}
        exec(fixed, namespace)
        calls = []

        def message():
            calls.append(1)
            return "不正な値"

        namespace["run"](1, message)
        self.assertEqual(calls, [])
        with self.assertRaisesRegex(ValueError, "不正な値"):
            namespace["run"](0, message)
        self.assertEqual(calls, [1])

    def test_assert_fix_handles_multiline_and_no_message(self):
        source = self.source("def run(value):\n    assert (\n        value > 0\n    )\n    return value")
        fixed = layout.rewrite_input_asserts(source, [2], "ValueError")
        namespace = {}
        exec(fixed, namespace)
        with self.assertRaises(ValueError) as raised:
            namespace["run"](0)
        self.assertEqual(raised.exception.args, ())

    def test_assert_fix_refuses_shared_lines_comments_and_unknown_selection(self):
        for text in (
            "def run(value): assert value",
            "def run(value):\n    assert value; return value",
            "def run(value):\n    assert value  # 説明",
            "def run(value):\n    assert (\n        value  # 説明\n    )",
        ):
            source = self.source(text)
            selected = layout.public_input_asserts(source)[0].lineno
            with self.subTest(text=text), self.assertRaises(ValueError):
                layout.rewrite_input_asserts(source, [selected], "ValueError")
        source = self.source("def run(value):\n    assert value")
        for lines, error in (([], "ValueError"), ([2, 99], "ValueError"), ([2], "RuntimeError")):
            with self.assertRaises(ValueError):
                layout.rewrite_input_asserts(source, lines, error)

    def test_enumerate_candidate_is_informational(self):
        text = "for index in range(len(nodes)):\n    print(index, nodes[index])"
        self.assertIn("L041", self.codes(text))
        self.assertIn("L041", layout.INFORMATIONAL)

    def test_assert_fix_refuses_shadowed_exception_names(self):
        for text in (
            "def run(value, TypeError):\n    assert value",
            "TypeError = CustomError\ndef run(value):\n    assert value",
            "from errors import TypeError\ndef run(value):\n    assert value",
        ):
            source = self.source(text)
            selected = layout.public_input_asserts(source)[0].lineno
            with self.subTest(text=text), self.assertRaises(ValueError):
                layout.rewrite_input_asserts(source, [selected], "TypeError")

    def test_index_algorithms_and_updates_are_not_simple_enumeration(self):
        for body in ("nodes[index] = index", "print(nodes[index + 1])", "print(index)", "nodes.append(nodes[index])", "del nodes[index]", "nodes[index] += 1"):
            with self.subTest(body=body):
                self.assertNotIn("L041", self.codes("for index in range(len(nodes)):\n    " + body))
        self.assertNotIn("L041", self.codes("for index in range(len(nodes) - 1):\n    print(nodes[index])"))

    def test_assert_cli_requires_explicit_selection_and_keeps_bom_crlf(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "example.py"
            original = b'\xef\xbb\xbfdef run(value):\r\n    assert value > 0, "positive"\r\n    return value\r\n'
            path.write_bytes(original)
            base = [sys.executable, layout.__file__, "--fix-asserts", "ValueError", str(path)]
            result = subprocess.run(base, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(path.read_bytes(), original)
            result = subprocess.run(base + ["--line", "2", "--line", "99"], capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(path.read_bytes(), original)
            result = subprocess.run(base + ["--line", "2"], capture_output=True)
            self.assertEqual(result.returncode, 0)
            data = path.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
            self.assertIn(b"raise ValueError", data)

    def test_cli_returns_failure_for_input_assert_and_passes_review_candidates(self):
        """入力assertは終了コード1、意味の確認が必要な候補は情報として0を返す。"""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "example.py"
            base = [sys.executable, layout.__file__, "--check", str(path)]
            path.write_text("def run(value):\n    assert value > 0\n", encoding="utf-8")
            result = subprocess.run(base, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"L040", result.stdout)
            original = "for index in range(len(nodes)):\n    print(index, nodes[index])\n"
            path.write_text(original, encoding="utf-8")
            result = subprocess.run(base, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn(b"L041", result.stdout)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
