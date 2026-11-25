"""``mlib.nodes.shadingEngine`` の ShadingEngine.assign が割り当てられない対象を受けたときの動きを確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class ShadingEngineAssignErrorTest(NamespaceCase):
    """割り当てできない対象への assign。"""

    PREFIX = "mlibSpecShadingAssign_"

    def setUp(self):
        super().setUp()
        self.engine = mlib.getNode(cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=self.name("engine")))
        self.cube = cmds.polyCube(constructionHistory=False, name=self.name("cube"))[0]

    @unittest.expectedFailure
    def test_vertex_assignment_is_rejected(self):
        """頂点は割り当てられないので RuntimeError(docstringの「Mayaが割り当てを拒否した場合」)。

        findings2 nodes-geometry「3. ShadingEngine.assign が割り当てられない対象を黙って無視する」:
        Mayaは警告を出すだけで例外にならず、何も割り当てずに戻る。
        """
        with self.assertRaises(RuntimeError):
            self.engine.assign(self.cube + ".vtx[0]")
        self.assertFalse(cmds.sets(self.engine.getName(full=True), query=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
