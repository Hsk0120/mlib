"""``mlib.nodes.mesh`` のテスト。

- 形状のシェイプのメソッドと createNurbsPlane を確かめる。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibShapeAdd_"

    def surface(self, scale=(1, 1, 1)):
        """幅4・長さ2(lengthRatio 0.5)の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=0.5, patchesU=2, patchesV=1, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        cmds.setAttr(transform + ".scale", *scale)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def curve(self, points, degree=3):
        """点列から NURBS カーブを作り、シェイプのラッパーを返す。"""
        transform = cmds.curve(name=self.name("curve#"), point=points, degree=degree)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def mesh(self):
        """polyPlane(2x2 分割)を作り、シェイプのラッパーを返す。"""
        transform = cmds.polyPlane(name=self.name("mesh#"), subdivisionsX=2, subdivisionsY=2, constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def assertDeletedRaises(self, node, calls):
        """ノードを削除し、各呼出しが RuntimeError になることを確かめる。"""
        cmds.delete(node.getName(full=True))
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(RuntimeError):
                    call(node)


class MeshColorSetTest(_Case):
    """Mesh の UV シェルとカラーセット。"""

    def test_uv_shells(self):
        """UV シェルは getUvShellsIds の分類と一致し、UV を切ると分かれる。存在しない UV セットは ValueError。"""
        shape = self.mesh()
        self.assertEqual(shape.getShells(uv=True), [list(range(shape.getNumUVs()))])
        name = shape.getName(full=True)
        cmds.polyMapCut(name + ".e[*]", constructionHistory=False)
        shells = shape.getShells(uv=True, uvSet="map1")
        self.assertEqual(len(shells), 4)
        count, ids = om2.MFnMesh(shape.mpath()).getUvShellsIds("map1")
        self.assertEqual(
            sorted(sorted(shell) for shell in shells), sorted(sorted(i for i, value in enumerate(ids) if value == shell_id) for shell_id in range(count))
        )
        self.assertEqual(sorted(index for shell in shells for index in shell), list(range(shape.getNumUVs())))
        self.assertEqual([shell[0] for shell in shells], sorted(shell[0] for shell in shells))
        for shell in shells:
            self.assertEqual(shell, sorted(shell))
        for value, error in (("missing", ValueError), ("", ValueError), (1, TypeError)):
            with self.subTest(uvSet=value):
                with self.assertRaises(error):
                    shape.getShells(uv=True, uvSet=value)
        # uvSetはUVシェル(uv=True)のときだけ指定できる。uvはboolだけを受け付ける。
        for flags in ({"uvSet": "map1"}, {"uv": False, "uvSet": "map1"}, {"uv": 1}):
            with self.subTest(flags=flags):
                with self.assertRaises(TypeError):
                    shape.getShells(**flags)

    def test_color_sets_match_poly_color_set(self):
        """作成・現在・複製・名前変更・削除が polyColorSet の照会と一致し、それぞれ Undo 1回で戻る。"""
        shape = self.mesh()
        name = shape.getName(full=True)

        def names():
            return cmds.polyColorSet(name, query=True, allColorSets=True) or []

        def current():
            found = cmds.polyColorSet(name, query=True, currentColorSet=True)
            return found[0] if found else None

        self.assertEqual(shape.getSetNames(color=True), [])
        self.assertIsNone(shape.getCurrentSet(color=True))
        self.flushUndo()
        self.assertIsNone(shape.createSet("a", color=True))
        self.assertUndoesInOneStep(lambda: self.assertEqual(names(), []), lambda: self.assertEqual(names(), ["a"]))
        shape.createSet("a", color=True)
        shape.createSet("b", color=True)
        self.assertEqual(shape.getSetNames(color=True), names())
        self.assertEqual(shape.getCurrentSet(color=True), current())
        self.assertEqual(current(), "b")
        self.flushUndo()
        shape.setCurrentSet("a", color=True)
        self.assertUndoesInOneStep(lambda: self.assertEqual(current(), "b"), lambda: self.assertEqual(current(), "a"))
        self.flushUndo()
        shape.copySet("a", "c", color=True)
        self.assertUndoesInOneStep(lambda: self.assertEqual(names(), ["a", "b"]), lambda: self.assertEqual(names(), ["a", "b", "c"]))
        self.flushUndo()
        shape.renameSet("b", "d", color=True)
        self.assertUndoesInOneStep(lambda: self.assertEqual(names(), ["a", "b"]), lambda: self.assertEqual(names(), ["a", "d"]))
        self.flushUndo()
        shape.deleteSet("b", color=True)
        self.assertUndoesInOneStep(lambda: self.assertEqual(names(), ["a", "b"]), lambda: self.assertEqual(names(), ["a"]))
        self.assertEqual(shape.getSetNames(color=True), ["a", "b"])

    def test_color_set_errors(self):
        """名前の型・空・有無の誤りは TypeError/ValueError で、シーンを変えない。削除済みは RuntimeError。"""
        shape = self.mesh()
        shape.createSet("a", color=True)
        cases = (
            (shape.createSet, ("a",), ValueError),
            (shape.createSet, ("",), ValueError),
            (shape.createSet, (None,), TypeError),
            (shape.setCurrentSet, ("x",), ValueError),
            (shape.deleteSet, ("x",), ValueError),
            (shape.renameSet, ("x", "y"), ValueError),
            (shape.renameSet, ("a", "a"), ValueError),
            (shape.copySet, ("a", 1), TypeError),
            (shape.copySet, ("x", "y"), ValueError),
        )
        for method, args, error in cases:
            with self.subTest(method=method.__name__, args=args):
                with self.assertRaises(error):
                    method(*args, color=True)
                self.assertEqual(shape.getSetNames(color=True), ["a"])
        # colorはboolだけを受け付ける。replaceはUVセットの複製だけで使える。
        calls = (
            ("getSetNames", ()),
            ("getCurrentSet", ()),
            ("setCurrentSet", ("a",)),
            ("createSet", ("b",)),
            ("copySet", ("a", "b")),
            ("renameSet", ("a", "b")),
            ("deleteSet", ("a",)),
        )
        for name, args in calls:
            with self.subTest(method=name, color=1):
                with self.assertRaises(TypeError):
                    getattr(shape, name)(*args, color=1)
                self.assertEqual(shape.getSetNames(color=True), ["a"])
        with self.subTest(method="copySet", color=True, replace=True):
            with self.assertRaises(TypeError):
                shape.copySet("a", "b", color=True, replace=True)
            self.assertEqual(shape.getSetNames(color=True), ["a"])
        # 同じ名前でも、UVセットとカラーセットは別々に調べる。
        self.assertNotIn("a", shape.getSetNames())
        with self.assertRaises(ValueError):
            shape.setCurrentSet("a")
        self.assertDeletedRaises(
            shape, (lambda node: node.getSetNames(color=True), lambda node: node.getShells(uv=True), lambda node: node.createSet("z", color=True))
        )

    def test_uv_shells_are_ordered_by_smallest_uv(self):
        """UVシェルは、それぞれのいちばん小さいUV番号の順に並ぶ(UV番号が飛び飛びのシェルでも)。"""
        transform = cmds.createNode("transform", name=self.name("uvOrder#"))
        selection = om2.MSelectionList()
        selection.add(transform)
        points = [om2.MPoint(x, 0, z) for x, z in ((0, 0), (1, 0), (1, 1), (0, 1), (3, 0), (4, 0), (4, 1), (3, 1))]
        fn = om2.MFnMesh()
        fn.create(points, [4, 4], list(range(8)), parent=selection.getDependNode(0))
        # 1つ目の面はUV 0・5・6・7、2つ目の面はUV 1〜4 を使う。UVの位置は面ごとに離す。
        fn.setUVs([0.0, 0.5, 0.6, 0.6, 0.5, 0.1, 0.1, 0.0], [0.0, 0.0, 0.0, 0.1, 0.1, 0.0, 0.1, 0.1])
        fn.assignUVs([4, 4], [0, 5, 6, 7, 1, 2, 3, 4])
        shape = mlib.getNode(om2.MDagPath.getAPathTo(fn.object()).fullPathName())
        mesh_fn = om2.MFnMesh(shape.mpath())
        count, ids = mesh_fn.getUvShellsIds(mesh_fn.currentUVSetName())
        self.assertEqual(count, 2)
        self.assertEqual(shape.getShells(uv=True), [[0, 5, 6, 7], [1, 2, 3, 4]])
        self.assertEqual(
            sorted(map(tuple, shape.getShells(uv=True))), sorted(tuple(i for i, value in enumerate(ids) if value == shell) for shell in range(count))
        )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
