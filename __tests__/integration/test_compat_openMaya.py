"""mlib が使う OpenMaya API 2.0 の入口が、対応する Maya の版にあることを確かめる。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2


class OpenMayaEntriesTest(unittest.TestCase):
    """関数セット・イテレーター・Plug の読み取りに使う名前がそろっている。"""

    def test_classes(self):
        for name in ("MFnSet", "MNamespace", "MFnMatrixData", "MItDag", "MFnReference"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(om2, name))
        for name in ("MFnGeometryFilter", "MAnimControl"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(oma2, name))

    def test_methods(self):
        for owner, name in ((om2.MGlobal, "getActiveSelectionList"), (om2.MFnMesh, "getPoint"),
                            (om2.MFnMesh, "getUV"), (om2.MFnNurbsCurve, "cvPosition"),
                            (om2.MPlug, "asDouble"), (om2.MPlug, "asMObject"),
                            (oma2.MAnimControl, "currentTime"), (oma2.MAnimControl, "setCurrentTime")):
            with self.subTest(owner=owner.__name__, name=name):
                self.assertTrue(hasattr(owner, name))

    def test_current_time_type(self):
        self.assertIsInstance(oma2.MAnimControl.currentTime(), om2.MTime)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
