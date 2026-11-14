"""明示的なNode/Plug登録と、入力に応じた型選択をMaya内で検証する。

あわせて次も確かめる。

- mlib.core の Object・NodeRegistry・extensions・reload_package の約束を固定する仕様テスト(担当D)。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.core.registry import NodeRegistry, _inherited_node_types
from mlib.nodes import Joint, Node, Transform


class _FallbackClass:
    def __init__(self, value=None):
        self.value = value


class _RegisteredClass:
    def __init__(self, value=None):
        self.value = value


class NodeRegistryTest(unittest.TestCase):
    """register/lookup/wrapper_class/clear/replace の基本動作を検証する。"""

    def setUp(self):
        self.registry = NodeRegistry(_FallbackClass)

    def test_unregistered_type_falls_back_and_lookup_returns_none(self):
        self.assertIs(self.registry.wrapper_class("unregisteredType"), _FallbackClass)
        self.assertIs(self.registry.wrapper_class("unregisteredType"), _FallbackClass)
        self.assertIsNone(self.registry.lookup("unregisteredType"))

    def test_register_and_get(self):
        self.registry.register("myType", _RegisteredClass)
        self.assertIs(self.registry.wrapper_class("myType"), _RegisteredClass)
        self.assertIs(self.registry.lookup("myType"), _RegisteredClass)
        self.assertIs(self.registry.wrapper_class("otherType"), _FallbackClass)

    def test_register_rejects_invalid_input(self):
        with self.assertRaises(ValueError):
            self.registry.register("", _RegisteredClass)
        with self.assertRaises(TypeError):
            self.registry.register("myType", object())

    def test_clear_removes_all_registrations(self):
        self.registry.register("myType", _RegisteredClass)
        self.registry.clear()
        self.assertIs(self.registry.wrapper_class("myType"), _FallbackClass)

    def test_replace_replaces_existing_registrations(self):
        self.registry.register("staleType", _RegisteredClass)
        self.registry.replace({"myType": _RegisteredClass})
        self.assertIs(self.registry.wrapper_class("staleType"), _FallbackClass)
        self.assertIs(self.registry.wrapper_class("myType"), _RegisteredClass)

    def test_replace_validates_all_entries_before_changing_registry(self):
        """不正な後続エントリーで、既存登録を失わず部分登録もしない。"""
        self.registry.register("staleType", _RegisteredClass)
        for invalid, exception in (
            ({"validType": _FallbackClass, "": _RegisteredClass}, ValueError),
            ({"validType": _FallbackClass, "invalidType": object()}, TypeError),
        ):
            with self.assertRaises(exception):
                self.registry.replace(invalid)
            self.assertIs(self.registry.lookup("staleType"), _RegisteredClass)
            self.assertIsNone(self.registry.lookup("validType"))


class NodeRegistryInheritedTypesTest(unittest.TestCase):
    """resolve_inherited_types=True 時の継承チェーン経由の解決を検証する(実際のMayaノードタイプ継承を使う)。"""

    def test_falls_back_to_nearest_registered_ancestor(self):
        registry = NodeRegistry(_FallbackClass, resolve_inherited_types=True)
        registry.register("transform", _RegisteredClass)
        # joint は transform を継承する組み込みノードタイプ。joint 自体は未登録。
        self.assertIs(registry.wrapper_class("joint"), _RegisteredClass)

    def test_disabled_by_default_ignores_inheritance(self):
        registry = NodeRegistry(_FallbackClass)
        registry.register("transform", _RegisteredClass)
        self.assertIs(registry.wrapper_class("joint"), _FallbackClass)

    def test_exact_match_takes_precedence_over_ancestor(self):
        class _JointClass:
            pass

        registry = NodeRegistry(_FallbackClass, resolve_inherited_types=True)
        registry.register("transform", _RegisteredClass)
        registry.register("joint", _JointClass)
        self.assertIs(registry.wrapper_class("joint"), _JointClass)

    def test_unrecognized_type_falls_back_without_raising(self):
        registry = NodeRegistry(_FallbackClass, resolve_inherited_types=True)
        registry.register("transform", _RegisteredClass)
        self.assertIs(registry.wrapper_class("mlibBogusTypeXYZ"), _FallbackClass)

    def test_no_ancestor_registered_falls_back(self):
        registry = NodeRegistry(_FallbackClass, resolve_inherited_types=True)
        # locator の系統には何も登録しないため、フォールバックのままになる。
        self.assertIs(registry.wrapper_class("locator"), _FallbackClass)


class NodeTypeHierarchyTest(unittest.TestCase):
    """mlib.core.registry._inherited_node_types の照会・キャッシュを検証する。"""

    def test_chain_is_self_first_then_ancestors_toward_base(self):
        chain = _inherited_node_types("joint")
        self.assertEqual(chain[0], "joint")
        self.assertEqual(chain[-1], "containerBase")
        self.assertIn("transform", chain)
        self.assertLess(chain.index("transform"), chain.index("containerBase"))

    def test_unrecognized_type_returns_itself_only(self):
        self.assertEqual(_inherited_node_types("mlibBogusTypeXYZ"), ("mlibBogusTypeXYZ",))

    def test_repeated_calls_return_cached_equal_result(self):
        first = _inherited_node_types("locator")
        second = _inherited_node_types("locator")
        self.assertEqual(first, second)


class ExplicitRegistrationsTest(unittest.TestCase):
    """公開一覧から独立した明示的な型対応表を検証する。"""

    def test_node_table_matches_initialized_registry(self):
        """Nodeの型対応表に書いたクラスを既存の取得入口で選択する。"""
        registry = mlib.Node._registry
        for node_type, wrapper in mlib.nodes._WRAPPER_CLASSES.items():
            self.assertIs(registry.lookup(node_type), wrapper)
        self.assertIs(registry.wrapper_class("joint"), mlib.Joint)
        self.assertIs(registry.wrapper_class("mesh"), mlib.Mesh)

    def test_plug_table_matches_initialized_registry(self):
        """Plugの型対応表が公開クラスの登録漏れなく初期化される。"""
        registry = mlib.Plug._registry
        for attr_type, wrapper in mlib.plugs._WRAPPER_CLASSES.items():
            self.assertIs(registry.lookup(attr_type), wrapper)
        self.assertIs(registry.lookup("double"), mlib.DoublePlug)

    def test_publication_does_not_require_metadata_decorators(self):
        """公開・登録済みクラスへ旧自動検出用メタデータを要求しない。"""
        for wrapper in (mlib.Joint, mlib.Joints, mlib.DoublePlug):
            for name in ("__mlib_node_type__", "__mlib_plug_type__", "__mlib_public__", "__mlib_collection__"):
                self.assertNotIn(name, wrapper.__dict__)


class NodeRegistrySpecTest(unittest.TestCase):
    """独立したNodeRegistryで登録・検証・祖先型の解決を固定する。"""

    class Fallback:
        """フォールバック用のクラス。"""

    class TransformLike:
        """transform用のクラス。"""

    class DagLike:
        """dagNode用のクラス。"""

    def test_exact_lookup_and_fallback(self):
        """完全一致は登録クラス、未登録はフォールバック。lookupはNoneを返す。"""
        registry = NodeRegistry(self.Fallback)
        registry.register("transform", self.TransformLike)
        self.assertIs(registry.wrapper_class("transform"), self.TransformLike)
        self.assertIs(registry.wrapper_class("transform"), self.TransformLike)
        self.assertIs(registry.wrapper_class("joint"), self.Fallback)
        self.assertIsNone(registry.lookup("joint"))
        self.assertIs(registry.lookup("transform"), self.TransformLike)

    def test_inherited_types_use_nearest_ancestor(self):
        """継承検索を有効にした表は、Mayaの型継承で最も近い登録済み祖先を返す。"""
        registry = NodeRegistry(self.Fallback, resolve_inherited_types=True)
        registry.register("dagNode", self.DagLike)
        registry.register("transform", self.TransformLike)
        self.assertIn("transform", cmds.nodeType("joint", isTypeName=True, inherited=True))
        self.assertIs(registry.wrapper_class("joint"), self.TransformLike)
        self.assertIs(registry.wrapper_class("mesh"), self.DagLike)
        self.assertIs(registry.wrapper_class("network"), self.Fallback)
        self.assertIs(registry.wrapper_class("mlibNoSuchType"), self.Fallback)
        self.assertIsNone(registry.lookup("joint"))

    def test_validation_and_atomic_replace(self):
        """キーは空でない文字列(非strはTypeError・空はValueError)、値はクラス。replaceは全件検証し、失敗時は現在の登録を保つ。"""
        registry = NodeRegistry(self.Fallback)
        with self.assertRaises(ValueError):
            registry.register("", self.TransformLike)
        for key in (None, 5):
            with self.assertRaises(TypeError):
                registry.register(key, self.TransformLike)
        with self.assertRaises(TypeError):
            registry.register("transform", self.TransformLike())
        registry.register("transform", self.TransformLike)
        registry.register("transform", self.DagLike)
        self.assertIs(registry.lookup("transform"), self.DagLike)
        with self.assertRaises(TypeError):
            registry.replace({"joint": self.TransformLike, "mesh": "notAClass"})
        self.assertIs(registry.lookup("transform"), self.DagLike)
        self.assertIsNone(registry.lookup("joint"))
        registry.replace({"joint": self.TransformLike})
        self.assertIsNone(registry.lookup("transform"))
        registry.clear()
        self.assertIsNone(registry.lookup("joint"))
        self.assertIs(registry.wrapper_class("joint"), self.Fallback)

    def test_global_node_registry(self):
        """本体のNode登録表はjointをJointへ、未登録の型を登録済みの祖先型へ解決する。"""
        registry = Node._registry
        self.assertIs(registry.lookup("joint"), Joint)
        self.assertIs(registry.wrapper_class("transform"), Transform)
        chain = cmds.nodeType("joint", isTypeName=True, inherited=True)
        self.assertEqual(chain[-1], "joint")
        resolved = registry.wrapper_class("mlibNoSuchType")
        self.assertIs(resolved, Node)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
