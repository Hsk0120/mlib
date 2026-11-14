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
        cmds.delete(node.getFullName())
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(RuntimeError):
                    call(node)


class MeshColorSetTest(_Case):
    """Mesh の UV シェルとカラーセット。"""

    def test_uv_shells(self):
        """UV シェルは getUvShellsIds の分類と一致し、UV を切ると分かれる。存在しない UV セットは ValueError。"""
        shape = self.mesh()
        self.assertEqual(shape.getUVShells(), [list(range(shape.getNumUVs()))])
        name = shape.getFullName()
        cmds.polyMapCut(name + ".e[*]", constructionHistory=False)
        shells = shape.getUVShells(uvSet="map1")
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
                    shape.getUVShells(value)

    def test_color_sets_match_poly_color_set(self):
        """作成・現在・複製・名前変更・削除が polyColorSet の照会と一致し、それぞれ Undo 1回で戻る。"""
        shape = self.mesh()
        name = shape.getFullName()

        def names():
            return cmds.polyColorSet(name, query=True, allColorSets=True) or []

        def current():
            found = cmds.polyColorSet(name, query=True, currentColorSet=True)
            return found[0] if found else None

        self.assertEqual(shape.getColorSetNames(), [])
        self.assertIsNone(shape.getCurrentColorSet())
        self.flushUndo()
        self.assertIs(shape.createColorSet("a"), shape)
        self.assertUndoesInOneStep(lambda: self.assertEqual(names(), []), lambda: self.assertEqual(names(), ["a"]))
        shape.createColorSet("a")
        shape.createColorSet("b")
        self.assertEqual(shape.getColorSetNames(), names())
        self.assertEqual(shape.getCurrentColorSet(), current())
        self.assertEqual(current(), "b")
        self.flushUndo()
        shape.setCurrentColorSet("a")
        self.assertUndoesInOneStep(lambda: self.assertEqual(current(), "b"), lambda: self.assertEqual(current(), "a"))
        self.flushUndo()
        shape.copyColorSet("a", "c")
        self.assertUndoesInOneStep(lambda: self.assertEqual(names(), ["a", "b"]), lambda: self.assertEqual(names(), ["a", "b", "c"]))
        self.flushUndo()
        shape.renameColorSet("b", "d")
        self.assertUndoesInOneStep(lambda: self.assertEqual(names(), ["a", "b"]), lambda: self.assertEqual(names(), ["a", "d"]))
        self.flushUndo()
        shape.deleteColorSet("b")
        self.assertUndoesInOneStep(lambda: self.assertEqual(names(), ["a", "b"]), lambda: self.assertEqual(names(), ["a"]))
        self.assertEqual(shape.getColorSetNames(), ["a", "b"])

    def test_color_set_errors(self):
        """名前の型・空・有無の誤りは TypeError/ValueError で、シーンを変えない。削除済みは RuntimeError。"""
        shape = self.mesh()
        shape.createColorSet("a")
        cases = (
            (shape.createColorSet, ("a",), ValueError),
            (shape.createColorSet, ("",), ValueError),
            (shape.createColorSet, (None,), TypeError),
            (shape.setCurrentColorSet, ("x",), ValueError),
            (shape.deleteColorSet, ("x",), ValueError),
            (shape.renameColorSet, ("x", "y"), ValueError),
            (shape.renameColorSet, ("a", "a"), ValueError),
            (shape.copyColorSet, ("a", 1), TypeError),
            (shape.copyColorSet, ("x", "y"), ValueError),
        )
        for method, args, error in cases:
            with self.subTest(method=method.__name__, args=args):
                with self.assertRaises(error):
                    method(*args)
                self.assertEqual(shape.getColorSetNames(), ["a"])
        self.assertDeletedRaises(shape, (lambda node: node.getColorSetNames(), lambda node: node.getUVShells(), lambda node: node.createColorSet("z")))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
