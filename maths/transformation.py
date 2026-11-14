"""ピボットと回転順序まで持つ、トランスフォームの値。"""

import maya.api.OpenMaya as om2

from .eulerRotate import EulerRotate
from .matrix import Matrix
from .quaternion import Quaternion
from .scale import Scale
from .shear import Shear
from .translate import Translate
from .vector import _vector_of

_MTransformation = om2.MTransformationMatrix
_MQuaternion = om2.MQuaternion
_MEuler = om2.MEulerRotation
_SPACE = om2.MSpace.kTransform
#: 2つの値を同じとみなす、既定の許容差。
_TOLERANCE = 1e-10


def _three(value, label):
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
    if isinstance(value, om2.MPoint):
        return (value.x, value.y, value.z)
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{label}は3つの数値の並びで指定してください")
    try:
        values = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        raise TypeError(f"{label}は3つの数値の並びで指定してください") from None
    if len(values) != 3:
        raise ValueError(f"{label}は3つの数値で指定してください: {len(values)}個")
    return values


def _resolve_quaternion(value, label):
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
    if isinstance(value, _MQuaternion):
        return _MQuaternion(value)
    if isinstance(value, _MEuler):
        return value.asQuaternion()
    return _MEuler(*_three(value, label)).asQuaternion()


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

    __slots__ = ("_inverse_scale", "_joint_orient")
    __hash__ = None

    def __new__(cls, *args, **kwargs):
        """基底クラスの初期化でC++の実体を確保し、何も変換しない値を作る。

        Args:
            *args: ここでは使わない生成引数。
            **kwargs: ここでは使わないキーワード引数。

        Returns:
            Transformation: clsの、何も変換しない値。
        """
        self = _MTransformation.__new__(cls)
        _MTransformation.__init__(self)
        self._joint_orient = _MQuaternion()
        self._inverse_scale = (1.0, 1.0, 1.0)
        return self

    def __init__(
        self,
        value=None,
        *,
        translate=None,
        rotate=None,
        rotateOrder=None,
        scale=None,
        shear=None,
        rotateAxis=None,
        jointOrient=None,
        rotatePivot=None,
        rotatePivotTranslate=None,
        scalePivot=None,
        scalePivotTranslate=None,
        inverseScale=None,
    ):
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
        if value is not None:
            if isinstance(value, _MTransformation):
                self._copy_from(value)
            else:
                self._copy_from(_MTransformation(om2.MMatrix(value if isinstance(value, om2.MMatrix) else Matrix(value))))
        if rotateOrder is not None:
            self.rotateOrder = rotateOrder
        components = (
            ("translate", translate),
            ("rotate", rotate),
            ("scale", scale),
            ("shear", shear),
            ("rotateAxis", rotateAxis),
            ("jointOrient", jointOrient),
            ("rotatePivot", rotatePivot),
            ("rotatePivotTranslate", rotatePivotTranslate),
            ("scalePivot", scalePivot),
            ("scalePivotTranslate", scalePivotTranslate),
            ("inverseScale", inverseScale),
        )
        for name, item in components:
            if item is not None:
                setattr(self, name, item)

    def __eq__(self, other):
        """すべての値が完全に一致するかを比べる。

        Args:
            other (object): 比べる相手。

        Returns:
            bool: om2.MTransformationMatrix系で、すべての値が一致すればTrue。違う型はNotImplemented。
        """
        if not isinstance(other, _MTransformation):
            return NotImplemented
        return self._values() == Transformation(other)._values()

    def __ne__(self, other):
        """:meth:`__eq__` の逆を返す。

        Args:
            other (object): 比べる相手。

        Returns:
            bool: 値が1つでも違えばTrue。違う型はNotImplemented。
        """
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __repr__(self):
        """主な値を、読める形の文字列にする。

        Returns:
            str: translate・rotate・scaleを並べた文字列。
        """
        translate, rotate, scale = tuple(self.translate), self.rotate, tuple(self.scale)
        return f"{type(self).__name__}(translate={translate}, rotate={rotate!r}, scale={scale})"

    @property
    def translate(self):
        """Translate: 平行移動(cm)。"""
        return _vector_of(Translate, self.translation(_SPACE))

    @translate.setter
    def translate(self, value):
        self.setTranslation(om2.MVector(*_three(value, "translate")), _SPACE)

    @property
    def rotate(self):
        """EulerRotate: 回転(ラジアン)。回転順序も持つ。"""
        return EulerRotate._wrap(self.rotation())

    @rotate.setter
    def rotate(self, value):
        if isinstance(value, _MEuler):
            self.setRotation(_MEuler(value))
        elif isinstance(value, _MQuaternion):
            self.quaternion = value
        else:
            self.setRotation(_MEuler(*_three(value, "rotate"), self.rotateOrder))

    @property
    def quaternion(self):
        """Quaternion: rotateをクォータニオンで表した値。代入しても回転順序は変わらない。"""
        return Quaternion._wrap(self.rotation(asQuaternion=True))

    @quaternion.setter
    def quaternion(self, value):
        order = self.rotateOrder
        self.setRotation(_resolve_quaternion(value, "quaternion").asEulerRotation().reorder(order))

    @property
    def rotateOrder(self):
        """int: 回転順序。0(xyz)〜5(zyx)。代入すると、向きを保ったまま回転順序を変える。"""
        return self.rotation().order

    @rotateOrder.setter
    def rotateOrder(self, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("rotateOrderは整数で指定してください")
        if not 0 <= value <= 5:
            raise ValueError(f"rotateOrderは0〜5で指定してください: {value}")
        self.setRotation(self.rotation().reorder(value))

    @property
    def scale(self):
        """Scale: スケール。"""
        return _vector_of(Scale, self._scale_values())

    @scale.setter
    def scale(self, value):
        self.setScale(_three(value, "scale"), _SPACE)

    @property
    def shear(self):
        """Shear: シアー(XY・XZ・YZ)。"""
        return _vector_of(Shear, self._shear_values())

    @shear.setter
    def shear(self, value):
        self.setShear(_three(value, "shear"), _SPACE)

    @property
    def rotateAxis(self):
        """Quaternion: rotateAxisの回転。"""
        return Quaternion._wrap(self.rotationOrientation())

    @rotateAxis.setter
    def rotateAxis(self, value):
        # om2は向きを保つようにrotateを書き換えることがあるため、rotateを入れ直す。
        rotation = _MTransformation.rotation(self)
        self.setRotationOrientation(_resolve_quaternion(value, "rotateAxis"))
        self.setRotation(rotation)

    @property
    def jointOrient(self):
        """Quaternion: jointOrientの回転。Joint以外では回転なし。"""
        return Quaternion._wrap(self._joint_orient)

    @jointOrient.setter
    def jointOrient(self, value):
        self._joint_orient = _resolve_quaternion(value, "jointOrient")

    @property
    def rotatePivot(self):
        """Translate: 回転ピボット(cm)。"""
        return _vector_of(Translate, _three(_MTransformation.rotatePivot(self, _SPACE), "rotatePivot"))

    @rotatePivot.setter
    def rotatePivot(self, value):
        self.setRotatePivot(om2.MPoint(*_three(value, "rotatePivot")), _SPACE, False)

    @property
    def rotatePivotTranslate(self):
        """Translate: 回転ピボットの補正の移動(cm)。"""
        return _vector_of(Translate, self.rotatePivotTranslation(_SPACE))

    @rotatePivotTranslate.setter
    def rotatePivotTranslate(self, value):
        self.setRotatePivotTranslation(om2.MVector(*_three(value, "rotatePivotTranslate")), _SPACE)

    @property
    def scalePivot(self):
        """Translate: スケールピボット(cm)。"""
        return _vector_of(Translate, _three(_MTransformation.scalePivot(self, _SPACE), "scalePivot"))

    @scalePivot.setter
    def scalePivot(self, value):
        self.setScalePivot(om2.MPoint(*_three(value, "scalePivot")), _SPACE, False)

    @property
    def scalePivotTranslate(self):
        """Translate: スケールピボットの補正の移動(cm)。"""
        return _vector_of(Translate, self.scalePivotTranslation(_SPACE))

    @scalePivotTranslate.setter
    def scalePivotTranslate(self, value):
        self.setScalePivotTranslation(om2.MVector(*_three(value, "scalePivotTranslate")), _SPACE)

    @property
    def inverseScale(self):
        """Scale: 親のスケールを打ち消すための値。既定は1(打ち消さない)。"""
        return _vector_of(Scale, self._inverse_scale)

    @inverseScale.setter
    def inverseScale(self, value):
        self._inverse_scale = _three(value, "inverseScale")

    @property
    def matrix(self):
        """Matrix: すべての値を合成したローカルのマトリクス。jointOrientとinverseScaleも含む。"""
        if self._joint_orient.isEquivalent(_MQuaternion(), 0.0) and self._inverse_scale == (1.0, 1.0, 1.0):
            return Matrix(self.asMatrix())
        sp, rp = tuple(self.scalePivot), tuple(self.rotatePivot)
        orient = self.rotationOrientation() * self.rotation(asQuaternion=True) * self._joint_orient
        result = (
            Matrix(translate=tuple(-v for v in sp))
            * Matrix(scale=self._scale_values(), shear=self._shear_values())
            * Matrix(translate=sp)
            * Matrix(translate=tuple(self.scalePivotTranslate))
            * Matrix(translate=tuple(-v for v in rp))
            * Matrix(rotate=orient)
            * Matrix(translate=rp)
            * Matrix(translate=tuple(self.rotatePivotTranslate))
            * Matrix(scale=tuple(1.0 / v for v in self._inverse_scale))
            * Matrix(translate=tuple(self.translate))
        )
        assert isinstance(result, Matrix)
        return result

    def copy(self):
        """同じ値を持つ、別のオブジェクトを作る。

        Returns:
            Transformation: 自身と同じ型の新しい値。
        """
        return type(self)(self)

    def isEquivalent(self, other, tolerance=_TOLERANCE):
        """すべての値が、許容差の中で一致するかを判定する。

        Args:
            other (om2.MTransformationMatrix): 比べる相手。
            tolerance (float): 成分ごとの許容差。

        Returns:
            bool: すべての成分の差がtolerance以下ならTrue。

        Raises:
            TypeError: otherがom2.MTransformationMatrix系でない場合。
        """
        if not isinstance(other, _MTransformation):
            raise TypeError("otherはTransformationかom2.MTransformationMatrixで指定してください")
        mine, theirs = self._values(), Transformation(other)._values()
        return all(abs(a - b) <= tolerance for a, b in zip(mine, theirs))

    def _scale_values(self):
        """スケールの3成分をtupleで返す(基底クラスの ``scale()`` と同じ値)。"""
        return tuple(_MTransformation.scale(self, _SPACE))

    def _shear_values(self):
        """シアーの3成分をtupleで返す(基底クラスの ``shear()`` と同じ値)。"""
        return tuple(_MTransformation.shear(self, _SPACE))

    def _copy_from(self, source):
        """om2.MTransformationMatrix系の値を、成分ごとに写す。

        Args:
            source (om2.MTransformationMatrix): コピー元。Transformationなら、jointOrientとinverseScaleも写す。
        """
        self.setTranslation(source.translation(_SPACE), _SPACE)
        self.setScale(_MTransformation.scale(source, _SPACE), _SPACE)
        self.setShear(_MTransformation.shear(source, _SPACE), _SPACE)
        # rotateAxisを入れるとom2がrotateを書き換えることがあるため、rotateはそのあとに入れる。
        self.setRotationOrientation(source.rotationOrientation())
        self.setRotation(_MTransformation.rotation(source))
        self.setRotatePivot(_MTransformation.rotatePivot(source, _SPACE), _SPACE, False)
        self.setRotatePivotTranslation(source.rotatePivotTranslation(_SPACE), _SPACE)
        self.setScalePivot(_MTransformation.scalePivot(source, _SPACE), _SPACE, False)
        self.setScalePivotTranslation(source.scalePivotTranslation(_SPACE), _SPACE)
        if isinstance(source, Transformation):
            self._joint_orient = _MQuaternion(source._joint_orient)
            self._inverse_scale = tuple(source._inverse_scale)

    def _values(self):
        """比較に使う、すべての成分を並べたtupleを返す。"""
        rotation = _MTransformation.rotation(self)
        values = list(self.translation(_SPACE))
        values += [rotation.x, rotation.y, rotation.z, float(rotation.order)]
        values += self._scale_values() + self._shear_values()
        values += list(self.rotationOrientation())
        values += _three(_MTransformation.rotatePivot(self, _SPACE), "rotatePivot")
        values += list(self.rotatePivotTranslation(_SPACE))
        values += _three(_MTransformation.scalePivot(self, _SPACE), "scalePivot")
        values += list(self.scalePivotTranslation(_SPACE))
        values += list(self._joint_orient) + list(self._inverse_scale)
        return tuple(values)
