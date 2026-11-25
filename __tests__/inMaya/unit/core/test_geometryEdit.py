"""点の座標の読み書き(geometryEdit)の、特異なトランスフォームと周期カーブの分岐を確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.core import geometryEdit


class GeometryEditTest(NamespaceCase):
    """ヒストリの無いメッシュと円のカーブで確かめる。"""

    PREFIX = "mlibGeometryEdit_"

    def cube(self):
        """ヒストリの無いpolyCubeを作り、(transform名, Mesh)を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), constructionHistory=False)[0]
        return transform, mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def circle(self):
        """ヒストリの無い周期カーブを作り、(transform名, NurbsCurve)を返す。"""
        transform = cmds.circle(name=self.name("circle#"), constructionHistory=False)[0]
        return transform, mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def test_world_space_on_singular_transform(self):
        """スケール0のトランスフォームでは、NURBSの通常・fastとメッシュのfastがValueErrorで何も書かない。"""
        transform, mesh = self.cube()
        points = mesh.getPoints()
        cmds.setAttr(transform + ".scale", 0, 0, 0)
        with self.assertRaises(ValueError):
            mesh.setPoints(points, ws=True, fast=True)
        self.assertEqual(mesh.getPoints(), points)
        curve_transform, curve = self.circle()
        curve_points = curve.getPoints()
        cmds.setAttr(curve_transform + ".scale", 0, 0, 0)
        for fast in (False, True):
            with self.subTest(fast=fast), self.assertRaises(ValueError):
                curve.setPoints(curve_points, worldSpace=True, fast=fast)
            self.assertEqual(curve.getPoints(), curve_points)

    def test_periodic_curve_check_includes_overlapping_cvs(self):
        """周期カーブの先頭のCVへcheck=Trueで書くと、重なった末尾のCVのロックも確かめる。"""
        transform, curve = self.circle()
        name = curve.getName(full=True)
        count = cmds.getAttr(name + ".spans") + cmds.getAttr(name + ".degree")
        cmds.setAttr(f"{name}.controlPoints[{count - 3}]", lock=True)
        cv = mlib.ls(transform + ".cv[0]")[0]
        before = cv.getPosition()
        with self.assertRaises(RuntimeError):
            cv.setPosition((1.0, 2.0, 3.0), check=True)
        self.assertEqual(cv.getPosition(), before)
        cmds.setAttr(f"{name}.controlPoints[{count - 3}]", lock=False)
        cv.setPosition((1.0, 2.0, 3.0), check=True)
        self.assertEqual(tuple(cmds.pointPosition(transform + ".cv[0]", local=True)), (1.0, 2.0, 3.0))

    def test_internal_helpers_for_meshes_and_empty_input(self):
        """object_positionsはメッシュの点をwを1として変換し、空の番号の書き込みは何もしない。"""
        transform, mesh = self.cube()
        cmds.setAttr(transform + ".translate", 1, 0, 0)
        self.assertEqual(geometryEdit.object_positions(mesh, [0, 1], [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]), [(0.0, 2.0, 3.0), (3.0, 5.0, 6.0)])
        cmds.setAttr(transform + ".scale", 0, 0, 0)
        with self.assertRaises(ValueError):
            geometryEdit.object_positions(mesh, [0], [(1.0, 2.0, 3.0)])
        points = mesh.getPoints()
        geometryEdit._set_positions_fast(mesh, [], [])
        geometryEdit.set_positions(mesh, [], [], fast=True)
        self.assertEqual(mesh.getPoints(), points)


class LockedControlPointsTest(NamespaceCase):
    """controlPoints全体をロックしたNURBS曲面は、CVの位置の書き込みを書く前に止める。"""

    PREFIX = "mlibGeometryEditLocked_"

    def test_locked_control_points_are_refused(self):
        surface = cmds.nurbsPlane(name=self.name("plane"), constructionHistory=False)[0]
        shape = cmds.listRelatives(surface, shapes=True, fullPath=True)[0]
        before = cmds.pointPosition(surface + ".cv[0][0]", local=True)
        cmds.setAttr(shape + ".controlPoints", lock=True)
        with self.assertRaises(RuntimeError):
            geometryEdit.require_control_points_unlocked(mlib.getNode(shape), [0])
        with self.assertRaises(RuntimeError):
            mlib.ls(surface + ".cv[0][0]")[0].setPosition((1.0, 2.0, 3.0))
        self.assertEqual(cmds.pointPosition(surface + ".cv[0][0]", local=True), before)
        cmds.setAttr(shape + ".controlPoints", lock=False)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
