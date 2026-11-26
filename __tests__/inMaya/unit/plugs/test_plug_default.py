"""追加アトリビュートの既定値変更とMaya標準Undoの制限を検証する。"""

import math
import tempfile
import unittest
from pathlib import Path

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class PlugDefaultTest(NamespaceCase):
    def make_plug(self, kind="double", **flags):
        node = self.make()
        cmds.addAttr(node, longName="extra", attributeType=kind, **flags)
        return mlib.getPlug(node + ".extra")

    def test_normal_native_undo_and_fast(self):
        for fast in (False, True):
            untouched = self.make_plug(defaultValue=7)
            untouched.setDefault(9, fast=fast)
            self.assertEqual(untouched.get(), 7)
            plug = self.make_plug(defaultValue=7)
            plug.set(2)
            self.flushUndo()
            self.assertIsNone(plug.setDefault(9, fast=fast))
            self.assertEqual(plug.getDefault(), 9)
            self.assertEqual(plug.get(), 2)
            if fast:
                self.assertUndoEmpty()
            else:
                cmds.undo()
                self.assertEqual(plug.getDefault(), 0)
                self.assertEqual(plug.get(), 2)
                cmds.redo()
                self.assertEqual(plug.getDefault(), 9)

    def test_supported_types_and_units(self):
        old_angle = cmds.currentUnit(query=True, angle=True)
        old_linear = cmds.currentUnit(query=True, linear=True)
        try:
            cmds.currentUnit(angle="rad", linear="m")
            for fast in (False, True):
                for kind, value in (("long", 9), ("short", 8), ("byte", 7), ("float", 2.5), ("double", 3.5), ("bool", True), ("enum", 5)):
                    flags = {"enumName": "first=0:last=5"} if kind == "enum" else {}
                    plug = self.make_plug(kind, **flags)
                    plug.setDefault(value, fast=fast)
                    self.assertEqual(plug.getDefault(), value)
                angle = self.make_plug("doubleAngle")
                angle.setDefault(90, fast=fast)
                self.assertAlmostEqual(angle.getDefault(unit="rad"), math.pi / 2)
                angle.setDefault(1, fast=fast, uiUnits=True)
                self.assertAlmostEqual(angle.getDefault(unit="rad"), 1)
                distance = self.make_plug("doubleLinear")
                distance.setDefault(2, fast=fast, uiUnits=True)
                self.assertAlmostEqual(distance.getDefault(), 200)
            # UIの角度の単位が度なら、uiUnits=Trueの数値は度として読む。
            cmds.currentUnit(angle="deg")
            for fast in (False, True):
                angle = self.make_plug("doubleAngle")
                angle.setDefault(15, fast=fast, uiUnits=True)
                self.assertAlmostEqual(angle.getDefault(), 15)
                with self.assertRaises(ValueError):
                    angle.setDefault(15, fast=fast, unit="deg", uiUnits=True)
        finally:
            cmds.currentUnit(angle=old_angle, linear=old_linear)

    def test_rejections_leave_default_unchanged(self):
        for fast in (False, True):
            plug = self.make_plug(defaultValue=7, minValue=0, maxValue=10)
            for value in (float("nan"), float("inf"), 11, -1):
                with self.assertRaises(ValueError):
                    plug.setDefault(value, fast=fast)
                self.assertEqual(plug.getDefault(), 7)
            for kind in ("time", "message"):
                unsupported = self.make_plug(kind)
                with self.assertRaises(TypeError):
                    unsupported.setDefault(1, fast=fast)
            array = self.make_plug(multi=True)
            for target in (array, array[3], mlib.getPlug(self.make() + ".tx")):
                with self.assertRaises(TypeError):
                    target.setDefault(1, fast=fast)
            plug.setLocked(True)
            with self.assertRaises(RuntimeError):
                plug.setDefault(9, fast=fast)

    def test_definition_restrictions(self):
        for fast in (False, True):
            node = self.make()
            cmds.addAttr(node, longName="compound", attributeType="double3")
            for name in ("x", "y", "z"):
                cmds.addAttr(node, longName=name, attributeType="double", parent="compound")
            for name in ("compound", "x"):
                with self.assertRaises(TypeError):
                    mlib.getPlug(node + "." + name).setDefault(1, fast=fast)
            enum = self.make_plug("enum", enumName="a=0:b=5")
            with self.assertRaises(ValueError):
                enum.setDefault(3, fast=fast)
            integer = self.make_plug("short")
            with self.assertRaises(TypeError):
                integer.setDefault(1.5, fast=fast)
            with self.assertRaises(ValueError):
                integer.setDefault(32768, fast=fast)
            cmds.lockNode(node, lock=True)
            try:
                with self.assertRaises(RuntimeError):
                    mlib.getPlug(node + ".x").setDefault(1, fast=fast)
            finally:
                cmds.lockNode(node, lock=False)

    def test_file_roundtrip_and_reference_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            for fast in (False, True):
                for extension, file_type in (("ma", "mayaAscii"), ("mb", "mayaBinary")):
                    plug = self.make_plug(defaultValue=7)
                    plug.set(2)
                    plug.setDefault(9, fast=fast)
                    node = plug.getName(full=True).rsplit(".", 1)[0]
                    cmds.select(node, replace=True)
                    path = str(Path(directory) / ("default." + extension))
                    cmds.file(path, force=True, exportSelected=True, type=file_type)
                    namespace = self.ns + "Imported"
                    self.extra_namespaces.append(namespace)
                    imported = cmds.file(path, i=True, namespace=namespace, returnNewNodes=True)
                    target = next(name for name in imported if cmds.attributeQuery("extra", node=name, exists=True))
                    restored = mlib.getPlug(target + ".extra")
                    self.assertEqual(restored.getDefault(), 9)
                    self.assertEqual(restored.get(), 2)
                    reference_namespace = self.ns + "Reference"
                    cmds.file(path, reference=True, namespace=reference_namespace)
                    reference = cmds.file(path, query=True, referenceNode=True)
                    try:
                        nodes = cmds.referenceQuery(reference, nodes=True)
                        target = next(name for name in nodes if cmds.attributeQuery("extra", node=name, exists=True))
                        with self.assertRaises(RuntimeError):
                            mlib.getPlug(target + ".extra").setDefault(3, fast=fast)
                    finally:
                        cmds.file(removeReference=True, referenceNode=reference)

    def test_connected_value_is_preserved(self):
        for fast in (False, True):
            source = self.make_plug()
            target = self.make_plug(defaultValue=7)
            source.set(4)
            target.connect(source)
            target.setDefault(9, fast=fast)
            self.assertEqual(target.get(), 4)
            self.assertEqual(target.getConnections(input=True), source)
            self.assertEqual(target.getDefault(), 9)

    def test_fast_preserves_undo_queue_and_plural_dispatch(self):
        first = self.make_plug(defaultValue=7)
        second = self.make_plug(defaultValue=7)
        self.flushUndo()
        first.set(4)
        undo_name = cmds.undoInfo(query=True, undoName=True)
        mlib.ls(first.getName(full=True), second.getName(full=True)).setDefault(9, fast=True)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
        cmds.undo()
        self.assertEqual(first.get(), 7)
        self.assertEqual(first.getDefault(), 9)
        self.assertEqual(second.getDefault(), 9)
        cmds.undoInfo(stateWithoutFlush=False)
        try:
            first.setDefault(8, fast=True)
            self.assertFalse(cmds.undoInfo(query=True, state=True))
        finally:
            cmds.undoInfo(stateWithoutFlush=True)


if __name__ == "__main__":
    unittest.main()
