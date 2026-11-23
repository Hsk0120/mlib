"""cmds・maths・json・logger の公開APIが docstring の Raises に書いた例外のうち、ほかのテストで確かめていないものを固定する。

- cmds の作成関数(createCluster・createLattice・createWire・createGroup・createDagPose・bakeDeformer・bindSkin):
  引数の型・名前の値・見つからないノード・読めないファイルの拒否。例外の後はノードが増減しない。
  createWire は形状の無い transform を ValueError にし、Mayaが失敗したときは作りかけのノードを消す。
- common.references.createReference: 無いファイルは OSError で、リファレンスを作らない。
- json: dump・load・Snapshot.load の OSError、Snapshot.fromData・NameMapping.applyPath の TypeError、
  AttributesSnapshot.capture の MissingAttributeError。
- maths: tolerance の型の TypeError、Quaternion.fromRollBend・asRollBend の引数の拒否、Vector.cotan の ValueError。
- logger.raiseWithNotify: fromException が例外でも None でもなければ TypeError。
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib import logger
from mlib.common.references import createReference
from mlib.json import AttributesSnapshot, NameMapping, PoseSnapshot, dump, load
from mlib.maths import EulerRotate, Matrix, Quaternion, Vector
from mlib.plugs.plug import MissingAttributeError


class _ErrorCase(NamespaceCase):
    """シーン全体のノード一覧の比較と、テスト用の形状の作成を共通にする。"""

    PREFIX = "mlibSpecOtherRaises_"

    def nodes(self):
        """シーン全体のノードの完全名の集合を返す。"""
        return set(cmds.ls(long=True) or [])

    def plane(self, text="plane"):
        """ヒストリの無い平面を作り、(transform, Mesh) を返す。"""
        transform = cmds.polyPlane(name=self.name(text), width=2, height=2, subdivisionsX=2, subdivisionsY=2, constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        return transform, mlib.getNode(shape)

    def curve(self, text="curve"):
        """直線のカーブを作り、transform の名前を返す。"""
        return cmds.curve(name=self.name(text), degree=1, point=[(-1, 0, 0), (1, 0, 0)])

    def check(self, function, cases):
        """各 (例外型, 位置引数, キーワード引数) で例外になり、ノードが増減しないことを確かめる。

        Args:
            function (Callable): 確かめる関数。
            cases (Iterable[tuple]): (例外型, 位置引数のタプル, キーワード引数の辞書) の並び。
        """
        before = self.nodes()
        for error, args, kwargs in cases:
            with self.subTest(function=function.__name__, args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    function(*args, **kwargs)
                self.assertEqual(self.nodes(), before)


class CreateDeformerErrorTest(_ErrorCase):
    """createCluster・createLattice・createWire の拒否。"""

    def test_create_cluster(self):
        """名前と短縮名の同時指定・型の不正は TypeError、名前の値・空の対象は ValueError、Mayaが拒否すると RuntimeError。"""
        transform, _ = self.plane()
        empty = self.make("transform", "empty")
        self.check(
            mlib.createCluster,
            (
                (TypeError, (transform,), {"name": self.name("a"), "n": self.name("b")}),
                (TypeError, (transform,), {"relative": True, "rel": True}),
                (TypeError, (transform,), {"relative": "yes"}),
                (TypeError, (transform,), {"name": 5}),
                (TypeError, (5,), {}),
                (ValueError, (transform,), {"name": ""}),
                (ValueError, (transform,), {"name": "a|b"}),
                (ValueError, ([],), {}),
                (RuntimeError, (empty,), {}),
                (RuntimeError, (self.name("noSuchShape"),), {}),
                (RuntimeError, (self.name("noSuchShape") + ".vtx[0]",), {}),
            ),
        )

    def test_create_lattice(self):
        """名前と短縮名の同時指定・型の不正は TypeError、名前・分割数の値・空の対象は ValueError、Mayaが拒否すると RuntimeError。"""
        transform, _ = self.plane()
        empty = self.make("transform", "empty")
        self.check(
            mlib.createLattice,
            (
                (TypeError, (transform,), {"name": self.name("a"), "n": self.name("b")}),
                (TypeError, (transform,), {"divisions": (2, 2, 2), "dv": (2, 2, 2)}),
                (TypeError, (transform,), {"name": 5}),
                (TypeError, (transform,), {"divisions": (2.5, 2, 2)}),
                (TypeError, (transform,), {"objectCentered": "yes"}),
                (TypeError, (5,), {}),
                (ValueError, (transform,), {"name": ""}),
                (ValueError, (transform,), {"name": "a|b"}),
                (ValueError, (transform,), {"divisions": (2, 2)}),
                (ValueError, (transform,), {"divisions": (0, 2, 2)}),
                (ValueError, ([],), {}),
                (RuntimeError, (empty,), {}),
                (RuntimeError, (self.name("noSuchShape"),), {}),
            ),
        )

    def test_create_wire(self):
        """名前と短縮名の同時指定・型の不正は TypeError、名前・距離の値・空の対象は ValueError。

        見つからない名前は RuntimeError。形状の無い transform(ターゲット・カーブ)と、カーブでない形状は ValueError。
        """
        transform, _ = self.plane()
        curve = self.curve()
        empty = self.make("transform", "empty")
        self.check(
            mlib.createWire,
            (
                (TypeError, (transform, curve), {"name": self.name("a"), "n": self.name("b")}),
                (TypeError, (transform, curve), {"dropoffDistance": 1.0, "dds": 1.0}),
                (TypeError, (transform, curve), {"dropoffDistance": "1"}),
                (TypeError, (transform, curve), {"name": 5}),
                (TypeError, (5, curve), {}),
                (TypeError, (transform, 5), {}),
                (ValueError, (transform, curve), {"name": ""}),
                (ValueError, (transform, curve), {"name": "a|b"}),
                (ValueError, (transform, curve), {"dropoffDistance": 0.0}),
                (ValueError, (transform, curve), {"dropoffDistance": -1.0}),
                (ValueError, (transform, curve), {"dropoffDistance": float("inf")}),
                (ValueError, ([], curve), {}),
                (ValueError, (transform, []), {}),
                (RuntimeError, (transform, self.name("noSuchCurve")), {}),
                (RuntimeError, (self.name("noSuchShape"), curve), {}),
                (ValueError, (transform, empty), {}),
                (ValueError, (empty, curve), {}),
                (ValueError, (transform, transform), {}),
            ),
        )

    def test_create_wire_removes_partial_nodes(self):
        """cmds.wire が途中で失敗したら、作りかけのノード(<カーブ名>BaseWire など)を消してから例外を出す。"""
        transform, _ = self.plane()
        curve = self.curve()
        original = cmds.wire

        def failing_wire(*args, **kwargs):
            """基準のカーブを作ってから失敗する cmds.wire の代わり。"""
            cmds.createNode("transform", name=curve + "BaseWire", skipSelect=True)
            cmds.createNode("nurbsCurve", name=curve + "BaseWireShape", parent=curve + "BaseWire", skipSelect=True)
            raise RuntimeError("wireの作成に失敗しました(テスト用)")

        before = self.nodes()
        with mock.patch.object(cmds, "wire", side_effect=failing_wire):
            with self.assertRaises(RuntimeError):
                mlib.createWire(transform, curve)
        self.assertIs(cmds.wire, original)
        self.assertEqual(self.nodes(), before)


class CreateReferenceErrorTest(_ErrorCase):
    """createReference の拒否。"""

    def test_missing_file(self):
        """無いファイルは OSError(FileNotFoundError)で、リファレンスノードを作らない。"""
        folder = tempfile.mkdtemp(prefix="mlibSpecOtherRaises")
        self.addCleanup(shutil.rmtree, folder, True)
        references = cmds.ls(type="reference")
        self.check(createReference, ((OSError, (os.path.join(folder, "missing.ma"),), {}),))
        self.assertEqual(cmds.ls(type="reference"), references)


class CreateNodeErrorTest(_ErrorCase):
    """createGroup・createDagPose の拒否。"""

    def test_create_group(self):
        """名前と短縮名の同時指定、name・world の型、transform でない子・親は TypeError。"""
        _, mesh = self.plane()
        child = self.make("transform", "child")
        self.check(
            mlib.createGroup,
            (
                (TypeError, ([child],), {"name": self.name("a"), "n": self.name("b")}),
                (TypeError, ([child],), {"world": True, "w": True}),
                (TypeError, ([child],), {"name": 5}),
                (TypeError, ([child],), {"world": "yes"}),
                (TypeError, ([mesh],), {}),
                (TypeError, ([child],), {"parent": mesh}),
                (TypeError, (5,), {}),
            ),
        )
        self.assertIsNone(cmds.listRelatives(child, parent=True))

    def test_create_dag_pose(self):
        """名前と短縮名の同時指定は TypeError、見つからないノードは RuntimeError。"""
        joint = self.make("joint", "joint")
        self.check(
            mlib.createDagPose,
            (
                (TypeError, ([joint],), {"name": self.name("a"), "n": self.name("b")}),
                (TypeError, ([joint],), {"bindPose": True, "bp": True}),
                (RuntimeError, ([self.name("noSuchJoint")],), {}),
            ),
        )


class SkinFileErrorTest(_ErrorCase):
    """bakeDeformer と bindSkin の拒否。"""

    def setUp(self):
        super().setUp()
        self.folder = tempfile.mkdtemp(prefix="mlibSpecOtherRaises")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)
        super().tearDown()

    def test_bake_deformer(self):
        """見つからない名前は RuntimeError。"""
        transform, _ = self.plane()
        joint = self.make("joint", "root")
        self.check(mlib.bakeDeformer, ((RuntimeError, (self.name("noSuchShape"), joint), {}), (RuntimeError, (transform, self.name("noSuchJoint")), {})))

    def test_bind_skin_unreadable_weights(self):
        """読めないウェイトのファイル(無いファイル・フォルダー)は OSError で、skinCluster を作らない。"""
        transform, _ = self.plane()
        joint = self.make("joint", "root")
        self.check(
            mlib.bindSkin,
            (
                (OSError, ([joint], transform), {"weights": os.path.join(self.folder, "missing.json")}),
                (OSError, ([joint], transform), {"weights": self.folder}),
            ),
        )


class JsonErrorTest(_ErrorCase):
    """json の file・Snapshot・NameMapping・AttributesSnapshot の拒否。"""

    def setUp(self):
        super().setUp()
        self.folder = tempfile.mkdtemp(prefix="mlibSpecOtherRaisesJson")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)
        super().tearDown()

    def test_dump_unwritable(self):
        """無いフォルダー・フォルダーそのものへの書き出しは OSError で、ファイルを残さない。"""
        os.mkdir(os.path.join(self.folder, "dir"))
        for label, path in (("missing folder", os.path.join(self.folder, "missing", "data.json")), ("directory", os.path.join(self.folder, "dir"))):
            with self.subTest(path=label):
                with self.assertRaises(OSError):
                    dump({"a": 1}, path, "mlib.spec", 1)
                self.assertEqual(sorted(os.listdir(self.folder)), ["dir"])
                self.assertEqual(os.listdir(os.path.join(self.folder, "dir")), [])

    def test_load_unreadable(self):
        """無いファイル・フォルダーの読み込みは OSError。"""
        for label, path in (("missing", os.path.join(self.folder, "missing.json")), ("directory", self.folder)):
            with self.subTest(function="load", path=label):
                with self.assertRaises(OSError):
                    load(path, "mlib.spec", 1)
            with self.subTest(function="PoseSnapshot.load", path=label):
                with self.assertRaises(OSError):
                    PoseSnapshot.load(path)

    def test_from_data_type(self):
        """Snapshot.fromData へ辞書以外を渡すと TypeError。"""
        for data in ("data", 5, None, [("a", 1)]):
            with self.subTest(data=data):
                with self.assertRaises(TypeError):
                    PoseSnapshot.fromData(data)

    def test_apply_path_type(self):
        """NameMapping.applyPath へ文字列以外を渡すと TypeError。"""
        mapping = NameMapping(replace=[("_L_", "_R_")])
        self.assertEqual(mapping.applyPath("|root|arm_L_jnt"), "|root|arm_R_jnt")
        for path in (5, None, ["root"]):
            with self.subTest(path=path):
                with self.assertRaises(TypeError):
                    mapping.applyPath(path)

    def test_capture_missing_plug(self):
        """無い Plug を指定すると MissingAttributeError(AttributeError の派生。RuntimeError の派生ではない)。"""
        node = self.make("transform", "node")
        for target in (node + ".noSuchAttr", [node + ".translateX", node + ".noSuchAttr"]):
            with self.subTest(target=target):
                with self.assertRaises(MissingAttributeError) as context:
                    AttributesSnapshot.capture(target)
                self.assertIsInstance(context.exception, AttributeError)
                self.assertNotIsInstance(context.exception, RuntimeError)


class MathsErrorTest(unittest.TestCase):
    """maths の tolerance・軸・単位・ベクトルの拒否。例外の後は自身を変えない。"""

    def test_tolerance_type(self):
        """isGimbalLocked・hasNonUniformScale・isZero の tolerance が数値でなければ TypeError。"""
        rotation = EulerRotate(0.1, 0.2, 0.3)
        matrix = Matrix()
        vector = Vector(1.0, 2.0, 3.0)
        calls = (
            ("EulerRotate.isGimbalLocked", rotation.isGimbalLocked),
            ("Matrix.hasNonUniformScale", matrix.hasNonUniformScale),
            ("Vector.isZero", vector.isZero),
        )
        for name, call in calls:
            with self.subTest(method=name, state="valid"):
                self.assertIsInstance(call(), bool)
            for value in ("0.1", None, [0.1]):
                with self.subTest(method=name, tolerance=value):
                    with self.assertRaises(TypeError):
                        call(value)
        self.assertEqual([vector.x, vector.y, vector.z], [1.0, 2.0, 3.0])

    def test_from_roll_bend(self):
        """角度・軸・単位の型は TypeError、非有限の角度・軸の名前・同じ軸・未対応の単位は ValueError。"""
        self.assertIsInstance(Quaternion.fromRollBend(10.0, 20.0, 30.0), Quaternion)
        cases = (
            (TypeError, ("10", 0.0, 0.0), {}),
            (TypeError, (0.0, None, 0.0), {}),
            (TypeError, (0.0, 0.0, 0.0), {"aimAxis": 0}),
            (TypeError, (0.0, 0.0, 0.0), {"upAxis": None}),
            (TypeError, (0.0, 0.0, 0.0), {"unit": 5}),
            (ValueError, (float("nan"), 0.0, 0.0), {}),
            (ValueError, (0.0, float("inf"), 0.0), {}),
            (ValueError, (0.0, 0.0, 0.0), {"aimAxis": "w"}),
            (ValueError, (0.0, 0.0, 0.0), {"aimAxis": "x", "upAxis": "x"}),
            (ValueError, (0.0, 0.0, 0.0), {"unit": "grad"}),
        )
        for error, args, kwargs in cases:
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    Quaternion.fromRollBend(*args, **kwargs)

    def test_as_roll_bend(self):
        """軸・単位の型は TypeError、軸の名前・同じ軸(符号違いを含む)・未対応の単位・0のクォータニオンは ValueError。"""
        quaternion = Quaternion.fromRollBend(10.0, 20.0, 30.0)
        before = [quaternion.x, quaternion.y, quaternion.z, quaternion.w]
        self.assertEqual(len(quaternion.asRollBend()), 3)
        cases = (
            (TypeError, {"aimAxis": 0}),
            (TypeError, {"upAxis": None}),
            (TypeError, {"unit": 5}),
            (ValueError, {"aimAxis": "w"}),
            (ValueError, {"aimAxis": "x", "upAxis": "x"}),
            (ValueError, {"aimAxis": "x", "upAxis": "-x"}),
            (ValueError, {"unit": "grad"}),
        )
        for error, kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(error):
                    quaternion.asRollBend(**kwargs)
                self.assertEqual([quaternion.x, quaternion.y, quaternion.z, quaternion.w], before)
        with self.subTest(case="zero quaternion"):
            with self.assertRaises(ValueError):
                Quaternion(0.0, 0.0, 0.0, 0.0).asRollBend()

    def test_cotan(self):
        """自身か相手が0のベクトル、または平行なら ValueError。"""
        self.assertAlmostEqual(Vector(1.0, 0.0, 0.0).cotan(Vector(1.0, 1.0, 0.0)), 1.0)
        cases = (
            ("zero self", Vector(0.0, 0.0, 0.0), Vector(1.0, 0.0, 0.0)),
            ("zero other", Vector(1.0, 0.0, 0.0), Vector(0.0, 0.0, 0.0)),
            ("same direction", Vector(1.0, 0.0, 0.0), Vector(2.0, 0.0, 0.0)),
            ("opposite direction", Vector(1.0, 0.0, 0.0), Vector(-3.0, 0.0, 0.0)),
        )
        for label, vector, other in cases:
            with self.subTest(case=label):
                with self.assertRaises(ValueError):
                    vector.cotan(other)


class LoggerErrorTest(unittest.TestCase):
    """logger.raiseWithNotify の fromException の拒否。"""

    def test_from_exception_type(self):
        """fromException が例外でも None でもなければ TypeError。例外・None なら指定した型。"""
        for value in ("cause", 5, ValueError):
            with self.subTest(fromException=value):
                with self.assertRaises(TypeError):
                    logger.raiseWithNotify(ValueError, "mlibSpec: 確認用のエラー", fromException=value)
        for value in (None, KeyError("cause")):
            with self.subTest(fromException=value):
                with self.assertRaises(ValueError) as context:
                    logger.raiseWithNotify(ValueError, "mlibSpec: 確認用のエラー", fromException=value)
                self.assertIs(context.exception.__cause__, value)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
