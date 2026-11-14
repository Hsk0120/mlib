# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ノードのクラスを公開し、Mayaのノード型との対応を宣言する。

手書きのクラスは、通常のimportと ``__all__`` で公開する。Mayaのノード型名(nodeType)との対応は
``_WRAPPER_CLASSES`` に書く。

登録の無いMayaのノード型は、取得するとき(``mlib.ls``・``mlib.getNode``・``Node(name)``)に
クラスを自動で作って使う。親クラスは、Mayaの継承の流れの上で最も近い登録クラスになる。
クラス名は型名の先頭を大文字にしたもの(例: ``pointLight`` → ``PointLight``)。
自動で作ったクラスは ``mlib.nodes.<TypeName>`` でも取得できる。
Mayaが認識しない型名(プラグインが読み込まれていない場合など)は ``AttributeError`` になる。

自動で作ったクラスは ``__all__`` に入れず、Sphinxにも載せない。
登録クラスと自動で作るクラスの間にある抽象型(weightGeometryFilter・containerBase・entityなど)の
クラスは作らない(デフォーマーに共通のgeometryFilterは、手書きのGeometryFilterとして登録している)。
そのため、``isinstance`` はMayaの継承を表さない。継承を判定するときは ``Node.isType()`` を使う。

自動で作ったクラスは、次のときに作り直される。持っているクラスの参照は取り直す。

- 登録表を変更したとき。
- ``mlib.Plugin`` でプラグインをロード・アンロードしたとき。
- ``mlib.reload()`` を実行したとき。
"""

from ..core.registry import _node_type_exists
from .node import Node, Nodes
from .shape import Shape
from .transform import Transform
from .addDoubleLinear import AddDL, AddDoubleLinear
from .aimConstraint import AimConstraint
from .aimMatrix import AimMatrix
from .angleBetween import AngleBetween
from .animCurve import AnimCurve
from .animCurveTA import AnimCurveTA
from .animCurveTL import AnimCurveTL
from .animCurveTT import AnimCurveTT
from .animCurveTU import AnimCurveTU
from .animCurveUA import AnimCurveUA
from .animCurveUL import AnimCurveUL
from .animCurveUT import AnimCurveUT
from .animCurveUU import AnimCurveUU
from .blendColors import BlendColors
from .blendMatrix import BlendMatrix
from .blendShape import BlendShape
from .blendWeighted import BlendWeighted
from .blinn import Blinn
from .camera import Camera
from .clamp import Clamp
from .cluster import Cluster
from .composeMatrix import ComposeMatrix
from .condition import Condition
from .constraint import Constraint
from .container import Container
from .curveInfo import CurveInfo
from .dagContainer import DagContainer
from .dagNode import DagNode
from .dagPose import DagPose
from .decomposeMatrix import DecomposeMatrix
from .displayLayer import DisplayLayer
from .distanceBetween import DistanceBetween
from .file import File
from .fourByFourMatrix import FourByFourMatrix
from .geometryConstraint import GeometryConstraint
from .geometryFilter import GeometryFilter
from .ikHandle import IkHandle
from .inverseMatrix import InverseMatrix
from .joint import Joint, Joints
from .lambert import Lambert
from .locator import Locator
from .mesh import Mesh
from .multDoubleLinear import MultDL, MultDoubleLinear
from .multiplyDivide import MultiplyDivide
from .multMatrix import MultMatrix
from .normalConstraint import NormalConstraint
from .nurbsCurve import NurbsCurve
from .nurbsSurface import NurbsSurface
from .objectSet import ObjectSet
from .orientConstraint import OrientConstraint
from .paintableShadingDependNode import PaintableShadingDependNode
from .pairBlend import PairBlend
from .parentConstraint import ParentConstraint
from .phong import Phong
from .phongE import PhongE
from .pickMatrix import PickMatrix
from .place2dTexture import Place2dTexture
from .place3dTexture import Place3dTexture
from .plusMinusAverage import PlusMinusAverage
from .pointConstraint import PointConstraint
from .pointOnCurveInfo import PointOnCurveInfo
from .pointOnPolyConstraint import PointOnPolyConstraint
from .pointOnSurfaceInfo import PointOnSurfaceInfo
from .poleVectorConstraint import PoleVectorConstraint
from .reference import Reference
from .reflect import Reflect
from .remapValue import RemapValue
from .reverse import Reverse
from .scaleConstraint import ScaleConstraint
from .setRange import SetRange
from .shadingDependNode import ShadingDependNode
from .shadingEngine import ShadingEngine
from .skinCluster import SkinCluster, SkinClusters
from .standardSurface import StandardSurface
from .surfaceShader import SurfaceShader
from .tangentConstraint import TangentConstraint
from .texture2d import Texture2d
from .unitConversion import UnitConversion
from .vectorProduct import VectorProduct

__all__ = ['AddDL', 'AddDoubleLinear', 'AimConstraint', 'AimMatrix', 'AngleBetween', 'AnimCurve', 'AnimCurveTA', 'AnimCurveTL', 'AnimCurveTT', 'AnimCurveTU', 'AnimCurveUA', 'AnimCurveUL', 'AnimCurveUT', 'AnimCurveUU', 'BlendColors', 'BlendMatrix', 'BlendShape', 'BlendWeighted', 'Blinn', 'Camera', 'Clamp', 'Cluster', 'ComposeMatrix', 'Condition', 'Constraint', 'Container', 'CurveInfo', 'DagContainer', 'DagNode', 'DagPose', 'DecomposeMatrix', 'DisplayLayer', 'DistanceBetween', 'File', 'FourByFourMatrix', 'GeometryConstraint', 'GeometryFilter', 'IkHandle', 'InverseMatrix', 'Joint', 'Joints', 'Lambert', 'Locator', 'Mesh', 'MultDL', 'MultDoubleLinear', 'MultMatrix', 'MultiplyDivide', 'Node', 'Nodes', 'NormalConstraint', 'NurbsCurve', 'NurbsSurface', 'ObjectSet', 'OrientConstraint', 'PaintableShadingDependNode', 'PairBlend', 'ParentConstraint', 'Phong', 'PhongE', 'PickMatrix', 'Place2dTexture', 'Place3dTexture', 'PlusMinusAverage', 'PointConstraint', 'PointOnCurveInfo', 'PointOnPolyConstraint', 'PointOnSurfaceInfo', 'PoleVectorConstraint', 'Reference', 'Reflect', 'RemapValue', 'Reverse', 'ScaleConstraint', 'SetRange', 'ShadingDependNode', 'ShadingEngine', 'Shape', 'SkinCluster', 'SkinClusters', 'StandardSurface', 'SurfaceShader', 'TangentConstraint', 'Texture2d', 'Transform', 'UnitConversion', 'VectorProduct']
_WRAPPER_CLASSES: dict

def __getattr__(name: str) -> type:
    """登録の無いMayaのノード型のクラスを、``mlib.nodes.<TypeName>`` の形で取得する。

    登録クラスやサブモジュールなど、モジュールに普通にある名前は対象にならない。
    次の順に型名を作り、登録表に同じ名前があるか、Mayaが認識する型かを調べる。

    1. 名前の先頭を小文字にした型名(``PointLight`` → ``pointLight``)。
    2. 名前そのまま(``AISEnvFacade``)。

    Args:
        name (str): クラス名。先頭は大文字。

    Returns:
        type: 登録クラス、またはMayaの継承に沿って自動で作ったクラス。

    Raises:
        AttributeError: 先頭が大文字でない場合、またはMayaが認識しない型名の場合
            (プラグインが読み込まれていない場合を含む)。
    """
    ...
