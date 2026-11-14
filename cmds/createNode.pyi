# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaのノードを作り、実際のノード型に合ったオブジェクトを返す。

mlibでノードを作る入口はこれだけ。``cmds.createNode`` に相当する。``Node.create`` や
``Node(name, create=True)`` のような作り方は無い。

戻り値は、作ったノードの実際のnodeTypeに合ったクラスのオブジェクト。登録済みの型はそのクラス、
登録の無い型は登録表の規則で選んだクラスになる。``getType()`` はMayaのnodeType名を返す。

通常はMayaのUndoに対応し、1回のUndoで作成を戻せる(shapeと一緒に自動で作られたtransformも戻る)。
``fast=True`` なら、対応している作成条件をOpenMayaで直接処理し、Undoの履歴に残さない。
対応していない条件は、ノードを作る前にエラーにする。

.. code-block:: python

    import mlib

    node = mlib.createNode("transform", name="example")
    child = mlib.createNode("joint", n="child", p=node, ss=True)

    # shape型はshapeが返り、name= はshapeに付く。transformは getTransform() で取得する。
    selected = mlib.ls(selection=True)  # 作成したノードが選択されるため、選択は先に取る。
    shape = mlib.createNode("locator", name="exampleShape")
    transform = shape.getTransform()
"""

from ..decorator import _edit_context, _merge_flags
from ..util import _UNSET
from typing import Literal
from mlib.nodes.addDoubleLinear import AddDoubleLinear
from mlib.nodes.aimConstraint import AimConstraint
from mlib.nodes.aimMatrix import AimMatrix
from mlib.nodes.angleBetween import AngleBetween
from mlib.nodes.animCurve import AnimCurve
from mlib.nodes.animCurveTA import AnimCurveTA
from mlib.nodes.animCurveTL import AnimCurveTL
from mlib.nodes.animCurveTT import AnimCurveTT
from mlib.nodes.animCurveTU import AnimCurveTU
from mlib.nodes.animCurveUA import AnimCurveUA
from mlib.nodes.animCurveUL import AnimCurveUL
from mlib.nodes.animCurveUT import AnimCurveUT
from mlib.nodes.animCurveUU import AnimCurveUU
from mlib.nodes.blendColors import BlendColors
from mlib.nodes.blendMatrix import BlendMatrix
from mlib.nodes.blendShape import BlendShape
from mlib.nodes.blendWeighted import BlendWeighted
from mlib.nodes.blinn import Blinn
from mlib.nodes.camera import Camera
from mlib.nodes.clamp import Clamp
from mlib.nodes.cluster import Cluster
from mlib.nodes.composeMatrix import ComposeMatrix
from mlib.nodes.condition import Condition
from mlib.nodes.constraint import Constraint
from mlib.nodes.container import Container
from mlib.nodes.curveInfo import CurveInfo
from mlib.nodes.dagContainer import DagContainer
from mlib.nodes.dagNode import DagNode
from mlib.nodes.dagPose import DagPose
from mlib.nodes.decomposeMatrix import DecomposeMatrix
from mlib.nodes.displayLayer import DisplayLayer
from mlib.nodes.distanceBetween import DistanceBetween
from mlib.nodes.file import File
from mlib.nodes.fourByFourMatrix import FourByFourMatrix
from mlib.nodes.geometryConstraint import GeometryConstraint
from mlib.nodes.geometryFilter import GeometryFilter
from mlib.nodes.ikHandle import IkHandle
from mlib.nodes.inverseMatrix import InverseMatrix
from mlib.nodes.joint import Joint
from mlib.nodes.lambert import Lambert
from mlib.nodes.locator import Locator
from mlib.nodes.mesh import Mesh
from mlib.nodes.multDoubleLinear import MultDoubleLinear
from mlib.nodes.multMatrix import MultMatrix
from mlib.nodes.multiplyDivide import MultiplyDivide
from mlib.nodes.node import Node
from mlib.nodes.normalConstraint import NormalConstraint
from mlib.nodes.nurbsCurve import NurbsCurve
from mlib.nodes.nurbsSurface import NurbsSurface
from mlib.nodes.objectSet import ObjectSet
from mlib.nodes.orientConstraint import OrientConstraint
from mlib.nodes.paintableShadingDependNode import PaintableShadingDependNode
from mlib.nodes.pairBlend import PairBlend
from mlib.nodes.parentConstraint import ParentConstraint
from mlib.nodes.phong import Phong
from mlib.nodes.phongE import PhongE
from mlib.nodes.pickMatrix import PickMatrix
from mlib.nodes.place2dTexture import Place2dTexture
from mlib.nodes.place3dTexture import Place3dTexture
from mlib.nodes.plusMinusAverage import PlusMinusAverage
from mlib.nodes.pointConstraint import PointConstraint
from mlib.nodes.pointOnCurveInfo import PointOnCurveInfo
from mlib.nodes.pointOnPolyConstraint import PointOnPolyConstraint
from mlib.nodes.pointOnSurfaceInfo import PointOnSurfaceInfo
from mlib.nodes.poleVectorConstraint import PoleVectorConstraint
from mlib.nodes.reference import Reference
from mlib.nodes.reflect import Reflect
from mlib.nodes.remapValue import RemapValue
from mlib.nodes.reverse import Reverse
from mlib.nodes.scaleConstraint import ScaleConstraint
from mlib.nodes.setRange import SetRange
from mlib.nodes.shadingDependNode import ShadingDependNode
from mlib.nodes.shadingEngine import ShadingEngine
from mlib.nodes.shape import Shape
from mlib.nodes.skinCluster import SkinCluster
from mlib.nodes.standardSurface import StandardSurface
from mlib.nodes.surfaceShader import SurfaceShader
from mlib.nodes.tangentConstraint import TangentConstraint
from mlib.nodes.texture2d import Texture2d
from mlib.nodes.transform import Transform
from mlib.nodes.unitConversion import UnitConversion
from mlib.nodes.vectorProduct import VectorProduct
from typing import overload


@overload
def createNode(type: Literal["addDL"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AddDoubleLinear: ...
@overload
def createNode(type: Literal["addDoubleLinear"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AddDoubleLinear: ...
@overload
def createNode(type: Literal["aimConstraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AimConstraint: ...
@overload
def createNode(type: Literal["aimMatrix"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AimMatrix: ...
@overload
def createNode(type: Literal["angleBetween"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AngleBetween: ...
@overload
def createNode(type: Literal["animCurve"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AnimCurve: ...
@overload
def createNode(type: Literal["animCurveTA"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AnimCurveTA: ...
@overload
def createNode(type: Literal["animCurveTL"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AnimCurveTL: ...
@overload
def createNode(type: Literal["animCurveTT"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AnimCurveTT: ...
@overload
def createNode(type: Literal["animCurveTU"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AnimCurveTU: ...
@overload
def createNode(type: Literal["animCurveUA"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AnimCurveUA: ...
@overload
def createNode(type: Literal["animCurveUL"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AnimCurveUL: ...
@overload
def createNode(type: Literal["animCurveUT"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AnimCurveUT: ...
@overload
def createNode(type: Literal["animCurveUU"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> AnimCurveUU: ...
@overload
def createNode(type: Literal["blendColors"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> BlendColors: ...
@overload
def createNode(type: Literal["blendMatrix"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> BlendMatrix: ...
@overload
def createNode(type: Literal["blendShape"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> BlendShape: ...
@overload
def createNode(type: Literal["blendWeighted"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> BlendWeighted: ...
@overload
def createNode(type: Literal["blinn"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Blinn: ...
@overload
def createNode(type: Literal["camera"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Camera: ...
@overload
def createNode(type: Literal["clamp"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Clamp: ...
@overload
def createNode(type: Literal["cluster"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Cluster: ...
@overload
def createNode(type: Literal["composeMatrix"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> ComposeMatrix: ...
@overload
def createNode(type: Literal["condition"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Condition: ...
@overload
def createNode(type: Literal["constraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Constraint: ...
@overload
def createNode(type: Literal["container"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Container: ...
@overload
def createNode(type: Literal["curveInfo"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> CurveInfo: ...
@overload
def createNode(type: Literal["dagContainer"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> DagContainer: ...
@overload
def createNode(type: Literal["dagNode"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> DagNode: ...
@overload
def createNode(type: Literal["dagPose"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> DagPose: ...
@overload
def createNode(type: Literal["decomposeMatrix"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> DecomposeMatrix: ...
@overload
def createNode(type: Literal["displayLayer"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> DisplayLayer: ...
@overload
def createNode(type: Literal["distanceBetween"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> DistanceBetween: ...
@overload
def createNode(type: Literal["file"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> File: ...
@overload
def createNode(type: Literal["fourByFourMatrix"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> FourByFourMatrix: ...
@overload
def createNode(type: Literal["geometryConstraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> GeometryConstraint: ...
@overload
def createNode(type: Literal["geometryFilter"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> GeometryFilter: ...
@overload
def createNode(type: Literal["ikHandle"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> IkHandle: ...
@overload
def createNode(type: Literal["inverseMatrix"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> InverseMatrix: ...
@overload
def createNode(type: Literal["joint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Joint: ...
@overload
def createNode(type: Literal["lambert"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Lambert: ...
@overload
def createNode(type: Literal["locator"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Locator: ...
@overload
def createNode(type: Literal["mesh"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Mesh: ...
@overload
def createNode(type: Literal["multDL"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> MultDoubleLinear: ...
@overload
def createNode(type: Literal["multDoubleLinear"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> MultDoubleLinear: ...
@overload
def createNode(type: Literal["multMatrix"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> MultMatrix: ...
@overload
def createNode(type: Literal["multiplyDivide"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> MultiplyDivide: ...
@overload
def createNode(type: Literal["normalConstraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> NormalConstraint: ...
@overload
def createNode(type: Literal["nurbsCurve"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> NurbsCurve: ...
@overload
def createNode(type: Literal["nurbsSurface"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> NurbsSurface: ...
@overload
def createNode(type: Literal["objectSet"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> ObjectSet: ...
@overload
def createNode(type: Literal["orientConstraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> OrientConstraint: ...
@overload
def createNode(type: Literal["paintableShadingDependNode"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> PaintableShadingDependNode: ...
@overload
def createNode(type: Literal["pairBlend"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> PairBlend: ...
@overload
def createNode(type: Literal["parentConstraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> ParentConstraint: ...
@overload
def createNode(type: Literal["phong"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Phong: ...
@overload
def createNode(type: Literal["phongE"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> PhongE: ...
@overload
def createNode(type: Literal["pickMatrix"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> PickMatrix: ...
@overload
def createNode(type: Literal["place2dTexture"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Place2dTexture: ...
@overload
def createNode(type: Literal["place3dTexture"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Place3dTexture: ...
@overload
def createNode(type: Literal["plusMinusAverage"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> PlusMinusAverage: ...
@overload
def createNode(type: Literal["pointConstraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> PointConstraint: ...
@overload
def createNode(type: Literal["pointOnCurveInfo"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> PointOnCurveInfo: ...
@overload
def createNode(type: Literal["pointOnPolyConstraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> PointOnPolyConstraint: ...
@overload
def createNode(type: Literal["pointOnSurfaceInfo"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> PointOnSurfaceInfo: ...
@overload
def createNode(type: Literal["poleVectorConstraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> PoleVectorConstraint: ...
@overload
def createNode(type: Literal["reference"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Reference: ...
@overload
def createNode(type: Literal["reflect"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Reflect: ...
@overload
def createNode(type: Literal["remapValue"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> RemapValue: ...
@overload
def createNode(type: Literal["reverse"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Reverse: ...
@overload
def createNode(type: Literal["scaleConstraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> ScaleConstraint: ...
@overload
def createNode(type: Literal["setRange"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> SetRange: ...
@overload
def createNode(type: Literal["shadingDependNode"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> ShadingDependNode: ...
@overload
def createNode(type: Literal["shadingEngine"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> ShadingEngine: ...
@overload
def createNode(type: Literal["shape"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Shape: ...
@overload
def createNode(type: Literal["skinCluster"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> SkinCluster: ...
@overload
def createNode(type: Literal["standardSurface"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> StandardSurface: ...
@overload
def createNode(type: Literal["surfaceShader"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> SurfaceShader: ...
@overload
def createNode(type: Literal["tangentConstraint"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> TangentConstraint: ...
@overload
def createNode(type: Literal["texture2d"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Texture2d: ...
@overload
def createNode(type: Literal["transform"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Transform: ...
@overload
def createNode(type: Literal["unitConversion"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> UnitConversion: ...
@overload
def createNode(type: Literal["vectorProduct"], *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> VectorProduct: ...
@overload
def createNode(type: str, *, fast: bool = ..., name: str = ..., n: str = ..., parent: object = ..., p: object = ..., shared: bool = ..., s: bool = ..., skipSelect: bool = ..., ss: bool = ..., **kwargs: object) -> Node:
    """Mayaのノードを作り、実際の型に合ったオブジェクトを返す。

    フラグの既定値 ``_UNSET`` は、省略されたかを見分けるためだけの値。省略したフラグはMayaへ渡さず、
    Mayaの既定の動きのままにする。長い名前と短い名前を同時に指定すると、入力を調べる前、
    Undoを始める前にエラーにする。その版のMayaに無いフラグは、Mayaがエラーにする。
    ``cmds.createNode`` に無い ``query``/``edit`` は受け付けない(ほかのフラグと同じく、MayaがTypeErrorにする)。

    shapeの型(``"mesh"``・``"nurbsCurve"``・``"locator"`` など)を指定するとshapeが返り、``name=`` も
    shapeの名前になる。親を省略した場合、``getParent()``・``getTransform()`` はMayaが自動で作った
    transformになる(transformの名前は ``rename()`` で付け直す)。

    作ったノードは、``cmds.createNode`` と同じく選択される(``skipSelect=True`` の場合を除く)。
    作る前の選択を使う場合は、先に ``mlib.ls(selection=True)`` で取得しておく。

    ``shared=True`` で、同じ名前・同じ型のノードがすでにある場合は、作らずにそのノードを返す
    (cmds.createNodeが作らずにNoneを返す場合にあたる)。cmdsはルート名前空間の名前だけを使い回し、
    名前空間付きの名前では連番の名前で新しく作る。
    fast=Trueでは、名前で既存の同じ型のノードを探す近い動きになる。名前空間付きでも既存のノードを返す。
    同じ名前のノードの型が違う場合は、連番の名前で新しく作らず、RuntimeErrorにする。

    jointの下へjointを作ると、``cmds.joint`` と同じく親の ``scale`` を ``inverseScale`` へ接続する
    (通常は作成と同じ1回のUndoで戻る。fastでも接続する)。
    2026で名前が変わった型は、どの版でも ``multDoubleLinear``/``multDL``・``addDoubleLinear``/``addDL`` の
    どちらの名前でも作れる。作られるのは、その版での実際の型のノード。

    Args:
        type (str): Mayaのノード型名。
        fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
        name (str): Mayaへ渡すノード名。DAGパスの区切り ``|`` は含められない
            (Mayaは黙って置き換えてしまうため、エラーにする)。
        n (str): nameの短縮名。nameと同時には指定できない。
        parent (object): 親のノード。Node・Plug・Component・APIのオブジェクトは、持ち主のノードの完全パスに変える。
        p (object): parentの短縮名。parentと同時には指定できない。
        shared (bool): Maya標準の共有の指定。同じ名前の共有ノードがある場合に使う。
        s (bool): sharedの短縮名。sharedと同時には指定できない。
        skipSelect (bool): Trueなら、作ったノードを選択しない。
        ss (bool): skipSelectの短縮名。skipSelectと同時には指定できない。
        **kwargs (object): 通常の処理では、そのほかのMayaのフラグとしてそのまま渡す。
            fast=Trueでは、対応していないフラグを作る前にエラーにする。

    Returns:
        Node: 作ったノードの、実際のnodeTypeに合ったオブジェクト。

    Raises:
        TypeError: 長い名前と短い名前を同時に指定した場合、fastがboolでない場合、parentが対応していない型の場合、
            またはcmds.createNodeに無いフラグ(query/editなど)を指定した場合。
        ValueError: typeが空文字列か文字列でない場合、nameに ``|`` を含む場合、parent が空文字列の場合、
            または削除済みの対象を指定した場合。
        RuntimeError: Mayaが知らないノード型名の場合(unknownノードは残さない。この版に無い型は
            「not available in this Maya version」と示す)、parent が見つからない場合、
            fast=Trueでロックされた親かリファレンスされた親を指定した場合、またはMayaが作成を拒否した場合。
        NotImplementedError: fast=Trueで、対応していないフラグを指定した場合。
    """
    ...
