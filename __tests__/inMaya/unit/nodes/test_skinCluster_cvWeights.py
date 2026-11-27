"""NURBSの独立CVとスキンウェイトの行・論理番号の対応を検証する。"""

import copy
import tempfile
import unittest
from pathlib import Path

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib
from mlib.components.cv import CV
from mlib.components.surfaceCV import SurfaceCV


class SkinClusterCvWeightsTest(NamespaceCase):
    """開いたNURBSと周期NURBSで通常更新・fast・保存復元を確認する。"""

    PREFIX = "mlibCvSkin_"

    def makeSkin(self, kind):
        """対象形状と2本の独立したインフルエンスを作る。"""
        if kind == "curve":
            shape = cmds.curve(name=self.name("curve#"), degree=3, point=[(0, 0, 0), (1, 1, 0), (2, -1, 0), (3, 0, 0)])
        elif kind == "periodicCurve":
            shape = cmds.circle(name=self.name("circle#"), constructionHistory=False, sections=8)[0]
        elif kind == "surface":
            shape = cmds.nurbsPlane(name=self.name("plane#"), constructionHistory=False, patchesU=2, patchesV=1)[0]
        else:
            shape = cmds.sphere(name=self.name("sphere#"), constructionHistory=False, sections=4, spans=2)[0]
        joints = [self.make("joint", "joint#") for _ in range(2)]
        cmds.setAttr(joints[1] + ".tx", 3)
        name = cmds.skinCluster(joints, shape, toSelectedBones=True, normalizeWeights=0, name=self.name("skin#"))[0]
        return mlib.getNode(name), mlib.getNode(shape).getShape(), joints

    def pointIndices(self, shape):
        """Mayaのジオメトリ反復から、実際にウェイトを持つ点番号を得る。"""
        iterator = om2.MItGeometry(shape.mpath())
        result = []
        while not iterator.isDone():
            result.append(iterator.index())
            iterator.next()
        return result

    def assertRowsEqual(self, actual, expected):
        """行の数と各要素の値を比較する。"""
        self.assertEqual(len(actual), len(expected))
        for row, wanted in zip(actual, expected):
            self.assertSequenceAlmostEqual(row, wanted)

    def test_open_and_periodic_rows_match_maya_point_indices(self):
        for kind in ("curve", "surface", "periodicCurve", "periodicSurface"):
            with self.subTest(kind=kind):
                skin, shape, joints = self.makeSkin(kind)
                indices = self.pointIndices(shape)
                rows = [[(index + 1) / 100.0, (index + 2) / 100.0] for index in indices]
                self.assertIsNone(skin.setWeights(joints, rows, rows=True))
                self.assertRowsEqual(skin.getWeights(joints, rows=True), rows)
                for index, row in zip(indices, rows):
                    self.assertSequenceAlmostEqual(cmds.getAttr(f"{skin}.weightList[{index}].weights[*]"), row)
                selected = [indices[-1], indices[0]]
                skin.setWeights(joints, [[0.2, 0.8], [0.7, 0.3]], vertices=selected, rows=True, fast=True)
                self.assertRowsEqual(skin.getWeights(joints, vertices=selected, rows=True), [[0.2, 0.8], [0.7, 0.3]])

    def test_components_names_and_periodic_aliases(self):
        for kind in ("periodicCurve", "periodicSurface"):
            with self.subTest(kind=kind):
                skin, shape, joints = self.makeSkin(kind)
                if kind == "periodicCurve":
                    fn = om2.MFnNurbsCurve(shape.mpath())
                    duplicate = fn.numCVs - fn.degree
                    component = CV(shape, duplicate)
                    name = shape.getName(full=True) + ".cv[0]"
                else:
                    fn = om2.MFnNurbsSurface(shape.mpath())
                    duplicate = fn.numCVsInV - fn.degreeInV
                    component = SurfaceCV(shape, duplicate)
                    name = shape.getName(full=True) + ".cv[0][0]"
                skin.setWeights({joints[0]: 0.4, joints[1]: 0.6}, vertex=component, normalize=True)
                self.assertSequenceAlmostEqual(skin.getWeights(joints, vertices=name), [0.4, 0.6])
                self.assertSequenceAlmostEqual(skin.getWeights(vertex=component).values(), [0.4, 0.6])
                before = list(skin.getWeights(joints))
                with self.assertRaises(ValueError):
                    skin.setWeights(joints, [0.5, 0.5], vertices=[0, duplicate], broadcast=True)
                self.assertEqual(list(skin.getWeights(joints)), before)

    def test_undo_and_fast_preserve_undo_queue(self):
        for kind in ("curve", "periodicSurface"):
            with self.subTest(kind=kind):
                skin, _, joints = self.makeSkin(kind)
                before = list(skin.getWeights(joints))
                skin.setWeights(joints, [0.1, 0.9], broadcast=True)
                cmds.undo()
                self.assertSequenceAlmostEqual(skin.getWeights(joints), before)
                undo_name = cmds.undoInfo(query=True, undoName=True)
                skin.setWeights(joints, [0.3, 0.7], broadcast=True, fast=True, check=True)
                self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
                self.assertTrue(cmds.undoInfo(query=True, state=True))
                self.assertSequenceAlmostEqual(skin.getWeights(joints, vertices=0), [0.3, 0.7])

    def test_blend_weights_order_and_undo(self):
        skin, shape, _ = self.makeSkin("periodicSurface")
        indices = self.pointIndices(shape)
        selected = [indices[-1], indices[0]]
        before = skin.getBlendWeights(vertices=selected)
        skin.setBlendWeights([0.8, 0.2], vertices=selected)
        self.assertSequenceAlmostEqual(skin.getBlendWeights(vertices=selected), [0.8, 0.2])
        cmds.undo()
        self.assertSequenceAlmostEqual(skin.getBlendWeights(vertices=selected), before)
        skin.setBlendWeights([0.6, 0.1], vertices=selected, fast=True)
        self.assertSequenceAlmostEqual(skin.getBlendWeights(vertices=selected), [0.6, 0.1])
        values = [order / len(indices) for order in range(len(indices))]
        skin.setBlendWeights(values, fast=True)
        self.assertSequenceAlmostEqual(skin.getBlendWeights(), values)

    def test_normalization_and_pruning_preserve_sparse_cv_rows(self):
        skin, shape, joints = self.makeSkin("periodicSurface")
        third = self.make("joint", "third")
        skin.addInfluences([third])
        joints.append(third)
        indices = self.pointIndices(shape)
        skin.setWeights(joints, [0.2, 0.3, 0.5], broadcast=True)
        cmds.setAttr(joints[1] + ".liw", True)
        for fast in (False, True):
            skin.setWeights(joints[0], [0.4], vertices=indices[-1], normalize=True, fast=fast)
            self.assertSequenceAlmostEqual(skin.getWeights(joints, vertices=indices[-1]), [0.4, 0.3, 0.3])
            self.assertSequenceAlmostEqual(skin.getWeights(joints, vertices=indices[0]), [0.2, 0.3, 0.5])
        cmds.setAttr(joints[1] + ".liw", False)
        skin.setWeights(joints, [0.01, 0.4, 0.59], broadcast=True)
        skin.pruneWeights(0.1, normalize=False)
        self.assertRowsEqual(skin.getWeights(joints, rows=True), [[0.0, 0.4, 0.59]] * len(indices))
        skin.normalizeWeights(fast=True)
        for row in skin.getWeights(joints, rows=True):
            self.assertAlmostEqual(sum(row), 1.0)

    def test_cv_weight_changes_deformation_and_preserves_raw_values(self):
        for kind in ("curve", "periodicSurface"):
            with self.subTest(kind=kind):
                skin, shape, joints = self.makeSkin(kind)
                index = self.pointIndices(shape)[-1]
                if kind == "curve":
                    name = shape.getName(full=True) + f".cv[{index}]"
                else:
                    u, v = divmod(index, om2.MFnNurbsSurface(shape.mpath()).numCVsInV)
                    name = shape.getName(full=True) + f".cv[{u}][{v}]"
                skin.setWeights(joints, [1.0, 0.0], broadcast=True)
                original = cmds.pointPosition(name, world=True)
                skin.setWeights(joints, [0.0, 1.0], vertices=index)
                cmds.setAttr(joints[1] + ".ty", 2.0)
                actual = cmds.pointPosition(name, world=True)
                self.assertSequenceAlmostEqual(actual, [original[0], original[1] + 2.0, original[2]], places=7)
                skin.setMode("interactive", kind="normalize")
                for fast in (False, True):
                    skin.setWeights(joints, [2.0, 3.0], vertices=index, fast=fast)
                    self.assertSequenceAlmostEqual(skin.getWeights(joints, vertices=index), [2.0, 3.0])

    def test_json_position_matching_uses_input_cv_coordinates(self):
        skin, _, joints = self.makeSkin("curve")
        rows = [[0.1, 0.9], [0.2, 0.8], [0.3, 0.7], [0.4, 0.6]]
        skin.setWeights(joints, rows, rows=True)
        data = skin.getWeightsData()
        # 行を逆順にしても保存位置を対応付けに使い、元のウェイトへ戻す。
        for key in ("positions", "blendWeights"):
            data[key].reverse()
        for key in ("indices", "values"):
            data["weights"][key].reverse()
        skin.setWeights(joints, [0.5, 0.5], broadcast=True)
        skin.setWeightsData(data, method="position")
        self.assertRowsEqual(skin.getWeights(joints, rows=True), rows)

    def test_json_roundtrip_includes_sparse_point_indices(self):
        for kind in ("curve", "surface", "periodicCurve", "periodicSurface"):
            with self.subTest(kind=kind):
                skin, shape, joints = self.makeSkin(kind)
                indices = self.pointIndices(shape)
                rows = [[0.1 + order / 100.0, 0.9 - order / 100.0] for order in range(len(indices))]
                skin.setWeights(joints, rows, rows=True)
                blend = [order / len(indices) for order in range(len(indices))]
                skin.setBlendWeights(blend)
                data = skin.getWeightsData()
                self.assertEqual(data["pointIndices"], indices)
                self.assertEqual(data["vertexCount"], len(indices))
                self.assertEqual(len(data["positions"]), len(indices))
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "weights.json"
                    skin.exportWeights(path)
                    skin.setWeights(joints, [0.5, 0.5], broadcast=True)
                    skin.setBlendWeights([0.0] * len(indices))
                    skin.importWeights(path)
                    self.assertRowsEqual(skin.getWeights(joints, rows=True), rows)
                    self.assertSequenceAlmostEqual(skin.getBlendWeights(), blend)
                skin.setWeights(joints, [0.0, 1.0], broadcast=True)
                skin.setWeightsData(data, fast=True)
                self.assertRowsEqual(skin.getWeights(joints, rows=True), rows)

    def test_json_rejects_different_cv_layout_before_update(self):
        skin, _, joints = self.makeSkin("periodicSurface")
        data = skin.getWeightsData()
        data["pointIndices"] = list(range(data["vertexCount"]))
        before = list(skin.getWeights(joints))
        with self.assertRaises(ValueError):
            skin.setWeightsData(data)
        self.assertEqual(list(skin.getWeights(joints)), before)
        invalid = copy.deepcopy(data)
        invalid["pointIndices"] = [0] * invalid["vertexCount"]
        with self.assertRaises(ValueError):
            skin.setWeightsData(invalid)

    def test_mesh_only_methods_reject_nurbs_before_update(self):
        skin, shape, joints = self.makeSkin("curve")
        before = list(skin.getWeights(joints))
        for method, args in (
            (skin.smoothWeights, ()),
            (skin.getInfluenceVertices, (joints[0],)),
            (skin.redistributeWeights, ([0],)),
            (skin.invertShape, (shape,)),
        ):
            with self.subTest(method=method.__name__):
                with self.assertRaises(NotImplementedError):
                    method(*args)
                self.assertEqual(list(skin.getWeights(joints)), before)

    def test_bad_cv_inputs_do_not_change_weights(self):
        skin, shape, joints = self.makeSkin("curve")
        other_skin, other_shape, _ = self.makeSkin("curve")
        before = list(skin.getWeights(joints))
        for value, error in ((True, TypeError), (-1, IndexError), (om2.MFnNurbsCurve(shape.mpath()).numCVs, IndexError), (CV(other_shape, 0), ValueError)):
            with self.subTest(value=str(value)):
                with self.assertRaises(error):
                    skin.setWeights(joints, [0.2, 0.8], vertices=value)
                self.assertEqual(list(skin.getWeights(joints)), before)
        self.assertTrue(other_skin.isValid())


if __name__ == "__main__":
    unittest.main()
