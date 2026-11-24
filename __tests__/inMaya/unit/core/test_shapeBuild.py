"""作りかけのノードを消す後始末(shapeBuild.removing_created_nodes)を確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.core import shapeBuild


class RemovingCreatedNodesTest(NamespaceCase):
    """中で作られたDG・DAGのノードが、例外のときだけ消えることを確かめる。"""

    PREFIX = "mlibShapeBuild_"

    def test_exception_removes_remaining_nodes(self):
        """例外のときは残ったDGノードとDAGノードを消し、中で消えたノードは飛ばして例外を出し直す。"""
        kept = self.make("network", "before")
        names = {}
        with self.assertRaises(KeyError), shapeBuild.removing_created_nodes():
            names["dg"] = cmds.createNode("network", name=self.name("dg"), skipSelect=True)
            names["dag"] = cmds.createNode("transform", name=self.name("dag"), skipSelect=True)
            gone = cmds.createNode("transform", name=self.name("gone"), skipSelect=True)
            cmds.delete(gone)
            raise KeyError("stop")
        self.assertFalse(cmds.objExists(names["dg"]))
        self.assertFalse(cmds.objExists(names["dag"]))
        self.assertTrue(cmds.objExists(kept))

    def test_success_keeps_nodes(self):
        """例外が無ければ、作ったノードを残す。"""
        with shapeBuild.removing_created_nodes():
            name = cmds.createNode("network", name=self.name("kept"), skipSelect=True)
        self.assertTrue(cmds.objExists(name))

    def test_require_shape_type_accepts_shapes(self):
        """シェイプの名前そのものも、求める型の形状として受け付ける。"""
        transform = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        shapeBuild.require_shape_type([shape, transform], "deformableShape", "ターゲット")
        with self.assertRaisesRegex(ValueError, "nurbsCurveの形状がありません"):
            shapeBuild.require_shape_type([shape], "nurbsCurve", "カーブ")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
