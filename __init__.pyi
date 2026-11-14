# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""mlibの入口。サブパッケージ・公開するコマンド・再読み込みの関数をまとめる。"""

from . import logger
from . import util, core, common, decorator, cmds, nodes, plugs, components, maths, json
from .core.registry import NodeRegistry as _NodeRegistry
from .core.reload import reload_package as _reload_package
from .cmds import bakeDeformer, bakeResults, bindSkin, createBlendShape, createCircle, createCluster, createContainer, createCurve, createDagContainer, createDagPose, createGroup, createIkHandle, createJointChain, createLattice, createLocator, createNode, createNurbsPlane, createPolyCube, createPolyCylinder, createPolyPlane, createPolySphere, createWire, delete, duplicate, getNode, getPlug, ls, objExists, select
from ._version import __version__
from .core import extensions as _extensions
from .nodes import AddDL as AddDL, AddDoubleLinear as AddDoubleLinear, AimConstraint as AimConstraint, AimMatrix as AimMatrix, AngleBetween as AngleBetween, AnimCurve as AnimCurve, AnimCurveTA as AnimCurveTA, AnimCurveTL as AnimCurveTL, AnimCurveTT as AnimCurveTT, AnimCurveTU as AnimCurveTU, AnimCurveUA as AnimCurveUA, AnimCurveUL as AnimCurveUL, AnimCurveUT as AnimCurveUT, AnimCurveUU as AnimCurveUU, BlendColors as BlendColors, BlendMatrix as BlendMatrix, BlendShape as BlendShape, BlendWeighted as BlendWeighted, Blinn as Blinn, Camera as Camera, Clamp as Clamp, Cluster as Cluster, ComposeMatrix as ComposeMatrix, Condition as Condition, Constraint as Constraint, Container as Container, CurveInfo as CurveInfo, DagContainer as DagContainer, DagNode as DagNode, DagPose as DagPose, DecomposeMatrix as DecomposeMatrix, DisplayLayer as DisplayLayer, DistanceBetween as DistanceBetween, File as File, FourByFourMatrix as FourByFourMatrix, GeometryConstraint as GeometryConstraint, GeometryFilter as GeometryFilter, IkHandle as IkHandle, InverseMatrix as InverseMatrix, Joint as Joint, Joints as Joints, Lambert as Lambert, Locator as Locator, Mesh as Mesh, MultDL as MultDL, MultDoubleLinear as MultDoubleLinear, MultMatrix as MultMatrix, MultiplyDivide as MultiplyDivide, Node as Node, Nodes as Nodes, NormalConstraint as NormalConstraint, NurbsCurve as NurbsCurve, NurbsSurface as NurbsSurface, ObjectSet as ObjectSet, OrientConstraint as OrientConstraint, PaintableShadingDependNode as PaintableShadingDependNode, PairBlend as PairBlend, ParentConstraint as ParentConstraint, Phong as Phong, PhongE as PhongE, PickMatrix as PickMatrix, Place2dTexture as Place2dTexture, Place3dTexture as Place3dTexture, PlusMinusAverage as PlusMinusAverage, PointConstraint as PointConstraint, PointOnCurveInfo as PointOnCurveInfo, PointOnPolyConstraint as PointOnPolyConstraint, PointOnSurfaceInfo as PointOnSurfaceInfo, PoleVectorConstraint as PoleVectorConstraint, Reference as Reference, Reflect as Reflect, RemapValue as RemapValue, Reverse as Reverse, ScaleConstraint as ScaleConstraint, SetRange as SetRange, ShadingDependNode as ShadingDependNode, ShadingEngine as ShadingEngine, Shape as Shape, SkinCluster as SkinCluster, SkinClusters as SkinClusters, StandardSurface as StandardSurface, SurfaceShader as SurfaceShader, TangentConstraint as TangentConstraint, Texture2d as Texture2d, Transform as Transform, UnitConversion as UnitConversion, VectorProduct as VectorProduct
from .plugs import BoolPlug as BoolPlug, CompoundPlug as CompoundPlug, Double3Plug as Double3Plug, DoubleAnglePlug as DoubleAnglePlug, DoubleLinearPlug as DoubleLinearPlug, DoublePlug as DoublePlug, EnumPlug as EnumPlug, FloatPlug as FloatPlug, LongPlug as LongPlug, MatrixPlug as MatrixPlug, MessagePlug as MessagePlug, MultiPlug as MultiPlug, Plug as Plug, Plugs as Plugs, RampPlug as RampPlug, ShortPlug as ShortPlug, StringPlug as StringPlug, TimePlug as TimePlug
from .components import CV as CV, UV as UV, CVs as CVs, Component as Component, Components as Components, Edge as Edge, Edges as Edges, Face as Face, Faces as Faces, LatticePoint as LatticePoint, LatticePoints as LatticePoints, PointComponent as PointComponent, PointComponents as PointComponents, SurfaceCV as SurfaceCV, SurfaceCVs as SurfaceCVs, UVs as UVs, Vertex as Vertex, VertexFace as VertexFace, VertexFaces as VertexFaces, Vertices as Vertices
from .maths import EulerRotate as EulerRotate, MSpace as MSpace, Matrix as Matrix, Quaternion as Quaternion, Scale as Scale, Shear as Shear, Transformation as Transformation, Translate as Translate, Vector as Vector
from .common import Callbacks as Callbacks, CurveFit as CurveFit, DampedSpring as DampedSpring, Deferred as Deferred, DrivenKey as DrivenKey, Environment as Environment, Keyframe as Keyframe, Keyframes as Keyframes, Module as Module, Namespace as Namespace, Plugin as Plugin, PluginPackage as PluginPackage, ProgressCancelled as ProgressCancelled, ScalarGraph as ScalarGraph, ScriptJob as ScriptJob, ScriptJobs as ScriptJobs, Selection as Selection, Time as Time, Version as Version
from typing import Any
from types import ModuleType

_node_registry: Any
_plug_registry: Any
_CLASS_PACKAGES: tuple
_EXCLUDED_CLASSES: frozenset
_names: list

def _class_sources() -> dict[str, str]:
    """ルートから取得できるクラス名と、その所属パッケージの対応を作る。

    対象は各パッケージの ``__all__`` にあるクラスだけ。名前が重なるときは、ルートの名前を優先し、
    次に ``_CLASS_PACKAGES`` で先にあるパッケージを優先する。
    commonは必要になるまでimportしない仕組みのため、ここではimportしない。
    また、大文字だけの名前(定数)は除く。

    Returns:
        dict[str, str]: クラス名から所属パッケージ名への対応。
    """
    ...
_classes: Any
__all__ = ['bakeDeformer', 'bakeResults', 'bindSkin', 'cmds', 'common', 'components', 'core', 'createBlendShape', 'createCircle', 'createCluster', 'createContainer', 'createCurve', 'createDagContainer', 'createDagPose', 'createGroup', 'createIkHandle', 'createJointChain', 'createLattice', 'createLocator', 'createNode', 'createNurbsPlane', 'createPolyCube', 'createPolyCylinder', 'createPolyPlane', 'createPolySphere', 'createWire', 'decorator', 'delete', 'duplicate', 'getNode', 'getPlug', 'json', 'logger', 'ls', 'maths', 'nodes', 'objExists', 'plugs', 'reload', 'select', 'util', 'AddDL', 'AddDoubleLinear', 'AimConstraint', 'AimMatrix', 'AngleBetween', 'AnimCurve', 'AnimCurveTA', 'AnimCurveTL', 'AnimCurveTT', 'AnimCurveTU', 'AnimCurveUA', 'AnimCurveUL', 'AnimCurveUT', 'AnimCurveUU', 'BlendColors', 'BlendMatrix', 'BlendShape', 'BlendWeighted', 'Blinn', 'BoolPlug', 'CV', 'CVs', 'Callbacks', 'Camera', 'Clamp', 'Cluster', 'Component', 'Components', 'ComposeMatrix', 'CompoundPlug', 'Condition', 'Constraint', 'Container', 'CurveFit', 'CurveInfo', 'DagContainer', 'DagNode', 'DagPose', 'DampedSpring', 'DecomposeMatrix', 'Deferred', 'DisplayLayer', 'DistanceBetween', 'Double3Plug', 'DoubleAnglePlug', 'DoubleLinearPlug', 'DoublePlug', 'DrivenKey', 'Edge', 'Edges', 'EnumPlug', 'Environment', 'EulerRotate', 'Face', 'Faces', 'File', 'FloatPlug', 'FourByFourMatrix', 'GeometryConstraint', 'GeometryFilter', 'IkHandle', 'InverseMatrix', 'Joint', 'Joints', 'Keyframe', 'Keyframes', 'Lambert', 'LatticePoint', 'LatticePoints', 'Locator', 'LongPlug', 'MSpace', 'Matrix', 'MatrixPlug', 'Mesh', 'MessagePlug', 'Module', 'MultDL', 'MultDoubleLinear', 'MultMatrix', 'MultiPlug', 'MultiplyDivide', 'Namespace', 'Node', 'Nodes', 'NormalConstraint', 'NurbsCurve', 'NurbsSurface', 'ObjectSet', 'OrientConstraint', 'PaintableShadingDependNode', 'PairBlend', 'ParentConstraint', 'Phong', 'PhongE', 'PickMatrix', 'Place2dTexture', 'Place3dTexture', 'Plug', 'Plugin', 'PluginPackage', 'Plugs', 'PlusMinusAverage', 'PointComponent', 'PointComponents', 'PointConstraint', 'PointOnCurveInfo', 'PointOnPolyConstraint', 'PointOnSurfaceInfo', 'PoleVectorConstraint', 'ProgressCancelled', 'Quaternion', 'RampPlug', 'Reference', 'Reflect', 'RemapValue', 'Reverse', 'ScalarGraph', 'Scale', 'ScaleConstraint', 'ScriptJob', 'ScriptJobs', 'Selection', 'SetRange', 'ShadingDependNode', 'ShadingEngine', 'Shape', 'Shear', 'ShortPlug', 'SkinCluster', 'SkinClusters', 'StandardSurface', 'StringPlug', 'SurfaceCV', 'SurfaceCVs', 'SurfaceShader', 'TangentConstraint', 'Texture2d', 'Time', 'TimePlug', 'Transform', 'Transformation', 'Translate', 'UV', 'UVs', 'UnitConversion', 'Vector', 'VectorProduct', 'Version', 'Vertex', 'VertexFace', 'VertexFaces', 'Vertices']

def reload() -> tuple[ModuleType]:
    """mlibを読み込み直す。

    本体を読み込み直したあと、拡張を探し直し、型の登録を作り直す。

    - 宣言済みの拡張モジュールと、読み込みに失敗した拡張モジュールは、先に解除する。
      拡張は本体の読み込み直しの途中で初期化し直す。
    - 外部SDKやMayaプラグインそのものは解除しない。
    - 読み込み直す前に取得していたクラス・関数・オブジェクトは、取得し直す。

    拡張ごとの読み込み・登録の失敗は、core.extensions.status()で確かめる。
    途中で失敗した場合に、元の状態へ自動で戻すことは保証しない。

    Returns:
        tuple[module]: 本体側で読み込み直したモジュール。拡張モジュールの一覧ではない。

    Raises:
        RuntimeError: 拡張の初期化中に呼ばれたため、読み込み直しを始められない場合。
    """
    ...

def __getattr__(name: str) -> type:
    """各パッケージのクラスを ``mlib.<クラス名>`` で取得する。

    ``mlib.Joint`` は ``mlib.nodes.Joint`` と同じクラスを返す。クラスはルートに保持せず、
    毎回所属パッケージから取得する。そのため、読み込み直したあとも現在のクラスを返す。

    先頭が大文字で、どのパッケージにも無い名前は、``mlib.nodes`` と同じく、
    登録の無いMayaのnodeTypeから作ったクラスとして返す(例: ``mlib.PointLight``)。

    Args:
        name (str): クラス名。

    Returns:
        type: 所属パッケージのクラス、またはnodeTypeから作ったクラス。

    Raises:
        AttributeError: 対象のクラスが無い場合。
    """
    ...

def __dir__() -> list[str]:
    """モジュール内の名前と、ルートから取得できるクラス名を列挙する。

    Returns:
        list[str]: 補完や探索に使う名前の一覧。
    """
    ...
