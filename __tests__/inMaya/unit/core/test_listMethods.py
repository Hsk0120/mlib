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
        nodes.append(self.c.getFullName())  # 名前も、作るときと同じ決まりで解決する。
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
        self.assertEqual(nodes.index(self.c.getFullName()), 2)
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
        plugs.append(self.a.getFullName() + ".tz")
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
        mesh = mlib.createPolyCube(name=self.name("cube#"))
        other = mlib.createPolyCube(name=self.name("cube#"))
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
        self.assertEqual(cmds.polyEvaluate(mesh.getFullName(), vertex=True), 8)
        self.assertUndoEmpty()


class PluralReturnTest(NamespaceCase):
    """一覧を返す取得系は、listでなく複数形のクラスを返す。"""

    PREFIX = "mlibPluralReturn_"

    def test_getters_return_plural_classes(self):
        cmds.select(clear=True)
        root = mlib.getNode(self.make("joint", "root#"))
        child = mlib.getNode(self.make("joint", "child#", parent=root.getFullName()))
        mesh = mlib.createPolyCube(name=self.name("cube#"))
        transform = mesh.getTransform()
        skin = mlib.bindSkin([root, child], transform)
        cases = (
            (transform.getShapes(), mlib.Nodes, [mesh]),
            (root.getChildren(), mlib.Nodes, [child]),
            (child.getParents(), mlib.Nodes, [root]),
            (root.getChainFromHere(), mlib.Joints, [root, child]),
            (transform.getSkinClusters(), mlib.SkinClusters, [skin]),
            (skin.getInfluences(), mlib.Nodes, [root, child]),
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
        self.assertEqual(root.getPlug("tx").getDestinations(), [child.getPlug("tx")])
        self.assertIs(type(root.getPlug("tx").getDestinations()), mlib.Plugs)
        self.assertIs(type(root.getPlug("tx").getDestinations(asNode=True)), mlib.Nodes)
        self.assertIs(type(root.getPlug("tx").getDestinations(asPair=True)), list)
        self.assertIs(type(root.getConnections(source=False, type="joint")), mlib.Plugs)
        # 返った集まりは、そのままlistのように足せる。
        shapes = transform.getShapes()
        shapes.append(root)
        self.assertEqual(shapes, [mesh, root])
        self.assertEqual(transform.getShapes(), [mesh])


if __name__ == "__main__":
    unittest.main()
