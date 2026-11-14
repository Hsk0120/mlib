"""mlib.nodes.objectSet の ObjectSet ラッパーを検証するMaya内テスト。

あわせて次も確かめる。

- セット・表示レイヤー・シェーディング所属のAPI経路を検証する。
- 約束の変更・不具合の修正(担当C)を実Mayaで検証する。
- デフォーマー・AnimCurve・ObjectSet のメソッドと作成関数を確かめる。
"""

import sys
import unittest
from unittest import mock

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Node
from mlib.nodes.objectSet import ObjectSet


class ObjectSetTest(unittest.TestCase):
    """基本的なメンバー列挙・追加・除外・所属判定を検証する。"""

    def setUp(self):
        self.created = []
        self.a = mlib.createNode(type="transform", name="mlibObjectSetA")
        self.b = mlib.createNode(type="transform", name="mlibObjectSetB")
        self.created.extend([self.a.getName(), self.b.getName()])
        set_name = cmds.sets(name="mlibObjectSetTestSet", empty=True)
        self.created.append(set_name)
        self.set = Node(set_name)

    def tearDown(self):
        for node in reversed(self.created):
            if cmds.objExists(node):
                cmds.delete(node)

    def test_node_resolves_to_object_set_wrapper(self):
        self.assertIsInstance(self.set, ObjectSet)

    def test_members_empty_by_default(self):
        self.assertEqual(self.set.getMembers(), [])

    def test_add_and_members_returns_node_wrappers(self):
        result = self.set.addMembers(self.a, self.b)
        self.assertIs(result, self.set)
        members = self.set.getMembers()
        self.assertEqual({member.getName() for member in members}, {self.a.getName(), self.b.getName()})
        self.assertTrue(all(isinstance(member, Node) for member in members))

    def test_remove_drops_a_member(self):
        self.set.addMembers(self.a, self.b)
        result = self.set.removeMembers(self.a)
        self.assertIs(result, self.set)
        self.assertEqual([member.getName() for member in self.set.getMembers()], [self.b.getName()])

    def test_is_member(self):
        self.assertFalse(self.set.isMember(self.a))
        self.set.addMembers(self.a)
        self.assertTrue(self.set.isMember(self.a))
        self.assertTrue(self.set.isMember(self.a.getFullName()))
        self.assertFalse(self.set.isMember(self.b))

    def test_add_accepts_component_strings(self):
        cube_transform = cmds.polyCube(name="mlibObjectSetCube", constructionHistory=False)[0]
        self.created.append(cube_transform)
        component = cube_transform + ".vtx[0:2]"

        self.set.addMembers(component)
        members = self.set.getMembers()
        self.assertIn(component, members)
        self.assertTrue(self.set.isMember(component))


class ConsolidatedSetsLayersTests(unittest.TestCase):
    """Maya標準の所属表現と通常Undoを確認する。"""

    def setUp(self):
        """隔離した新規シーンを用意する。"""
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)

    def tearDown(self):
        """既定レイヤーへ戻して検証シーンを破棄する。"""
        cmds.editDisplayLayerGlobals(currentDisplayLayer="defaultLayer")
        cmds.file(new=True, force=True)

    def test_object_set_members_and_component_subset(self):
        """圧縮範囲・順序・部分範囲の全件判定を標準setsと一致させる。"""
        cube = cmds.polyCube(name="setCube")[0]
        other = cmds.createNode("transform", name="setOther")
        name = cmds.sets(empty=True, name="querySet")
        cmds.sets(cube + ".vtx[0:2]", cube + ".vtx[5:6]", other, add=name)
        node = mlib.ObjectSet(name)
        expected = cmds.sets(name, query=True)
        actual = [item if isinstance(item, str) else item.getName() for item in node.getMembers()]
        self.assertEqual(actual, expected)
        for member in (cube + ".vtx[0]", cube + ".vtx[3]", cube + ".vtx[0:3]", other, cube):
            expected = bool(cmds.sets(member, isMember=name))
            with mock.patch.object(cmds, "sets", side_effect=AssertionError("cmds sets used")):
                self.assertEqual(node.isMember(member), expected)
                node.getMembers()

    def test_object_set_regular_undo(self):
        """セットの追加・除外はUndo可能にする。"""
        node = mlib.ObjectSet(cmds.sets(empty=True))
        cube = cmds.polyCube()[0]
        cmds.flushUndo()
        node.addMembers(cube + ".f[0:2]")
        self.assertTrue(node.isMember(cube + ".f[0:2]"))
        node.removeMembers(cube + ".f[1]")
        self.assertFalse(node.isMember(cube + ".f[1]"))
        node.addMembers(cube + ".f[1]")
        self.assertTrue(node.isMember(cube + ".f[1]"))
        cmds.undo()
        self.assertFalse(node.isMember(cube + ".f[1]"))


class _ContractCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibContractC_"
    ENABLE_UNDO = False


class ObjectSetIsMemberTest(_ContractCase):
    """ObjectSet.isMember が DG ノードやアトリビュートでも cmds.sets(isMember=) と一致することを確かめる。"""

    def test_matches_cmds(self):
        cube = cmds.polyCube(name=self.name("cube"))[0]
        dg_in = cmds.createNode("addDoubleLinear", name=self.name("adlIn"))
        dg_out = cmds.createNode("addDoubleLinear", name=self.name("adlOut"))
        locator = cmds.spaceLocator(name=self.name("loc"))[0]
        members = [dg_in, cube + ".vtx[0:2]", cube + ".tx", dg_out + ".input1", locator]
        object_set = cmds.sets(members, name=self.name("set"))
        wrapper = mlib.getNode(object_set)
        self.assertIsInstance(wrapper, ObjectSet)
        queries = [
            dg_in,
            dg_out,
            dg_out + ".input1",
            dg_in + ".input1",
            cube + ".vtx[0]",
            cube + ".vtx[0:3]",
            cube + ".tx",
            cube + ".ty",
            cube,
            locator,
            locator + ".tx",
            mlib.getNode(dg_in),
            mlib.getPlug(dg_out + ".input1"),
        ]
        for query in queries:
            with self.subTest(str(query)):
                self.assertEqual(wrapper.isMember(query), cmds.sets(str(query), isMember=object_set))


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibDeformAdd_"

    def cube(self, subdivisionsY=1):
        """1辺2cm の polyCube を作り、(transform 名, shape 名) を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, subdivisionsY=subdivisionsY, constructionHistory=False)[0]
        transform = cmds.ls(transform, long=True)[0]
        return transform, cmds.listRelatives(transform, shapes=True, fullPath=True)[0]

    def skinned(self):
        """2段の cube を2本の joint へバインドし、(skin, mesh 名, joints, 未登録 joint) を返す。"""
        mesh, _ = self.cube(subdivisionsY=2)
        cmds.select(clear=True)
        j0 = cmds.joint(name=self.name("j0"), position=(0, -1, 0))
        j1 = cmds.joint(name=self.name("j1"), position=(0, 1, 0))
        cmds.select(clear=True)
        stranger = cmds.joint(name=self.name("stranger"))
        cmds.select(clear=True)
        name = cmds.skinCluster(j0, j1, mesh, toSelectedBones=True, name=self.name("skin"))[0]
        cmds.select(clear=True)
        return mlib.getNode(name), mesh, (j0, j1), stranger

    def keyed(self):
        """translateX の frame 1 に 0、frame 10 に 5 のキーを打ったカーブを返す。"""
        node = self.make("transform", "keyed#")
        cmds.setKeyframe(node, attribute="translateX", time=1, value=0.0)
        cmds.setKeyframe(node, attribute="translateX", time=10, value=5.0)
        return mlib.getNode(cmds.listConnections(node + ".tx", type="animCurve")[0])


class ObjectSetDeformAdditionsTest(_Case):
    """ObjectSet の集合演算と clear。"""

    def flat(self, members):
        """getMembers 形式のリストを、フルパスの要素名の集合へ展開する。"""
        result = set()
        for member in members:
            if isinstance(member, str):
                result.update(cmds.ls(member, flatten=True, long=True))
            else:
                result.add(member.getFullName())
        return result

    def sets(self):
        """頂点の一部と transform を持つ2つのセットを返す。"""
        cube, _ = self.cube()
        a, b = self.make("transform", "a#"), self.make("transform", "b#")
        first = cmds.sets(cube + ".vtx[0:3]", a, name=self.name("first"))
        second = cmds.sets(cube + ".vtx[2:5]", b, name=self.name("second"))
        return mlib.getNode(first), mlib.getNode(second), cube, cmds.ls(a, long=True)[0], cmds.ls(b, long=True)[0]

    def test_set_operations(self):
        """和・積・差は要素単位で cmds の結果を集合演算したものと一致する。"""
        first, second, cube, a, b = self.sets()
        one = self.flat(cmds.sets(first.getFullName(), query=True))
        two = self.flat(cmds.sets(second.getFullName(), query=True))
        self.assertEqual(self.flat(first.getUnion(second)), one | two)
        self.assertEqual(self.flat(first.getIntersection(second)), one & two)
        self.assertEqual(self.flat(first.getDifference(second)), one - two)
        self.assertEqual(self.flat(first.getIntersection(second.getName())), one & two)
        self.assertFalse(first.isSubSet(second))
        sub = mlib.getNode(cmds.sets(cube + ".vtx[2]", b, name=self.name("sub")))
        self.assertTrue(sub.isSubSet(second))
        self.assertTrue(mlib.getNode(cmds.sets(empty=True, name=self.name("empty"))).isSubSet(first))

    def test_clear_and_invalid(self):
        """clear は Undo 1回で戻る。相手が objectSet でなければ TypeError、削除済みは RuntimeError。"""
        first, second, _, a, _ = self.sets()
        before = self.flat(first.getMembers())
        self.flushUndo()
        self.assertIs(first.clear(), first)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.flat(first.getMembers()), before), lambda: self.assertEqual(first.getMembers(), []))
        with self.assertRaises(TypeError):
            first.getUnion(a)
        cmds.delete(second.getFullName())
        with self.assertRaises(RuntimeError):
            first.getDifference(second)
        with self.assertRaises(RuntimeError):
            second.clear()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
