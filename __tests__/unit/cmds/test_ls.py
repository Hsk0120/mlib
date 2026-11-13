"""``mlib.cmds.ls`` のテスト。

- 約束の変更・不具合の修正(担当C)を実Mayaで検証する。
- mlib.cmds の7入口(getNode・getPlug・createNode・ls・delete・duplicate・select)の仕様テスト(担当D)。
"""

import sys
import time
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common.selection import _resolve_names, Selection
from mlib.components import Vertex, Vertices
from mlib.nodes import AnimCurve, Joints, Node, Nodes, ObjectSet, SkinClusters
from mlib.plugs import Plug, Plugs
from support.namespaceCase import NamespaceCase


class _ContractCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibContractC_"
    ENABLE_UNDO = False


class LsBulkResolveTest(_ContractCase):
    """ls の名前をまとめて解決しても、並び順と結果が cmds・名前ごとの解決と同じになることを確かめる。"""

    def setUp(self):
        super().setUp()
        self.group_a = cmds.group(empty=True, name=self.name("grpA"))
        self.group_b = cmds.group(empty=True, name=self.name("grpB"))
        box = cmds.polyCube(name=self.name("box"))[0]
        box = cmds.parent(box, self.group_a)[0]
        cmds.parent(cmds.ls(box, long=True)[0], self.group_b, addObject=True)
        self.dg = [cmds.createNode("addDoubleLinear", name=self.name("adl%d" % i)) for i in range(3)]
        self.transforms = [cmds.createNode("transform", name=self.name("t%02d" % i)) for i in range(40)]

    def test_order_matches_cmds(self):
        """16件を超える名前でも、cmds.ls の返した順に同じ完全名の参照を返す。"""
        names = list(reversed(self.transforms)) + self.dg
        expected = cmds.ls(names, long=True)
        self.assertEqual([item.getFullName() for item in mlib.ls(names, long=True)], expected)
        pattern = self.ns + ":*"
        self.assertEqual([str(item) for item in mlib.ls(pattern)], cmds.ls(pattern))

    def test_instances_and_plugs(self):
        """インスタンスの全パスと、インスタンスのアトリビュートの所有パスを名前ごとの解決と同じにする。"""
        paths = cmds.ls(self.ns + ":box", allPaths=True, long=True)
        self.assertEqual(len(paths), 2)
        self.assertEqual([item.getFullName() for item in mlib.ls(self.ns + ":box", allPaths=True, long=True)], paths)
        shape = paths[1] + "|" + self.ns + ":boxShape"
        names = [shape + ".castsShadows", paths[0] + ".worldMatrix[1]", self.dg[0] + ".input1",
                 self.transforms[0] + ".tx"]
        result = mlib.ls(names)
        # 所有インスタンスは cmds.ls が返した名前で決まるため、その名前を1件ずつ解決した結果と比べる。
        returned = cmds.ls(names)
        self.assertEqual(len(result), len(returned))
        self.assertTrue(all(isinstance(item, Plug) for item in result))
        for item, name in zip(result, returned):
            expected = mlib.getPlug(name)
            self.assertEqual(item.getNode().getFullName(), expected.getNode().getFullName())
            self.assertEqual(str(item), str(expected))

    def test_components_keep_old_path(self):
        """コンポーネントはまとめた解決の対象外で、従来どおり単体へ展開する。"""
        box = cmds.ls(self.ns + ":box", allPaths=True, long=True)[0]
        result = mlib.ls(box + ".vtx[0:2]", self.transforms[0] + ".tx", box + ".vtx[5]", flatten=True)
        self.assertEqual(sum(isinstance(item, Vertex) for item in result), 4)
        self.assertEqual([isinstance(item, Plug) for item in result].count(True), 1)
        self.assertEqual([item.index for item in result if isinstance(item, Vertex)], [0, 1, 2, 5])

    def test_duplicates_are_not_merged(self):
        """同じ名前を重ねて渡しても、選択リストの統合で結果を減らさない。"""
        name = self.transforms[0]
        found = _resolve_names([name, name, self.transforms[1]])
        self.assertIsNotNone(found[0])
        self.assertIsNone(found[1])
        self.assertIsNotNone(found[2])
        self.assertEqual([item.getFullName() for item in Selection([name, self.transforms[1], name])],
                         cmds.ls([name, self.transforms[1]], long=True))

    def test_unresolved_names_keep_errors(self):
        """解決できない名前は、従来の名前ごとの経路の例外のまま。"""
        with self.assertRaises(RuntimeError):
            Selection([self.transforms[0], self.name("missing")])
        self.assertEqual(_resolve_names([self.name("missing"), self.ns + ":t*"]), [None, None])

    def test_selection_order(self):
        """Selection の保持順は入力の順で、ワイルドカードと混ぜても名前ごとの解決と同じ。"""
        names = [self.transforms[3], self.dg[1], self.ns + ":t0*", self.transforms[1]]
        expected = []
        for name in names:
            for full in cmds.ls(name, long=True):
                if full not in expected:
                    expected.append(full)
        self.assertEqual([item.getFullName() for item in Selection(names)], expected)

    def test_time_scales_linearly(self):
        """名前の数を16倍にしても、1件あたりの時間が大きく増えない(件数の2乗にならない)。"""
        many = [cmds.createNode("transform", name=self.name("bulk%d" % i)) for i in range(3200)]

        def per_item(names):
            best = None
            for _ in range(5):
                start = time.perf_counter()
                _resolve_names(names)
                elapsed = time.perf_counter() - start
                best = elapsed if best is None else min(best, elapsed)
            return best / len(names)

        small = per_item(many[:200])
        large = per_item(many)
        # 件数の2乗なら1件あたり約16倍になる。他の処理と同時に動くと揺れるため、上限は6倍に取る。
        self.assertLess(large, small * 6.0, (small, large))


class _CmdsCase(unittest.TestCase):
    """一時名前空間・選択・Undo設定の保存と復元を共通にする。"""

    def setUp(self):
        """一時名前空間を作り、選択とUndo設定を保存する。"""
        self.undo_state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(stateWithoutFlush=True)
        self.selection = cmds.ls(selection=True, long=True)
        self.ns = "mlibSpecDCmds_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)

    def tearDown(self):
        """一時名前空間を中身ごと削除し、選択とUndo設定を戻す。"""
        cmds.select(clear=True)
        if cmds.namespace(exists=self.ns):
            for node in cmds.ls(self.ns + ":*", long=True) or []:
                if cmds.objExists(node) and cmds.lockNode(node, query=True, lock=True)[0]:
                    cmds.lockNode(node, lock=False)
            cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        existing = [name for name in self.selection if cmds.objExists(name)]
        if existing:
            cmds.select(existing, replace=True)
        cmds.undoInfo(state=self.undo_state)

    def name(self, leaf):
        """一時名前空間内の名前を返す。"""
        return self.ns + ":" + leaf

    def transforms(self):
        """一時名前空間内のtransformの数を返す。"""
        return len(cmds.ls(self.ns + ":*", type="transform") or [])


class LsSpecTest(_CmdsCase):
    """lsの戻り値の型・順序とcmds.lsとの一致を固定する。"""

    def setUp(self):
        """検索対象のノードを作る。"""
        super().setUp()
        self.joints = [cmds.createNode("joint", name=self.name("j%d" % i)) for i in range(3)]
        self.cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]

    def test_order_and_names_match_cmds(self):
        """結果の並びと名前はcmds.ls(long=True)と一致する。"""
        for kwargs in (dict(type="transform"), dict(long=True), dict(dag=True), dict(sn=True)):
            result = mlib.ls(self.ns + ":*", **kwargs)
            self.assertIsInstance(result, Nodes)
            expected = cmds.ls(self.ns + ":*", long=True, **{k: v for k, v in kwargs.items() if k not in ("long", "sn")})
            self.assertEqual([item.getFullName() for item in result], expected, msg=repr(kwargs))
            self.assertTrue(all(isinstance(item, Node) for item in result))

    def test_special_collections(self):
        """type/typがjointならJoints、skinClusterならSkinClusters。結果がなければ空の同型。"""
        joints = mlib.ls(self.ns + ":*", type="joint")
        self.assertIsInstance(joints, Joints)
        self.assertEqual(len(joints), 3)
        self.assertIsInstance(mlib.ls(self.ns + ":*", typ="joint"), Joints)
        empty = mlib.ls(self.ns + ":*", type="skinCluster")
        self.assertIsInstance(empty, SkinClusters)
        self.assertEqual(len(empty), 0)

    def test_empty_inputs(self):
        """Noneや空の列だけなら全ノードを検索せず空のNodesを返す。コンポーネント型指定の0件も空のNodes。"""
        for result in (mlib.ls([]), mlib.ls(None), mlib.ls(self.name("missing*")),
                       mlib.ls(self.name("missing*"), type="transform"),
                       mlib.ls(self.name("missing*"), type="vertex")):
            self.assertIs(type(result), Nodes)
            self.assertEqual(result, [])
            self.assertFalse(result)

    def test_plugs_and_components(self):
        """アトリビュート名はPlugs、コンポーネント範囲は同じ種類の集まりへまとめ、type指定で絞り込む。"""
        plugs = mlib.ls(self.cube + ".tx")
        self.assertIs(type(plugs), Plugs)
        self.assertEqual(len(plugs), 1)
        self.assertIsInstance(plugs[0], Plug)
        vertices = mlib.ls(self.cube + ".vtx[0:2]")
        self.assertIs(type(vertices), Vertices)
        self.assertEqual([item.index for item in vertices], [0, 1, 2])
        self.assertTrue(all(isinstance(item, Vertex) for item in vertices))
        cmds.select(self.cube + ".vtx[1:2]", self.cube + ".f[0]", replace=True)
        selected = mlib.ls(selection=True, type="vertex")
        self.assertIs(type(selected), Vertices)
        self.assertEqual([item.index for item in selected], [1, 2])
        self.assertIs(type(mlib.ls(sl=True, type="face")), mlib.Faces)
        self.assertEqual(len(mlib.ls(sl=True, type="face")), 1)

    def test_result_collection_kinds(self):
        """結果の種類ごとの集まり。混在(ノードとアトリビュート、複数の種類・形状のコンポーネント)だけlist。"""
        other = cmds.polyCube(name=self.name("other"), constructionHistory=False)[0]
        curve = cmds.curve(name=self.name("crv"), degree=1, point=[(0, 0, 0), (1, 0, 0), (2, 0, 0)])
        cases = [
            ("nodes", (self.joints[0], self.cube), Nodes),
            ("plugs", (self.cube + ".tx", self.joints[0] + ".ry"), Plugs),
            ("edges", (self.cube + ".e[0:3]",), mlib.Edges),
            ("uvs", (self.cube + ".map[0:1]",), mlib.UVs),
            ("cvs", (curve + ".cv[0:2]",), mlib.CVs),
            ("node and plug", (self.cube, self.cube + ".tx"), list),
            ("vertex and face", (self.cube + ".vtx[0]", self.cube + ".f[0]"), list),
            ("two shapes", (self.cube + ".vtx[0]", other + ".vtx[0]"), list),
            ("plug and vertex", (self.cube + ".tx", self.cube + ".vtx[0]"), list),
        ]
        for name, args, expected in cases:
            with self.subTest(name=name):
                self.assertIs(type(mlib.ls(*args)), expected)

    def test_duplicates_follow_collection_rules(self):
        """集まりで返す場合は構築と同じく重複を除き、cmds.lsの結果の初出の順を保つ。"""
        names = [self.joints[1], self.joints[0], self.joints[1]]
        nodes = mlib.ls(names)
        self.assertEqual([node.getName() for node in nodes], list(dict.fromkeys(cmds.ls(names))))
        self.assertEqual(len(nodes), 2)
        plugs = mlib.ls(self.cube + ".tx", self.cube + ".translateX")
        self.assertEqual(len(plugs), 1)

    def test_nodes_operators(self):
        """Nodesの+・==・sort。+は左辺の型で構築と同じ重複除外、sortはその場で並べ替えてNone。"""
        joints = mlib.ls(self.ns + ":*", type="joint")
        cube = mlib.getNode(self.cube)
        joined = mlib.ls(self.joints[0]) + [self.cube] + joints
        self.assertIs(type(joined), Nodes)
        self.assertEqual([node.getName() for node in joined],
                         [self.joints[0], self.cube, self.joints[1], self.joints[2]])
        self.assertIs(type(joints + [self.joints[0]]), Joints)
        with self.assertRaises(TypeError):
            joints + [cube]
        with self.assertRaises(TypeError):
            joints + cube
        with self.assertRaises(TypeError):
            joints + [self.cube, cube]
        self.assertIs(type([cube] + Nodes([self.joints[0]])), Nodes)
        self.assertEqual(joints, [mlib.getNode(name) for name in self.joints])
        self.assertEqual(joints, tuple(joints))
        self.assertEqual(joints, Nodes(self.joints))
        self.assertNotEqual(joints, joints[::-1])
        self.assertNotEqual(joints, self.joints)  # 名前の文字列とは比べない
        with self.assertRaises(TypeError):
            hash(joints)
        copy = joints.copy()
        self.assertIs(joints.sort(reverse=True), joints)
        self.assertEqual([node.getName() for node in joints], self.joints[::-1])
        self.assertEqual([node.getName() for node in copy], self.joints)
        joints.sort(key=lambda node: node.getName())
        self.assertEqual([node.getName() for node in joints], self.joints)
        with self.assertRaises(TypeError):
            joints.sort(key="name")
        with self.assertRaises(TypeError):
            joints.sort(reverse=None)

    def test_plugs_collection(self):
        """Plugsはlen・添字・for・bool・+・==・sort・reprを持ち、そのままcmdsへ渡せる。"""
        names = [self.cube + ".tx", self.cube + ".ry", self.joints[0] + ".sz"]
        plugs = Plugs(names)
        self.assertEqual(len(plugs), 3)
        self.assertTrue(plugs)
        self.assertFalse(Plugs())
        self.assertEqual([plug.getFullName() for plug in plugs],
                         [mlib.getPlug(name).getFullName() for name in names])
        self.assertIs(type(plugs[1:]), Plugs)
        self.assertEqual(plugs[-1], mlib.getPlug(names[2]))
        self.assertEqual(Plugs(names + names[:1]), plugs)
        self.assertEqual(Plugs(mlib.getPlug(names[0])), [mlib.getPlug(names[0])])
        self.assertEqual(plugs + [self.cube + ".tz"], Plugs(names + [self.cube + ".tz"]))
        self.assertIs(type([self.cube + ".tz"] + plugs), Plugs)
        self.assertTrue(repr(plugs).startswith("Plugs(["))
        with self.assertRaises(TypeError):
            plugs + mlib.getPlug(names[0])
        with self.assertRaises(TypeError):
            Plugs([self.cube])
        with self.assertRaises(TypeError):
            hash(plugs)
        expected = sorted(plug.getFullName() for plug in plugs)
        self.assertIs(plugs.sort(), plugs)
        self.assertEqual([plug.getFullName() for plug in plugs], expected)
        cmds.select(plugs, replace=True)
        self.assertEqual(len(cmds.ls(selection=True)), 3)
        self.assertEqual(cmds.getAttr(Plugs([self.cube + ".t"])), [(0.0, 0.0, 0.0)])

    def test_wrapper_inputs_and_conflicts(self):
        """Node・コレクションを名前として渡せる。長短名の同時指定はTypeError。"""
        nodes = mlib.ls(mlib.getNode(self.joints[0]), [mlib.getNode(self.joints[1])])
        self.assertEqual([node.getName() for node in nodes], self.joints[:2])
        for kwargs in (dict(long=True, l=True), dict(type="joint", typ="joint"),
                       dict(selection=True, sl=True), {"assemblies": True, "as": True}):
            with self.assertRaises(TypeError, msg=repr(kwargs)):
                mlib.ls(self.ns + ":*", **kwargs)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
