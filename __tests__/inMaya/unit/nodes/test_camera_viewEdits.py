"""カメラの画角とフィルム開口の編集を検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CameraEditTest(NamespaceCase):
    def camera(self):
        return mlib.getNode(cmds.camera(name=self.name("camera"))[1])

    def parented_camera(self):
        """移動・回転した親の下に、回転したカメラを作り、(カメラのシェイプ, Transform の名前) を返す。"""
        camera = self.camera()
        group = cmds.group(empty=True, name=self.name("parent"))
        cmds.setAttr(group + ".translate", 2, 3, 4)
        cmds.setAttr(group + ".rotate", 12, 23, 34)
        transform = cmds.parent(camera.getParent().getName(full=True), group)[0]
        cmds.setAttr(transform + ".rotate", -20, 35, 10)
        return camera, cmds.ls(transform, long=True)[0]

    def test_world_view(self):
        for linear in ("cm", "m"):
            cmds.currentUnit(linear=linear)
            camera = self.camera()
            group = cmds.group(empty=True, name=self.name("parent"))
            cmds.setAttr(group + ".translate", 2, 3, 4)
            cmds.setAttr(group + ".rotate", 12, 23, 34)
            cmds.parent(camera.getParent().getName(full=True), group)
            camera.setDirection((1, 0, 0), kind="up")
            self.assertAlmostEqual(camera.getDirection(kind="up") * camera.getDirection(), 0, places=5)
        cmds.currentUnit(linear="cm")

    def test_set_direction_kind(self):
        """setDirection は kind を省略できず、変えられるのは "up" だけ(Undo 1回で戻る)。"""
        camera = self.camera()
        before = camera.getDirection(kind="up")
        view = camera.getDirection()
        with self.assertRaises(TypeError):
            camera.setDirection((1, 0, 0))
        with self.assertRaises(TypeError):
            camera.setDirection((1, 0, 0), "up")
        with self.assertRaises(NotImplementedError):
            camera.setDirection((1, 0, 0), kind="view")
        with self.assertRaises(ValueError):
            camera.setDirection((1, 0, 0), kind="eye")
        with self.assertRaises(TypeError):
            camera.setDirection((1, 0, 0), kind=None)
        with self.assertRaises(ValueError):
            camera.setDirection(tuple(view), kind="up")
        self.assertSequenceAlmostEqual(camera.getDirection(kind="up"), before)
        cmds.flushUndo()
        self.assertIsNone(camera.setDirection((1, 0, 0), kind="up"))
        self.assertSequenceAlmostEqual(camera.getDirection(kind="up"), (1, 0, 0), places=6)
        self.assertSequenceAlmostEqual(camera.getDirection(), view, places=6)
        cmds.undo()
        self.assertSequenceAlmostEqual(camera.getDirection(kind="up"), before, places=6)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_set_point_eye_fast(self):
        """setPoint(point, fast=True)(kind="eye")はカメラの位置を変え、Undo に載らない。fast=False は NotImplementedError。"""
        camera, transform = self.parented_camera()
        cmds.flushUndo()
        self.assertIsNone(camera.setPoint((5, 6, 7), fast=True))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertSequenceAlmostEqual(camera.getPoint(), (5, 6, 7), places=6)
        self.assertSequenceAlmostEqual(cmds.xform(transform, query=True, translation=True, worldSpace=True), (5, 6, 7), places=6)
        # kind="eye" を明示しても同じ。ワールド空間の短縮名 ws も受ける。
        camera.setPoint((-1, 0, 2), ws=True, kind="eye", fast=True)
        self.assertSequenceAlmostEqual(camera.getPoint(), (-1, 0, 2), places=6)
        # カメラ空間(worldSpace=False)の原点は今の位置なので、位置は変わらない。
        camera.setPoint((0, 0, 0), worldSpace=False, fast=True)
        self.assertSequenceAlmostEqual(camera.getPoint(), (-1, 0, 2), places=6)
        # fast=False(既定)は NotImplementedError で、位置は変わらない。
        for kwargs in ({}, {"fast": False}, {"kind": "eye"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(NotImplementedError):
                    camera.setPoint((9, 9, 9), **kwargs)
                self.assertSequenceAlmostEqual(camera.getPoint(), (-1, 0, 2), places=6)
        for args, kwargs, error in (
            (((0, 0),), {"fast": True}, ValueError),
            (((0, 0, float("nan")),), {"fast": True}, ValueError),
            (((0, 0, 0),), {"fast": True, "kind": "view"}, ValueError),
            (((0, 0, 0),), {"fast": True, "kind": 1}, TypeError),
            (((0, 0, 0),), {"fast": True, "worldSpace": True, "ws": True}, TypeError),
        ):
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    camera.setPoint(*args, **kwargs)
                self.assertSequenceAlmostEqual(camera.getPoint(), (-1, 0, 2), places=6)

    def test_set_point_eye_keeps_center_of_interest(self):
        """setPoint(point, fast=True)(kind="eye")は、注視点を保ったまま視点を動かす(カメラは注視点を向き続ける)。"""
        camera, _transform = self.parented_camera()
        target = camera.getPoint(kind="centerOfInterest")
        camera.setPoint((5, 6, 7), fast=True)
        self.assertSequenceAlmostEqual(camera.getPoint(), (5, 6, 7), places=6)
        self.assertSequenceAlmostEqual(camera.getPoint(kind="centerOfInterest"), target, places=5)
        expected = (om2.MVector(*target) - om2.MVector(5, 6, 7)).normal()
        self.assertSequenceAlmostEqual(camera.getDirection(), tuple(expected), places=5)

    def test_set_point_center_of_interest_fast(self):
        """setPoint(kind="centerOfInterest", fast=True) は視点を保って向きと注視点を変え、fast=False は NotImplementedError。"""
        camera = self.camera()
        cmds.setAttr(camera.getParent().getName(full=True) + ".translate", 1, 2, 3)
        eye = camera.getPoint()
        with self.assertRaises(NotImplementedError):
            camera.setPoint((1, 2, -7), kind="centerOfInterest")
        with self.assertRaises(ValueError):
            camera.setPoint(tuple(eye), kind="centerOfInterest", fast=True)
        cmds.flushUndo()
        self.assertIsNone(camera.setPoint((11, 2, 3), kind="centerOfInterest", fast=True))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertSequenceAlmostEqual(camera.getPoint(), eye, places=6)
        self.assertSequenceAlmostEqual(camera.getPoint(kind="centerOfInterest"), (11, 2, 3), places=5)
        self.assertSequenceAlmostEqual(camera.getDirection(), (1, 0, 0), places=6)

    def test_field_of_view_undo(self):
        camera = self.camera()
        for vertical in (False, True):
            before = camera.getFieldOfView()
            cmds.flushUndo()
            camera.setFieldOfView(40, vertical=vertical)
            after = camera.getFieldOfView()
            self.assertAlmostEqual(after[int(vertical)], 40)
            cmds.undo()
            for a, b in zip(camera.getFieldOfView(), before):
                self.assertAlmostEqual(a, b)
            cmds.redo()
            for a, b in zip(camera.getFieldOfView(), after):
                self.assertAlmostEqual(a, b)
        camera.setFieldOfView(1, unit="rad")
        self.assertAlmostEqual(camera.getFieldOfView(unit="rad")[0], 1)

    def test_aspect_ratio_undo(self):
        camera = self.camera()
        before = camera.getAspectRatio()
        cmds.flushUndo()
        camera.setAspectRatio(2)
        self.assertAlmostEqual(camera.getAspectRatio(), 2)
        cmds.undo()
        self.assertAlmostEqual(camera.getAspectRatio(), before)
        cmds.redo()
        self.assertAlmostEqual(camera.getAspectRatio(), 2)

    def test_focus_distance_undo(self):
        camera = self.camera()
        for name, index, value in [("near", 0, 3), ("far", 1, 9)]:
            before = camera.getDepthOfFieldRange()
            cmds.flushUndo()
            self.assertIsNone(camera.setFocusDistance(**{name: value}))
            after = camera.getDepthOfFieldRange()
            self.assertAlmostEqual(after[index], value)
            cmds.undo()
            for a, b in zip(camera.getDepthOfFieldRange(), before):
                self.assertAlmostEqual(a, b)
            cmds.redo()
            for a, b in zip(camera.getDepthOfFieldRange(), after):
                self.assertAlmostEqual(a, b)
        # near と far は、どちらか1つを指定する。位置引数では渡せない。
        before = camera.getDepthOfFieldRange()
        for label, args, kwargs, error in (
            ("neither", (), {}, TypeError),
            ("both", (), {"near": 3, "far": 9}, TypeError),
            ("positional", (3,), {}, TypeError),
            ("near type", (), {"near": "a"}, TypeError),
            ("near zero", (), {"near": 0}, ValueError),
            ("far negative", (), {"far": -1}, ValueError),
            ("far nan", (), {"far": float("nan")}, ValueError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    camera.setFocusDistance(*args, **kwargs)
                for a, b in zip(camera.getDepthOfFieldRange(), before):
                    self.assertAlmostEqual(a, b)
        for name in ("near", "far"):
            with self.subTest(message=name):
                with self.assertRaisesRegex(ValueError, name + "は正の距離で指定してください"):
                    camera.setFocusDistance(**{name: -1})


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
