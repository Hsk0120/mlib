"""``mlib.nodes.camera`` のテスト。

- 形状ラッパーと標準コンストレイントを Maya 内で検証する。
- Shape 系(Mesh・NurbsCurve・Camera)とデフォーマー(Cluster)の照会の約束を固定する(担当C)。
- 形状のシェイプのメソッドと createNurbsPlane を確かめる。
"""

import importlib
import math
import sys
import unittest
import uuid

from maya.api.OpenMaya import MSpace
import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.nodes import Camera, Cluster, Mesh, Node, NurbsCurve
from support.namespaceCase import NamespaceCase


mlib_cmds = importlib.import_module("mlib.cmds")


class ShapesConstraintsTest(unittest.TestCase):
    """専用名前空間に作成したノードだけで動作を確認する。"""

    def setUp(self):
        self.selection = cmds.ls(selection=True, long=True) or []
        self.previous_namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.namespace = ':mlibShapesConstraints_' + uuid.uuid4().hex
        cmds.namespace(add=self.namespace)
        cmds.namespace(set=self.namespace)

    def tearDown(self):
        cmds.namespace(set=self.previous_namespace)
        cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        if self.selection:
            cmds.select(self.selection, replace=True)
        else:
            cmds.select(clear=True)

    def getTransform(self):
        return mlib_cmds.createNode('transform')

    def test_camera_shape_wrapper_and_focal_length(self):
        _camera_transform, camera_shape_name = cmds.camera()
        camera = mlib.Node(camera_shape_name)
        self.assertIsInstance(camera, mlib.Camera)

        cmds.setAttr(camera_shape_name + '.focalLength', 50.0)
        self.assertAlmostEqual(camera.getFocalLength(), 50.0)

        import maya.api.OpenMaya as om2
        self.assertIsInstance(camera.mfn(), om2.MFnCamera)

    def mirror_shapes(self):
        """非対称カーブと履歴付きメッシュを変換済みの親の下へ作成する。"""
        cube = mlib.Node(cmds.polyCube()[0])
        curve = mlib.Node(cmds.curve(degree=1, point=[(1, 2, 3), (4, 1, -2), (2, 5, 1)]))
        parent = self.getTransform()
        cmds.setAttr(parent.getFullName() + '.translate', 4, -2, 3)
        cmds.setAttr(parent.getFullName() + '.rotate', 23, 41, -17)
        cmds.setAttr(parent.getFullName() + '.scale', 2, 0.7, 1.3)
        cmds.parent(cube.getFullName(), curve.getFullName(), parent.getFullName(), relative=True)
        return [cube.getShape(), curve.getShape()]

    def positions(self, shape, ws=False):
        """API の内部距離単位で形状の全位置を返す。"""
        points = shape.getPoints(ws) if isinstance(shape, mlib.Mesh) else shape.getCvPositions(ws)
        return [tuple(point)[:3] for point in points]

    def assert_positions(self, actual, expected):
        """全成分を許容誤差付きで比較する。"""
        self.assertEqual(len(actual), len(expected))
        for point, reference in zip(actual, expected):
            for component, value in zip(point, reference):
                # Mesh の座標保存精度を考慮し、距離単位変更時も相対誤差で比較する。
                self.assertAlmostEqual(component, value, delta=max(1e-5, abs(value) * 1e-6))


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeGeo_"
    ENABLE_UNDO = False


class IntermediateCameraTest(_SpecCase):
    """Shape.isIntermediateObject と Camera。"""

    def test_intermediate(self):
        """デフォーマーで作られる Orig は中間オブジェクト、表示 Shape は違う。"""
        cube = cmds.polyCube(name=self.name("cube"))[0]
        cmds.cluster(cube)
        shapes = Node(cube).getShapes(intermediates=True)
        flags = [shape.isIntermediateObject() for shape in shapes]
        self.assertEqual(flags, [cmds.getAttr(shape.getFullName() + ".intermediateObject") for shape in shapes])
        self.assertEqual(sorted(flags), [False, True])

    def test_camera(self):
        """getFocalLength は mm の焦点距離で、UI の距離単位に左右されない。"""
        transform, shape = cmds.camera(name=self.name("cam"), focalLength=50)
        camera = Node(shape)
        self.assertIsInstance(camera, Camera)
        self.assertIsInstance(camera.mfn(), om2.MFnCamera)
        self.assertEqual(camera.getFocalLength(), 50.0)
        cmds.currentUnit(linear="mm")
        self.assertEqual(camera.getFocalLength(), 50.0)
        self.assertEqual(camera.getFocalLength(), cmds.getAttr(shape + ".focalLength"))
        self.assertIsNot(type(Node(transform)), Camera)


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibShapeAdd_"

    def surface(self, scale=(1, 1, 1)):
        """幅4・長さ2(lengthRatio 0.5)の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=0.5, patchesU=2, patchesV=1,
                                    axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        cmds.setAttr(transform + ".scale", *scale)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def curve(self, points, degree=3):
        """点列から NURBS カーブを作り、シェイプのラッパーを返す。"""
        transform = cmds.curve(name=self.name("curve#"), point=points, degree=degree)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def mesh(self):
        """polyPlane(2x2 分割)を作り、シェイプのラッパーを返す。"""
        transform = cmds.polyPlane(name=self.name("mesh#"), subdivisionsX=2, subdivisionsY=2,
                                   constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def assertDeletedRaises(self, node, calls):
        """ノードを削除し、各呼出しが RuntimeError になることを確かめる。"""
        cmds.delete(node.getFullName())
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(RuntimeError):
                    call(node)


class CameraQueryTest(_Case):
    """Camera の画角・向き・投影。"""

    def camera(self):
        """焦点距離50の透視カメラを作り、(transform, shape) のラッパーを返す。"""
        transform, shape = cmds.camera(name=self.name("cam#"), focalLength=50)
        return mlib.getNode(transform), mlib.getNode(shape)

    def test_field_of_view(self):
        """画角は 2*atan(フィルムバック(インチ)/0.03937/2/焦点距離) と一致し、unit で単位を変えられる。"""
        _transform, shape = self.camera()
        name = shape.getFullName()
        horizontal = 2 * math.atan(cmds.getAttr(name + ".horizontalFilmAperture") / 0.03937 / 2 / 50.0)
        vertical = 2 * math.atan(cmds.getAttr(name + ".verticalFilmAperture") / 0.03937 / 2 / 50.0)
        self.assertSequenceAlmostEqual(shape.getFieldOfView(), (math.degrees(horizontal), math.degrees(vertical)),
                                       places=6)
        self.assertSequenceAlmostEqual(shape.getFieldOfView(unit="rad"), (horizontal, vertical), places=6)
        for unit, error in (("frame", ValueError), (1, TypeError)):
            with self.subTest(unit=unit):
                with self.assertRaises(error):
                    shape.getFieldOfView(unit=unit)

    def test_directions(self):
        """位置・視線・上方向は Transform の配置(xform)と一致し、ローカルは原点・-Z・+Y。"""
        transform, shape = self.camera()
        cmds.xform(transform.getFullName(), translation=(1, 2, 3), rotation=(0, 90, 0), worldSpace=True)
        self.assertSequenceAlmostEqual(shape.getEyePoint(), (1, 2, 3))
        self.assertSequenceAlmostEqual(shape.getEyePoint(ws=False), (0, 0, 0))
        self.assertSequenceAlmostEqual(shape.getViewDirection(), (-1, 0, 0))
        self.assertSequenceAlmostEqual(shape.getViewDirection(worldSpace=False), (0, 0, -1))
        self.assertSequenceAlmostEqual(shape.getUpDirection(), (0, 1, 0))
        cmds.setAttr(transform.getFullName() + ".scale", 2, 2, 2)
        self.assertAlmostEqual(shape.getViewDirection().length(), 1.0)
        with self.assertRaises(TypeError):
            shape.getEyePoint(worldSpace=True, ws=True)
        with self.assertRaises(TypeError):
            shape.getUpDirection(worldSpace=0)

    def test_projection_and_ortho(self):
        """投影マトリクスの [0][0] は 1/tan(水平画角/2) で、カメラ前方の点は画面の中央へ写る。正投影の判定。"""
        _transform, shape = self.camera()
        matrix = shape.getProjectionMatrix()
        self.assertIsInstance(matrix, mlib.Matrix)
        horizontal = shape.getFieldOfView(unit="rad")[0]
        self.assertAlmostEqual(matrix.getElement(0, 0), 1.0 / math.tan(horizontal / 2), places=5)
        point = om2.MPoint(0, 0, -10) * matrix
        self.assertAlmostEqual(point.x / point.w, 0.0)
        self.assertAlmostEqual(point.y / point.w, 0.0)
        self.assertFalse(shape.isOrtho())
        ortho = mlib.getNode(cmds.camera(name=self.name("ortho#"), orthographic=True)[1])
        self.assertTrue(ortho.isOrtho())
        self.assertDeletedRaises(shape, (lambda node: node.getFieldOfView(), lambda node: node.getEyePoint(),
                                         lambda node: node.getProjectionMatrix(), lambda node: node.isOrtho()))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
