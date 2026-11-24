"""ノードの表示設定がアウトライナーの表示設定を変えないことを検証する。GUIの描画確認ではない。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from mlib.decorator import undoChunk


class OutlinerVisibilityTest(unittest.TestCase):
    """複数ノードへの順次操作とUndoを検証する。"""

    def test_visibility_and_undo(self):
        nodes = [mlib.createNode("transform"), mlib.createNode("joint")]

        def visibility():
            return [node.getVisibility() for node in nodes]

        try:
            for _ in range(2):
                with undoChunk("mlibOutlinerVisibilityTest"):
                    for node in nodes:
                        node.setVisibility(False)
                self.assertEqual(visibility(), [False, False])
                self.assertFalse(cmds.getAttr(nodes[0].getName(full=True) + ".hiddenInOutliner"))
                cmds.undo()
                self.assertEqual(visibility(), [True, True])
        finally:
            cmds.delete([node.getName(full=True) for node in nodes])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
