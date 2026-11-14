# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ピボットと回転順序まで持つ、トランスフォームの値。"""

import maya.api.OpenMaya as om2
from .eulerRotate import EulerRotate
from .matrix import Matrix
from .quaternion import Quaternion
from .scale import Scale
from .shear import Shear
from .translate import Translate
from .vector import _vector_of
from typing import Any, Iterable
from typing_extensions import Self

_MTransformation: Any
_MQuaternion: Any
_MEuler: Any
_SPACE: Any
_TOLERANCE: float

def _three(value: Iterable[float] | om2.MVector | om2.MPoint, label: str) -> tuple[float, float, float]:
    """3つの数値の並びをtupleにする。

    Args:
        value (Iterable[float] | om2.MVector | om2.MPoint): 3成分の値。MPointはXYZだけを使う。
        label (str): 例外メッセージに使う名前。

    Returns:
        tuple[float, float, float]: 3つのfloat。

    Raises:
        TypeError: 数値の並びでない場合。
        ValueError: 成分の数が3でない場合。
    """
    ...

def _resolve_quaternion(value: om2.MQuaternion | om2.MEulerRotation | Iterable[float], label: str) -> om2.MQuaternion:
    """回転の指定を om2.MQuaternion にする。

    Args:
        value (om2.MQuaternion | om2.MEulerRotation | Iterable[float]): クォータニオン、オイラー回転、
            またはXYZ順のラジアンの3成分。
        label (str): 例外メッセージに使う名前。

    Returns:
        om2.MQuaternion: 新しいクォータニオン。

    Raises:
        TypeError: 回転として読めない値の場合。
        ValueError: 成分の数が3でない場合。
    """
    ...


class Transformation(om2.MTransformationMatrix):
    """om2.MTransformationMatrixを継承した、トランスフォームの値。

    4行4列の :class:`~mlib.maths.matrix.Matrix` では持てない、次の値をまとめて持つ。OpenMayaのAPIへそのまま渡せる。

    - translate・rotate(回転順序つき)・scale・shear
    - rotateAxis、回転ピボット・スケールピボットと、それぞれの補正の移動
    - jointOrient と inverseScale(Jointのための値。om2.MTransformationMatrixには無いので、このクラスが持つ)

    値の単位は、距離がcm、角度がラジアン。シーンには触れない。値は後から書き換えられる。
    プロパティで取得した値は複製なので、書き換えても自身は変わらない。書き換えるときはプロパティへ代入する。

    :attr:`matrix` は、Mayaのtransform・jointのローカルのマトリクスと同じ決まりで合成する(行ベクトルの規約)。

    ``[-sp] * S * Sh * [sp] * [spt] * [-rp] * (rotateAxis * rotate * jointOrient) * [rp] * [rpt] * [1/inverseScale] * T``

    継承した ``asMatrix()`` は om2 の計算のままで、jointOrient と inverseScale を含まない。
    基底クラスの ``scale()``・``shear()``・``rotatePivot()``・``scalePivot()`` は、同じ名前のプロパティに置き換えている
    (om2の関数として呼ぶときは ``om2.MTransformationMatrix.scale(value, space)`` と書く)。

    ハッシュはできない(dictのキーやsetの要素にできない)。``==`` は、すべての値が完全に一致するかを比べる。
    """
    __slots__: tuple
    __hash__: None
    def __new__(cls, *args, **kwargs) -> Self:
        """基底クラスの初期化でC++の実体を確保し、何も変換しない値を作る。

        Args:
            *args: ここでは使わない生成引数。
            **kwargs: ここでは使わないキーワード引数。

        Returns:
            Transformation: clsの、何も変換しない値。
        """
        ...
    def __init__(self, value: Transformation | om2.MTransformationMatrix | om2.MMatrix | Iterable[float] | None = ..., *, translate: Iterable[float] | None = ..., rotate: om2.MEulerRotation | om2.MQuaternion | Iterable[float] | None = ..., rotateOrder: int | None = ..., scale: Iterable[float] | None = ..., shear: Iterable[float] | None = ..., rotateAxis: om2.MQuaternion | om2.MEulerRotation | Iterable[float] | None = ..., jointOrient: om2.MQuaternion | om2.MEulerRotation | Iterable[float] | None = ..., rotatePivot: Iterable[float] | None = ..., rotatePivotTranslate: Iterable[float] | None = ..., scalePivot: Iterable[float] | None = ..., scalePivotTranslate: Iterable[float] | None = ..., inverseScale: Iterable[float] | None = ...) -> None:
        """コピー元の値、またはそれぞれの成分から値を設定する。

        valueを写したあとに、指定した成分で上書きする。

        Args:
            value (Transformation | om2.MTransformationMatrix | om2.MMatrix | Iterable[float] | None):
                コピー元。マトリクスからはピボットなどを復元できないので、translate・rotate・scale・shear
                だけを分解して入れる。Noneなら何も変換しない値。
            translate (Iterable[float] | None): XYZの平行移動(cm)。
            rotate (om2.MEulerRotation | om2.MQuaternion | Iterable[float] | None): 回転。
                オイラー回転は回転順序も入れる。クォータニオンと3成分(ラジアン)は、今の回転順序の値にする。
            rotateOrder (int | None): 回転順序。0(xyz)〜5(zyx)。rotateより先に入れる。
            scale (Iterable[float] | None): XYZのスケール。
            shear (Iterable[float] | None): XY・XZ・YZのシアー。
            rotateAxis (om2.MQuaternion | om2.MEulerRotation | Iterable[float] | None): rotateAxisの回転。
                3成分はXYZ順のラジアン。
            jointOrient (om2.MQuaternion | om2.MEulerRotation | Iterable[float] | None): jointOrientの回転。
                3成分はXYZ順のラジアン。
            rotatePivot (Iterable[float] | None): 回転ピボット(cm)。
            rotatePivotTranslate (Iterable[float] | None): 回転ピボットの補正の移動(cm)。
            scalePivot (Iterable[float] | None): スケールピボット(cm)。
            scalePivotTranslate (Iterable[float] | None): スケールピボットの補正の移動(cm)。
            inverseScale (Iterable[float] | None): 親のスケールを打ち消すための値。そのまま1/値を掛ける。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 成分が数値の並びでない場合、または回転として読めない場合。
            ValueError: 成分の数が合わない場合、マトリクスとして読めない場合、またはrotateOrderが0〜5でない場合。
        """
        ...
    def __eq__(self, other: object) -> bool:
        """すべての値が完全に一致するかを比べる。

        Args:
            other (object): 比べる相手。

        Returns:
            bool: om2.MTransformationMatrix系で、すべての値が一致すればTrue。違う型はNotImplemented。
        """
        ...
    def __ne__(self, other: object) -> bool:
        """:meth:`__eq__` の逆を返す。

        Args:
            other (object): 比べる相手。

        Returns:
            bool: 値が1つでも違えばTrue。違う型はNotImplemented。
        """
        ...
    def __repr__(self) -> str:
        """主な値を、読める形の文字列にする。

        Returns:
            str: translate・rotate・scaleを並べた文字列。
        """
        ...
    @property
    def translate(self) -> Translate:
        """Translate: 平行移動(cm)。"""
        ...
    @translate.setter
    def translate(self, value): ...
    @property
    def rotate(self) -> EulerRotate:
        """EulerRotate: 回転(ラジアン)。回転順序も持つ。"""
        ...
    @rotate.setter
    def rotate(self, value): ...
    @property
    def quaternion(self) -> Quaternion:
        """Quaternion: rotateをクォータニオンで表した値。代入しても回転順序は変わらない。"""
        ...
    @quaternion.setter
    def quaternion(self, value): ...
    @property
    def rotateOrder(self) -> int:
        """int: 回転順序。0(xyz)〜5(zyx)。代入すると、向きを保ったまま回転順序を変える。"""
        ...
    @rotateOrder.setter
    def rotateOrder(self, value): ...
    @property
    def scale(self) -> Scale:
        """Scale: スケール。"""
        ...
    @scale.setter
    def scale(self, value): ...
    @property
    def shear(self) -> Shear:
        """Shear: シアー(XY・XZ・YZ)。"""
        ...
    @shear.setter
    def shear(self, value): ...
    @property
    def rotateAxis(self) -> Quaternion:
        """Quaternion: rotateAxisの回転。"""
        ...
    @rotateAxis.setter
    def rotateAxis(self, value): ...
    @property
    def jointOrient(self) -> Quaternion:
        """Quaternion: jointOrientの回転。Joint以外では回転なし。"""
        ...
    @jointOrient.setter
    def jointOrient(self, value): ...
    @property
    def rotatePivot(self) -> Translate:
        """Translate: 回転ピボット(cm)。"""
        ...
    @rotatePivot.setter
    def rotatePivot(self, value): ...
    @property
    def rotatePivotTranslate(self) -> Translate:
        """Translate: 回転ピボットの補正の移動(cm)。"""
        ...
    @rotatePivotTranslate.setter
    def rotatePivotTranslate(self, value): ...
    @property
    def scalePivot(self) -> Translate:
        """Translate: スケールピボット(cm)。"""
        ...
    @scalePivot.setter
    def scalePivot(self, value): ...
    @property
    def scalePivotTranslate(self) -> Translate:
        """Translate: スケールピボットの補正の移動(cm)。"""
        ...
    @scalePivotTranslate.setter
    def scalePivotTranslate(self, value): ...
    @property
    def inverseScale(self) -> Scale:
        """Scale: 親のスケールを打ち消すための値。既定は1(打ち消さない)。"""
        ...
    @inverseScale.setter
    def inverseScale(self, value): ...
    @property
    def matrix(self) -> Matrix:
        """Matrix: すべての値を合成したローカルのマトリクス。jointOrientとinverseScaleも含む。"""
        ...
    def copy(self) -> Transformation:
        """同じ値を持つ、別のオブジェクトを作る。

        Returns:
            Transformation: 自身と同じ型の新しい値。
        """
        ...
    def isEquivalent(self, other: om2.MTransformationMatrix, tolerance: float = ...) -> bool:
        """すべての値が、許容差の中で一致するかを判定する。

        Args:
            other (om2.MTransformationMatrix): 比べる相手。
            tolerance (float): 成分ごとの許容差。

        Returns:
            bool: すべての成分の差がtolerance以下ならTrue。

        Raises:
            TypeError: otherがom2.MTransformationMatrix系でない場合。
        """
        ...
    def _scale_values(self):
        """スケールの3成分をtupleで返す(基底クラスの ``scale()`` と同じ値)。"""
        ...
    def _shear_values(self):
        """シアーの3成分をtupleで返す(基底クラスの ``shear()`` と同じ値)。"""
        ...
    def _copy_from(self, source: om2.MTransformationMatrix):
        """om2.MTransformationMatrix系の値を、成分ごとに写す。

        Args:
            source (om2.MTransformationMatrix): コピー元。Transformationなら、jointOrientとinverseScaleも写す。
        """
        ...
    def _values(self):
        """比較に使う、すべての成分を並べたtupleを返す。"""
        ...
