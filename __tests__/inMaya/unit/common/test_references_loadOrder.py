"""``mlib.common.references.listReferences(sortBy="load")`` のテスト。"""

import os
import shutil
import sys
import tempfile
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common.references import listReferences


class ListReferencesLoadOrderTest(unittest.TestCase):
    """読み込んだ順の並びが cmds.file(q=True, reference=True) と同じになる。"""

    def setUp(self):
        cmds.file(new=True, force=True)
        self.tmp_dir = tempfile.mkdtemp()
        # 子のリファレンスを持つファイル(outer)と、単独のファイル(zeta・alpha)を作る。
        paths = {}
        for name in ("inner", "zeta", "alpha"):
            cmds.file(new=True, force=True)
            cmds.createNode("transform", name=name + "Node")
            paths[name] = os.path.join(self.tmp_dir, name + ".ma").replace("\\", "/")
            cmds.file(rename=paths[name])
            cmds.file(save=True, type="mayaAscii", force=True)
        cmds.file(new=True, force=True)
        cmds.file(paths["inner"], reference=True, namespace="inner")
        paths["outer"] = os.path.join(self.tmp_dir, "outer.ma").replace("\\", "/")
        cmds.file(rename=paths["outer"])
        cmds.file(save=True, type="mayaAscii", force=True)
        cmds.file(new=True, force=True)
        # 名前順とは違う順で読み込む。
        for name in ("zeta", "outer", "alpha"):
            cmds.file(paths[name], reference=True, namespace=name)

    def tearDown(self):
        cmds.file(new=True, force=True)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_load_order(self):
        """トップレベルは読み込んだ順、ネストは親の直後に並ぶ。名前順の既定は変わらない。"""
        expected_top = [cmds.referenceQuery(path, referenceNode=True) for path in cmds.file(query=True, reference=True)]
        top = listReferences(topLevelOnly=True, sortBy="load")
        self.assertEqual(top.getNames(), expected_top)
        self.assertEqual(top.getNames(), ["zetaRN", "outerRN", "alphaRN"])
        everything = listReferences(sortBy="load").getNames()
        self.assertEqual(len(everything), 4)
        self.assertIn("inner", everything[everything.index("outerRN") + 1])
        self.assertEqual(listReferences().getNames(), sorted(listReferences().getNames()))
        paths = [reference.getFilename(withCopyNumber=False) for reference in top]
        self.assertEqual(paths, cmds.file(query=True, reference=True, withoutCopyNumber=True))

    def test_invalid_order(self):
        """name・load以外はValueError。"""
        with self.assertRaises(ValueError):
            listReferences(sortBy="created")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
