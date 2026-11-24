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

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Camera, Node

mlib_cmds = importlib.import_module("mlib.cmds")


class ShapesConstraintsTest(unittest.TestCase):
    """専用名前空間に作成したノードだけで動作を確認する。"""

    def setUp(self):
        self.selection = cmds.ls(selection=True, long=True) or []
        self.previous_namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.namespace = ":mlibShapesConstraints_" + uuid.uuid4().hex
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
        return mlib_cmds.createNode("transform")

    def test_camera_shape_wrapper_and_focal_length(self):
        _camera_transform, camera_shape_name = cmds.camera()
        camera = mlib.Node(camera_shape_name)
        self.assertIsInstance(camera, mlib.Camera)

        cmds.setAttr(camera_shape_name + ".focalLength", 50.0)
        self.assertAlmostEqual(camera.getPlug("focalLength").get(), 50.0)

        import maya.api.OpenMaya as om2

        self.assertIsInstance(camera.mfn(), om2.MFnCamera)

    def mirror_shapes(self):
        """非対称カーブと履歴付きメッシュを変換済みの親の下へ作成する。"""
        cube = mlib.Node(cmds.polyCube()[0])
        curve = mlib.Node(cmds.curve(degree=1, point=[(1, 2, 3), (4, 1, -2), (2, 5, 1)]))
        parent = self.getTransform()
        cmds.setAttr(parent.getName(full=True) + ".translate", 4, -2, 3)
        cmds.setAttr(parent.getName(full=True) + ".rotate", 23, 41, -17)
        cmds.setAttr(parent.getName(full=True) + ".scale", 2, 0.7, 1.3)
        cmds.parent(cube.getName(full=True), curve.getName(full=True), parent.getName(full=True), relative=True)
        return [cube.getShape(), curve.getShape()]

    def positions(self, shape, ws=False):
        """API の内部距離単位で形状の全位置を返す。"""
        points = shape.getPoints(ws)
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
        shapes = Node(cube).getShape(intermediates=True, all=True)
        flags = [shape.isIntermediateObject() for shape in shapes]
        self.assertEqual(flags, [cmds.getAttr(shape.getName(full=True) + ".intermediateObject") for shape in shapes])
        self.assertEqual(sorted(flags), [False, True])

    def test_camera(self):
        """camera の Shape は Camera、mfn は MFnCamera。トランスフォームは Camera にならない。"""
        transform, shape = cmds.camera(name=self.name("cam"), focalLength=50)
        camera = Node(shape)
        self.assertIsInstance(camera, Camera)
        self.assertIsInstance(camera.mfn(), om2.MFnCamera)
        self.assertIsNot(type(Node(transform)), Camera)


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibShapeAdd_"

    def surface(self, scale=(1, 1, 1)):
        """幅4・長さ2(lengthRatio 0.5)の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=0.5, patchesU=2, patchesV=1, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        cmds.setAttr(transform + ".scale", *scale)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def curve(self, points, degree=3):
        """点列から NURBS カーブを作り、シェイプのラッパーを返す。"""
        transform = cmds.curve(name=self.name("curve#"), point=points, degree=degree)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def mesh(self):
        """polyPlane(2x2 分割)を作り、シェイプのラッパーを返す。"""
        transform = cmds.polyPlane(name=self.name("mesh#"), subdivisionsX=2, subdivisionsY=2, constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def assertDeletedRaises(self, node, calls):
        """ノードを削除し、各呼出しが RuntimeError になることを確かめる。"""
        cmds.delete(node.getName(full=True))
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
        name = shape.getName(full=True)
        horizontal = 2 * math.atan(cmds.getAttr(name + ".horizontalFilmAperture") / 0.03937 / 2 / 50.0)
        vertical = 2 * math.atan(cmds.getAttr(name + ".verticalFilmAperture") / 0.03937 / 2 / 50.0)
        self.assertSequenceAlmostEqual(shape.getFieldOfView(), (math.degrees(horizontal), math.degrees(vertical)), places=6)
        self.assertSequenceAlmostEqual(shape.getFieldOfView(unit="rad"), (horizontal, vertical), places=6)
        for unit, error in (("frame", ValueError), (1, TypeError)):
            with self.subTest(unit=unit):
                with self.assertRaises(error):
                    shape.getFieldOfView(unit=unit)

    def test_directions(self):
        """位置・視線・上方向は Transform の配置(xform)と一致し、ローカルは原点・-Z・+Y。"""
        transform, shape = self.camera()
        cmds.xform(transform.getName(full=True), translation=(1, 2, 3), rotation=(0, 90, 0), worldSpace=True)
        self.assertSequenceAlmostEqual(shape.getPoint(), (1, 2, 3))
        self.assertSequenceAlmostEqual(shape.getPoint(ws=False), (0, 0, 0))
        self.assertSequenceAlmostEqual(shape.getDirection(), (-1, 0, 0))
        self.assertSequenceAlmostEqual(shape.getDirection(worldSpace=False), (0, 0, -1))
        self.assertSequenceAlmostEqual(shape.getDirection(kind="up"), (0, 1, 0))
        cmds.setAttr(transform.getName(full=True) + ".scale", 2, 2, 2)
        self.assertAlmostEqual(shape.getDirection().length(), 1.0)
        with self.assertRaises(TypeError):
            shape.getPoint(worldSpace=True, ws=True)
        with self.assertRaises(TypeError):
            shape.getDirection(worldSpace=0, kind="up")
        # kind を明示しても既定と同じ値。注視点は視点から視線の向きへ centerOfInterest だけ進んだ位置。
        self.assertSequenceAlmostEqual(shape.getPoint(kind="eye"), shape.getPoint())
        self.assertSequenceAlmostEqual(shape.getDirection(kind="view"), shape.getDirection())
        self.assertSequenceAlmostEqual(shape.getDirection(ws=False, kind="up"), (0, 1, 0))
        distance = cmds.getAttr(shape.getName(full=True) + ".centerOfInterest")
        self.assertSequenceAlmostEqual(shape.getPoint(kind="centerOfInterest"), tuple(shape.mfn().centerOfInterestPoint(om2.MSpace.kWorld))[:3], places=6)
        self.assertSequenceAlmostEqual(shape.getPoint(ws=False, kind="centerOfInterest"), (0, 0, -distance), places=6)
        for method in (shape.getPoint, shape.getDirection):
            with self.subTest(method=method.__name__):
                with self.assertRaises(ValueError):
                    method(kind="center")
                with self.assertRaises(TypeError):
                    method(kind=1)
        # 種類の名前は取得ごとに別(点の名前を向きへ、向きの名前を点へ渡すと ValueError)。
        with self.assertRaises(ValueError):
            shape.getPoint(kind="up")
        with self.assertRaises(ValueError):
            shape.getDirection(kind="eye")

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
        self.assertDeletedRaises(
            shape, (lambda node: node.getFieldOfView(), lambda node: node.getPoint(), lambda node: node.getProjectionMatrix(), lambda node: node.isOrtho())
        )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
