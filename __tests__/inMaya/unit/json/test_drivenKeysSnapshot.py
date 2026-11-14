"""``mlib.json.drivenKeysSnapshot`` のテスト。

- mlib.json の AnimationSnapshot・DrivenKeysSnapshot を確かめる。
"""

import os
import shutil
import sys
import tempfile
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.json._animCurveData import _read_curve
from mlib.json.drivenKeysSnapshot import DrivenKeysSnapshot

_CLEANUP_TYPES = ["animCurve", "animBlendNodeBase", "animLayer", "blendWeighted", "unitConversion"]


class _AnimCase(NamespaceCase):
    """カーブ・レイヤー等の後片付けと、カーブの比較を持つ基底。"""

    PREFIX = "mlibSpecJsonAnim_"

    def setUp(self):
        super().setUp()
        self.time_unit = cmds.currentUnit(query=True, time=True)
        cmds.currentUnit(time="film")
        self.before = set(cmds.ls(type=_CLEANUP_TYPES) or [])
        self.other = self.ns + "B"
        cmds.namespace(add=self.other)
        self.extra_namespaces.append(self.other)
        self.folder = tempfile.mkdtemp(prefix="mlibJsonAnim")

    def tearDown(self):
        cmds.currentUnit(time=self.time_unit)
        created = [node for node in cmds.ls(type=_CLEANUP_TYPES) or [] if node not in self.before]
        layers = [node for node in created if cmds.nodeType(node) == "animLayer"]
        for layer in layers:
            if cmds.objExists(layer):
                cmds.animLayer(layer, edit=True, lock=False)
        created = [node for node in created if cmds.objExists(node)]
        if created:
            cmds.delete(created)
        shutil.rmtree(self.folder, ignore_errors=True)
        super().tearDown()

    def other_name(self, text):
        """もう1つの名前空間の名前を返す。"""
        return self.other + ":" + text

    def curve(self, plug):
        """Plugへ直接つながるカーブ名を返す。"""
        curves = cmds.listConnections(plug, source=True, destination=False, skipConversionNodes=True, type="animCurve") or []
        return curves[0] if curves else None

    def assertCurveData(self, actual, expected):
        """カーブの辞書が同じ形か確かめる。接線は float32 で保持されるため誤差を許す。"""
        for name in ("curveType", "weighted", "preInfinity", "postInfinity"):
            self.assertEqual(actual[name], expected[name], name)
        self.assertEqual(len(actual["keys"]), len(expected["keys"]))
        for got, want in zip(actual["keys"], expected["keys"]):
            for name, value in want.items():
                if name.endswith("Weight") and want[name[:-6] + "Type"] in ("step", "stepnext"):
                    continue  # step の接線は形を持たず、Maya のウェイトの報告が一定でない。
                if isinstance(value, float):
                    self.assertAlmostEqual(got[name], value, places=4, msg=f"{name} at {want['input']}")
                else:
                    self.assertEqual(got[name], value, f"{name} at {want['input']}")

    def keyTimes(self, plug):
        """Plug のキーの時刻を返す。"""
        return cmds.keyframe(plug, query=True, timeChange=True) or []


class DrivenKeysSnapshotTest(_AnimCase):
    """ドリブンキーの保存と作り直し。"""

    def setUp(self):
        super().setUp()
        for namespace in (self.ns, self.other):
            for text in ("drvA", "drvB", "dvn"):
                cmds.createNode("transform", name=namespace + ":" + text)
        self.driverA, self.driverB, self.driven = (self.name(text) for text in ("drvA", "drvB", "dvn"))
        # 1つのドライバー(角度→距離)。
        for x, y in ((0, 0), (45, 2), (90, 10)):
            cmds.setDrivenKeyframe(self.driven + ".tx", currentDriver=self.driverA + ".rz", driverValue=x, value=y)
        curve = self.curve(self.driven + ".tx")
        cmds.keyTangent(curve, edit=True, index=(1, 1), lock=False)
        cmds.keyTangent(curve, edit=True, index=(1, 1), outAngle=10)
        cmds.setInfinity(self.driven + ".tx", postInfinite="linear")
        # 2つのドライバー(blendWeighted)。
        for x, y in ((0, 0), (90, 45)):
            cmds.setDrivenKeyframe(self.driven + ".rx", currentDriver=self.driverA + ".rz", driverValue=x, value=y)
        for x, y in ((0, 0), (10, 30)):
            cmds.setDrivenKeyframe(self.driven + ".rx", currentDriver=self.driverB + ".tx", driverValue=x, value=y)
        blend = cmds.listConnections(self.driven + ".rx", source=True, destination=False, skipConversionNodes=True)[0]
        self.assertEqual(cmds.nodeType(blend), "blendWeighted")
        cmds.setAttr(blend + ".weight[1]", 0.5)

    def sample(self, namespace):
        """ドライバーを動かしたときの駆動先の値を返す。"""
        values = []
        for a, b in ((0, 0), (30, 3), (60, 7), (120, 12)):
            cmds.setAttr(namespace + ":drvA.rz", a)
            cmds.setAttr(namespace + ":drvB.tx", b)
            values.append((cmds.getAttr(namespace + ":dvn.tx"), cmds.getAttr(namespace + ":dvn.rx")))
        return values

    def assertSampled(self, actual, expected):
        for got, want in zip(actual, expected):
            self.assertSequenceAlmostEqual(got, want, places=5)

    def test_round_trip_to_other_namespace(self):
        snap = DrivenKeysSnapshot.capture(self.driven)
        data = snap.toData()["items"]
        self.assertEqual(sorted(item["blendWeighted"] for item in data), [False, True])
        single = next(item for item in data if not item["blendWeighted"])
        self.assertEqual([key["input"] for key in single["drivers"][0]["curve"]["keys"]], [0.0, 45.0, 90.0])
        path = snap.save(os.path.join(self.folder, "dk.json"))
        report = DrivenKeysSnapshot.load(path).apply(namespaceMap={self.ns: self.other})
        self.assertEqual((report.missing, report.skipped), ([], []))
        blend = cmds.listConnections(self.other_name("dvn.rx"), source=True, destination=False, skipConversionNodes=True)[0]
        self.assertEqual(cmds.nodeType(blend), "blendWeighted")
        self.assertSampled(self.sample(self.other), self.sample(self.ns))
        self.assertCurveData(_read_curve(self.curve(self.other_name("dvn.tx")), 1.0), _read_curve(self.curve(self.driven + ".tx"), 1.0))

    def test_replaces_existing_and_unit_independent(self):
        snap = DrivenKeysSnapshot.capture(self.driven)
        expected = self.sample(self.ns)
        cmds.setDrivenKeyframe(self.other_name("dvn.tx"), currentDriver=self.other_name("drvA.rz"), driverValue=5, value=-7)
        cmds.currentUnit(angle="rad", linear="m")
        snap.apply(namespaceMap={self.ns: self.other})
        cmds.currentUnit(angle="deg", linear="cm")
        self.assertSampled(self.sample(self.other), expected)
        self.assertEqual(len(cmds.keyframe(self.curve(self.other_name("dvn.tx")), query=True, floatChange=True)), 3)

    def test_missing_driver_and_one_undo(self):
        snap = DrivenKeysSnapshot.capture(self.driven)
        cmds.delete(self.other_name("drvB"))
        self.flushUndo()
        report = snap.apply(namespaceMap={self.ns: self.other})
        self.assertEqual(report.missing, [self.other_name("drvB")])
        self.assertIsNotNone(self.curve(self.other_name("dvn.tx")))
        cmds.undo()
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertIsNone(cmds.listConnections(self.other_name("dvn.tx"), source=True, destination=False))
        self.assertIsNone(cmds.listConnections(self.other_name("dvn.rx"), source=True, destination=False))

    def test_invalid_data(self):
        good = DrivenKeysSnapshot.capture(self.driven).toData()
        for mutate in (
            lambda d: d.update(items={}),
            lambda d: d["items"][0].pop("blendWeighted"),
            lambda d: d["items"][0]["drivers"][0].update(weight="1"),
            lambda d: d["items"][0]["drivers"][0]["curve"].update(curveType="animCurveTL"),
        ):
            data = DrivenKeysSnapshot(good).toData()
            mutate(data)
            with self.assertRaises(ValueError):
                DrivenKeysSnapshot(data)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
