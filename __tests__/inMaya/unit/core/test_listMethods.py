"""複数形のクラス(Nodes・Joints・Plugs・コンポーネント)で、Pythonのlistと同じ名前の操作が使えることのテスト。

追加する値の解決と型の確認、同じ要素を2つ持たないこと、シーンを変えないこと(Undoに何も残らない)を確かめる。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class ListMethodsTest(NamespaceCase):
    PREFIX = "mlibListMethods_"

    def setUp(self):
        super().setUp()
        cmds.select(clear=True)
        self.a, self.b, self.c = (mlib.getNode(self.make("transform", "node#")) for _ in range(3))
        cmds.select(clear=True)
        self.joint = mlib.getNode(self.make("joint", "joint#"))

    def test_nodes_append_extend_insert(self):
        nodes = mlib.Nodes([self.a])
        self.flushUndo()
        self.assertIsNone(nodes.append(self.b))
        nodes.append(self.b)  # すでにある要素は足さない。
        nodes.append(self.c.getName(full=True))  # 名前も、作るときと同じ決まりで解決する。
        self.assertEqual(nodes, [self.a, self.b, self.c])
        nodes.extend([self.joint, self.a])
        self.assertEqual(nodes, [self.a, self.b, self.c, self.joint])
        other = mlib.Nodes([self.a])
        other.insert(0, self.b)
        other.insert(0, self.b)
        self.assertEqual(other, [self.b, self.a])
        other += [self.c]
        self.assertEqual(other, [self.b, self.a, self.c])
        self.assertIsInstance(other, mlib.Nodes)
        self.assertUndoEmpty()

    def test_nodes_remove_pop_index_count_clear_reverse(self):
        nodes = mlib.Nodes([self.a, self.b, self.c])
        self.assertEqual(nodes.index(self.b), 1)
        self.assertEqual(nodes.index(self.c.getName(full=True)), 2)
        self.assertEqual((nodes.count(self.a), nodes.count(self.joint)), (1, 0))
        self.assertIn(self.a, nodes)
        self.assertNotIn(self.joint, nodes)
        self.assertNotIn(5, nodes)
        self.assertIsNone(nodes.remove(self.b))
        self.assertEqual(nodes, [self.a, self.c])
        with self.assertRaises(ValueError):
            nodes.remove(self.b)
        with self.assertRaises(ValueError):
            nodes.index(self.b)
        self.assertIs(nodes.pop(), self.c)
        self.assertIs(nodes.pop(0), self.a)
        with self.assertRaises(IndexError):
            nodes.pop()
        nodes.extend([self.a, self.b, self.c])
        self.assertIsNone(nodes.reverse())
        self.assertEqual(nodes, [self.c, self.b, self.a])
        nodes[0] = self.joint
        self.assertEqual(nodes, [self.joint, self.b, self.a])
        with self.assertRaises(ValueError):
            nodes[0] = self.a  # 同じ要素は2つ持てない。
        del nodes[1]
        self.assertEqual(nodes, [self.joint, self.a])
        self.assertIsNone(nodes.clear())
        self.assertEqual(len(nodes), 0)
        # 取り除いても、シーンのノードは残る。
        self.assertTrue(all(node.isValid() for node in (self.a, self.b, self.c, self.joint)))

    def test_item_type_is_checked(self):
        joints = mlib.Joints([self.joint])
        for action in (lambda: joints.append(self.a), lambda: joints.extend([self.a]), lambda: joints.insert(0, self.a)):
            with self.assertRaises(TypeError):
                action()
        self.assertEqual(joints, [self.joint])
        with self.assertRaises(RuntimeError):
            mlib.Nodes().append("noSuchNode_mlibListMethods")
        # extendは、すべての値を確かめてから足す。
        nodes = mlib.Nodes([self.a])
        with self.assertRaises(RuntimeError):
            nodes.extend([self.b, "noSuchNode_mlibListMethods"])
        self.assertEqual(nodes, [self.a])

    def test_plugs(self):
        tx, ty, tz = (self.a.getPlug(name) for name in ("tx", "ty", "tz"))
        plugs = mlib.Plugs([tx])
        plugs.append(ty)
        plugs.append(ty)
        plugs.append(self.a.getName(full=True) + ".tz")
        self.assertEqual(plugs, [tx, ty, tz])
        self.assertEqual(plugs.index(tz), 2)
        self.assertIn(ty, plugs)
        plugs.remove(ty)
        plugs.reverse()
        self.assertEqual(plugs, [tz, tx])
        self.assertEqual(plugs.pop(), tx)
        with self.assertRaises(TypeError):
            plugs.append(self.a)
        plugs.clear()
        self.assertEqual(len(plugs), 0)

    def test_components(self):
        mesh = mlib.createPoly("cube", name=self.name("cube#"))
        other = mlib.createPoly("cube", name=self.name("cube#"))
        vertices = mesh.getVertices([0, 1])
        self.flushUndo()
        self.assertIsNone(vertices.append(mesh.getVertices([3])[0]))
        vertices.append(mesh.getVertices([3])[0])
        vertices.extend(mesh.getVertices([1, 5]))
        self.assertEqual(vertices.indices, (0, 1, 3, 5))
        vertices.insert(0, mesh.getVertices([7])[0])
        self.assertEqual(vertices.indices, (7, 0, 1, 3, 5))
        self.assertEqual(vertices.index(mesh.getVertices([1])[0]), 2)
        self.assertIn(mesh.getVertices([3])[0], vertices)
        self.assertNotIn(mesh.getVertices([2])[0], vertices)
        self.assertNotIn(other.getVertices([3])[0], vertices)
        vertices.remove(mesh.getVertices([0])[0])
        self.assertEqual(vertices.pop().index, 5)
        vertices.reverse()
        self.assertEqual(vertices.indices, (3, 1, 7))
        del vertices[0]
        vertices += mesh.getVertices([2])
        self.assertEqual(vertices.indices, (1, 7, 2))
        with self.assertRaises(TypeError):
            vertices.append(other.getVertices([0])[0])
        with self.assertRaises(TypeError):
            vertices.append(mesh.getEdges([0])[0])
        with self.assertRaises(ValueError):
            vertices.remove(mesh.getVertices([0])[0])
        vertices.clear()
        self.assertEqual(len(vertices), 0)
        self.assertEqual(cmds.polyEvaluate(mesh.getName(full=True), vertex=True), 8)
        self.assertUndoEmpty()


class PluralReturnTest(NamespaceCase):
    """一覧を返す取得系は、listでなく複数形のクラスを返す。"""

    PREFIX = "mlibPluralReturn_"

    def test_getters_return_plural_classes(self):
        cmds.select(clear=True)
        root = mlib.getNode(self.make("joint", "root#"))
        child = mlib.getNode(self.make("joint", "child#", parent=root.getName(full=True)))
        mesh = mlib.createPoly("cube", name=self.name("cube#"))
        transform = mesh.getTransform()
        skin = mlib.bindSkin([root, child], transform)
        cases = (
            (transform.getShape(all=True), mlib.Nodes, [mesh]),
            # 要素がすべてジョイントなら、NodesでなくJointsで返る。
            (root.getChildren(), mlib.Joints, [child]),
            (child.getParent(instances=True), mlib.Joints, [root]),
            (root.getChainFromHere(), mlib.Joints, [root, child]),
            (transform.getSkinClusters(), mlib.SkinClusters, [skin]),
            (skin.getInfluences(), mlib.Joints, [root, child]),
            (transform.getParent(instances=True), mlib.Nodes, []),
            (root.getPlug("translate").getChildren(), mlib.Plugs, [root.getPlug(name) for name in ("tx", "ty", "tz")]),
        )
        for result, expected_type, expected in cases:
            with self.subTest(expected=expected):
                self.assertIs(type(result), expected_type)
                self.assertEqual(result, expected)
        self.assertIsInstance(root.getPlugs(), mlib.Plugs)
        self.assertIsInstance(mesh.getHistory(), mlib.Nodes)
        self.assertIsInstance(root.resetAttrs(), mlib.Plugs)
        # 接続の一覧は、PlugならPlugs、NodeならNodes、組ならlist。
        root.getPlug("tx").connectTo(child.getPlug("tx"))
        self.assertEqual(root.getPlug("tx").getConnections(outputs=True), [child.getPlug("tx")])
        self.assertIs(type(root.getPlug("tx").getConnections(outputs=True)), mlib.Plugs)
        self.assertIs(type(root.getPlug("tx").getConnections(outputs=True, asNode=True)), mlib.Joints)
        self.assertIs(type(root.getPlug("tx").getConnections(outputs=True, asPair=True)), list)
        self.assertIs(type(root.getConnections(source=False, type="joint")), mlib.Plugs)
        # mlib.lsも、typeを指定しなくても、すべてジョイントならJointsで返す。
        self.assertIs(type(mlib.ls(root.getName(full=True), child.getName(full=True))), mlib.Joints)
        self.assertIs(type(mlib.ls(root.getName(full=True), transform.getName(full=True))), mlib.Nodes)
        self.assertEqual(root.getChildren().sortedByDepth(), [child])
        # 自動でJointsになった集まりは、ジョイント以外を足すとNodesへ戻る(中身によって足せなくならない)。
        children = root.getChildren()
        self.assertIs(type(children), mlib.Joints)
        self.assertIn(transform, children + [transform])
        self.assertIs(type(children + [transform]), mlib.Nodes)
        self.assertIs(type([transform] + children), mlib.Nodes)
        self.assertIs(type(children + [root]), mlib.Joints)
        self.assertIs(type(children), mlib.Joints)
        self.assertNotIn(transform, children)
        self.assertIs(type(children), mlib.Joints)
        children.append(root)
        self.assertIs(type(children), mlib.Joints)
        children.append(transform)
        self.assertIs(type(children), mlib.Nodes)
        self.assertEqual(children, [child, root, transform])
        extended = root.getChildren()
        with self.assertRaises(RuntimeError):
            extended.extend([transform, "noSuchNode_mlibPluralReturn"])
        self.assertIs(type(extended), mlib.Joints)
        self.assertEqual(extended, [child])
        # 自分で作ったJointsは、これまでどおりジョイント以外を拒否する。
        with self.assertRaises(TypeError):
            mlib.Joints([root]).append(transform)
        with self.assertRaises(TypeError):
            mlib.Joints([root]) + [transform]
        # 返った集まりは、そのままlistのように足せる。
        shapes = transform.getShape(all=True)
        shapes.append(root)
        self.assertEqual(shapes, [mesh, root])
        self.assertEqual(transform.getShape(all=True), [mesh])


class ForwardingTest(NamespaceCase):
    """複数形から、各要素のメソッドを同じ名前で呼べる。名前の一覧は getNames、完全な名前は getNames(full=True)。"""

    PREFIX = "mlibPluralForward_"

    def test_plugs_forward_to_each_plug(self):
        a = mlib.getNode(self.make("transform", "node#"))
        plugs = mlib.Plugs([a.getPlug("tx"), a.getPlug("ty")])
        self.flushUndo()
        self.assertEqual(plugs.set(3), [None, None])
        self.assertEqual(plugs.get(), [3.0, 3.0])
        self.assertUndoesInOneStep(lambda: self.assertEqual(plugs.get(), [0.0, 0.0]), lambda: self.assertEqual(plugs.get(), [3.0, 3.0]))
        self.flushUndo()
        plugs.set(5, fast=True)
        self.assertEqual(plugs.get(), [5.0, 5.0])
        self.assertUndoEmpty()
        self.assertEqual(plugs.isLocked(), [False, False])
        self.assertEqual(mlib.Plugs().get(), [])
        with self.assertRaises(AttributeError):
            plugs.noSuchMethod()
        with self.assertRaises(AttributeError):
            plugs._private()

    def test_names(self):
        parent = mlib.getNode(self.make("transform", "parent#"))
        child = mlib.getNode(self.make("transform", "child#", parent=parent.getName(full=True)))
        nodes = mlib.Nodes([parent, child])
        self.assertEqual(nodes.getNames(), [parent.getName(), child.getName()])
        self.assertEqual(nodes.getNames(full=True), [parent.getName(full=True), child.getName(full=True)])
        plugs = mlib.Plugs([child.getPlug("tx")])
        self.assertEqual(plugs.getNames(), [child.getPlug("tx").getName()])
        self.assertEqual(plugs.getNames(full=True), [child.getPlug("tx").getName(full=True)])

    def test_renamed_scene_methods_are_forwarded(self):
        """listのメソッドと同じ名前だった操作は、別の名前にしてあるので、複数形からもシーンを操作できる。"""
        a = mlib.getNode(self.make("transform", "node#"))
        first = mlib.getNode(cmds.sets(a.getName(full=True), name=self.name("set#")))
        sets = mlib.Nodes([first])
        self.assertFalse(hasattr(mlib.ObjectSet, "clear"))
        self.assertFalse(hasattr(mlib.NurbsCurve, "reverse"))
        sets.removeMembers(all=True)
        self.assertEqual(first.getMembers(), [])
        self.assertEqual(len(sets), 1)
        # clear は、集まりの中身を空にするだけで、シーンは変えない。
        sets.clear()
        self.assertEqual(len(sets), 0)
        self.assertTrue(first.isValid())
        curve = mlib.createCurve([(0, 0, 0), (1, 0, 0), (2, 1, 0), (3, 1, 0)], name=self.name("curve#"))
        start = cmds.pointPosition(curve.getName(full=True) + ".cv[0]")
        curves = mlib.Nodes([curve])
        curves.reverseDirection()
        self.assertNotEqual(cmds.pointPosition(curve.getName(full=True) + ".cv[0]"), start)


if __name__ == "__main__":
    unittest.main()
