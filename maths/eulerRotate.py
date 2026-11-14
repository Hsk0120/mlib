"""オイラー回転の値。om2.MEulerRotation を継承し、ラジアンの角度と回転順序を持つ。"""

import math
import operator

import maya.api.OpenMaya as om2

from ..util import (
    _angle_unit,
    _checked_digits,
    _checked_index,
    _checked_tolerance,
    _copy_state,
    _finite_vector,
    _foreign_comparison,
    _from_radians,
    _rethrow_init_error,
    _round_float,
    _to_radians,
)
from .quaternion import Quaternion
from .vector import _reduce_value

_MEuler = om2.MEulerRotation
_MQuaternion = om2.MQuaternion
_NEW = _MEuler.__new__
_INIT = _MEuler.__init__
_GET = _MEuler.__getitem__
_SET = _MEuler.__setitem__
_NUMBER = (int, float)

#: 回転順序の名前。並びの番号が、om2 の ``MEulerRotation.kXYZ`` (0)〜``kZYX`` (5)と、
#: Maya の rotateOrder アトリビュートの番号に対応する。
ORDER_NAMES = ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx")
_ORDER_INDEX = {name: index for index, name in enumerate(ORDER_NAMES)}


def orderIndex(order):
    """回転順序の名前か番号を、om2 の番号(0〜5)へ変換する。

    Args:
        order (str | int): ``"xyz"`` などの名前(大文字と小文字は区別しない)、または
            om2 の ``MEulerRotation.kXYZ``〜``kZYX`` (Maya の rotateOrder と同じ番号)。

    Returns:
        int: om2 の回転順序の番号。

    Raises:
        ValueError: 対応していない名前・番号の場合、または bool などの正しくない型の場合。
    """
    if isinstance(order, str):
        index = _ORDER_INDEX.get(order.lower())
        if index is None:
            raise ValueError(f"対応していない回転順序です: {order!r}")
        return index
    if isinstance(order, bool):
        raise ValueError(f"対応していない回転順序です: {order!r}")
    try:
        index = operator.index(order)
    except TypeError:
        raise ValueError(f"対応していない回転順序です: {order!r}") from None
    if not 0 <= index < 6:
        raise ValueError(f"対応していない回転順序です: {order!r}")
    return index


def _euler_keywords(x=0.0, y=0.0, z=0.0, order=None):
    """キーワード引数で渡された EulerRotate の引数を、(x, y, z, order) にまとめる。

    Args:
        x (float): X 回転(ラジアン)。
        y (float): Y 回転(ラジアン)。
        z (float): Z 回転(ラジアン)。
        order (str | int | None): 回転順序。None は xyz。

    Returns:
        tuple: (x, y, z, order)。
    """
    return x, y, z, order


class EulerRotate(om2.MEulerRotation):
    """オイラー回転の値。XYZの角度(rad)と回転順序を持ち、値を書き換えられる。

    om2.MEulerRotationを継承しているので、OpenMaya APIへそのまま渡せる。Vectorの派生クラスではない。

    作り方は ``__init__`` を参照。MEulerRotationを渡すと、回転順序も含めてコピーする。
    コンストラクタでorderを指定しても、成分は並べ替えない。姿勢を保ったまま回転順序を変えるときは
    ``reorder()`` を使う。orderはMayaのrotateOrderと同じ0〜5。コンストラクタは回転順序の名前も受け付け、
    :attr:`orderName` でも名前で取得・設定できる。

    計算はom2と同じで、結果はEulerRotateで返す。

    - ``+`` / ``-``: 回転順序が同じなら成分ごとに計算する。違えば、右辺を左辺の回転順序へ変換してから計算する。
    - ``*``: 数値なら成分を拡大縮小する。EulerRotate・Quaternionなら回転を合成する。
    - ``数値 * e`` と ``e / 数値`` はmlibで加えたもの。
    - ``+=`` / ``-=`` / ``*=`` / ``/=`` は自身を書き換える。

    継承したメソッドのうち数学の値を返すものも、対応するmlibの型で返す。
    コピーを返すメソッドと、名前がItで終わる自身を書き換えるメソッドは分けてある。

    ハッシュは作れない(dictのキーやsetの要素にできない)。番号は-3〜2で、範囲の外はIndexError。
    スライスは成分のtupleを返し、反復はXYZの順。
    ``==`` は回転順序も含めて、成分が完全に一致するときだけTrue。ほかの型との比較は
    :class:`~mlib.maths.vector.Vector` と同じ扱い。表示は度、中の値はrad。
    """

    __slots__ = ()
    __hash__ = None

    def __new__(cls, *args, **kwargs):
        """回転が0(xyzの順)のclsのインスタンスを作る。

        基底クラスの初期化で、C++の実体を先に用意しておく。こうすると、``__init__`` を通らなかったり
        失敗したりしても、実体へアクセスできる。詳しくは :meth:`mlib.maths.vector.Vector.__new__` を参照。

        Args:
            *args: ここでは使わない、作るときの引数。
            **kwargs: ここでは使わないキーワード引数。

        Returns:
            EulerRotate: 回転が0のclsのインスタンス。
        """
        self = _NEW(cls)
        _INIT(self)
        return self

    def __init__(self, *args, **kwargs):
        """成分と回転順序を設定する。

        すべての引数を確かめてから書き込むので、例外が起きても値は変わらない。

        Args:
            *args: ``()``、``(x, y, z)``、``(x, y, z, order)``、``(values)``、
                ``(values, order)``、または ``(MEulerRotation)``。角度の既定はラジアン。
            **kwargs: ``order``、または ``x`` / ``y`` / ``z`` / ``order`` のキーワード引数。
                ``unit`` は数値の成分の単位。既定は ``"rad"`` (om2と同じ)で、``"deg"`` なら度
                (``"degree"`` / ``"radians"`` などの別名も使える)。中の値はいつもラジアンで持つ。
                MEulerRotationをコピーするときは、``"rad"`` 以外を指定できない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 引数の数や型が正しくない場合、同じ引数を2回指定した場合、
                またはunitが文字列でもNoneでもない場合。
            ValueError: 対応していない回転順序・単位の場合、成分が数値でない場合、
                またはMEulerRotationを渡して度を指定した場合。
        """
        unit = "rad"
        if "unit" in kwargs:
            kwargs = dict(kwargs)
            unit = _angle_unit(kwargs.pop("unit"))
        if not kwargs and unit == "rad":
            # よく使う ()、(x, y, z)、(x, y, z, order) は、引数の解析を省く。
            count = len(args)
            if count == 3 or count == 4:
                x, y, z = args[0], args[1], args[2]
                if isinstance(x, _NUMBER) and isinstance(y, _NUMBER) and isinstance(z, _NUMBER):
                    index = orderIndex(args[3]) if count == 4 else 0
                    self.x = x
                    self.y = y
                    self.z = z
                    self.order = index
                    return
            elif count == 0:
                self.x = 0.0
                self.y = 0.0
                self.z = 0.0
                self.order = 0
                return
        if "x" in kwargs or "y" in kwargs or "z" in kwargs:
            try:
                x, y, z, order = _euler_keywords(*args, **kwargs)
            except TypeError as error:
                _rethrow_init_error(type(self), error)
        else:
            order = kwargs.pop("order", None)
            if kwargs:
                raise TypeError(f"EulerRotateに想定外のキーワード引数が渡されました: {', '.join(sorted(kwargs))}")
            count = len(args)
            if count == 1 and order is None and isinstance(args[0], _MEuler):
                if unit != "rad":
                    raise ValueError("unitでは既存の回転を変換できません。値はすでにラジアンです")
                self.setValue(args[0])
                return
            if count in (1, 2) and not isinstance(args[0], _NUMBER):
                if count == 2:
                    if order is not None:
                        raise TypeError("EulerRotateに'order'が複数回渡されました")
                    order = args[1]
                x, y, z = args[0]
            elif count in (3, 4):
                x, y, z = args[0], args[1], args[2]
                if count == 4:
                    if order is not None:
                        raise TypeError("EulerRotateに'order'が複数回渡されました")
                    order = args[3]
            elif count == 0:
                x = y = z = 0.0
            else:
                raise TypeError("EulerRotateには()、(x, y, z[, order])、(values[, order])、(EulerRotate)のどれかを指定してください")
        index = 0 if order is None else orderIndex(order)
        if not (isinstance(x, _NUMBER) and isinstance(y, _NUMBER) and isinstance(z, _NUMBER)):
            # 数値以外は om2 の変換の決まりに任せる(文字列などは om2 と同じ ValueError になる)。
            source = _MEuler(x, y, z)
            x, y, z = source.x, source.y, source.z
        if unit == "deg":
            x, y, z = math.radians(x), math.radians(y), math.radians(z)
        self.x = x
        self.y = y
        self.z = z
        self.order = index

    def __getitem__(self, index):
        """回転成分を取得する。

        Args:
            index (int | slice): -3〜2 の番号(X、Y、Z の順)、またはスライス。

        Returns:
            float | tuple[float, ...]: 指定した成分(ラジアン)。スライスでは成分の tuple。

        Raises:
            TypeError: 番号が整数でもスライスでもない場合。
            IndexError: 番号が範囲の外の場合。
        """
        if index.__class__ is int and -3 <= index < 3:
            return _GET(self, index)
        if isinstance(index, slice):
            return (self.x, self.y, self.z)[index]
        return _GET(self, _checked_index(index, 3, "EulerRotate"))

    def __setitem__(self, index, value):
        """回転成分を設定する。

        Args:
            index (int): -3〜2 の番号。
            value (float): 設定する値(ラジアン)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 番号が整数でない場合。
            IndexError: 番号が範囲の外の場合。
        """
        if index.__class__ is not int or not -3 <= index < 3:
            index = _checked_index(index, 3, "EulerRotate")
        _SET(self, index, value)

    def __iter__(self):
        """X、Y、Z の順に、回転の成分を1つずつ返す。

        Returns:
            Iterator[float]: 3成分(ラジアン)のイテレータ。
        """
        return iter((self.x, self.y, self.z))

    def __reduce__(self):
        """copy・pickleのために、コンストラクタを通さずに作り直す情報を返す。

        Returns:
            tuple: ``(_rebuild, (type(self), (x, y, z, order))[, state])``。
            利用者の派生クラスの ``__init__`` は呼ばない。``__dict__`` と ``__slots__`` の
            アトリビュートは、作り直すときに元に戻す。
        """
        return _reduce_value(self, (self.x, self.y, self.z, self.order))

    def __reduce_ex__(self, protocol):
        """pickle のプロトコルに関係なく、__reduce__ と同じ情報を返す。

        Args:
            protocol (int): pickle のプロトコル番号。使わない。

        Returns:
            tuple: ``__reduce__()`` の結果。
        """
        return self.__reduce__()

    def __copy__(self):
        """同じ型で、成分と回転順序が同じコピーを返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートも、浅くコピーする。

        Returns:
            EulerRotate: 自身と同じクラスの新しいインスタンス。
        """
        return _copy_state(self, type(self)._wrap(self))

    def __deepcopy__(self, memo):
        """同じ型で、成分と回転順序が同じコピーを返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートは、深くコピーする。

        Args:
            memo (dict): copy.deepcopy の memo。

        Returns:
            EulerRotate: 自身と同じクラスの新しいインスタンス。
        """
        return _copy_state(self, type(self)._wrap(self), memo)

    def __repr__(self):
        """デバッグ用の表記を返す。回転の成分(度)と回転順序の名前を含む。

        Returns:
            str: ``EulerRotate(degrees=(90, 0, -45), order='xyz')`` の形の文字列。
            中の値はラジアンのまま。
        """
        values = ", ".join(f"{value:.15g}" for value in self.asDegrees())
        return f"{type(self).__name__}(degrees=({values}), order={self.orderName!r})"

    __str__ = __repr__

    def __eq__(self, other):
        """MEulerRotation 系の値と比べる。

        om2 と同じく、回転順序も含めて完全に一致するかを調べる。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | types.NotImplementedType: MEulerRotation 系なら om2 で比べた結果。
            ほかの om2 の型なら False。それ以外の型なら NotImplemented(相手の比較に任せ、
            どちらも決めなければ False になる)。
        """
        if isinstance(other, _MEuler):
            return _MEuler.__eq__(self, other)
        return _foreign_comparison(other, False)

    def __ne__(self, other):
        """``__eq__`` の否定を返す。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | types.NotImplementedType: MEulerRotation 系なら om2 で比べた結果。
            ほかの om2 の型なら True。それ以外の型なら NotImplemented。
        """
        if isinstance(other, _MEuler):
            return _MEuler.__ne__(self, other)
        return _foreign_comparison(other, True)

    def __add__(self, other):
        """om2 の ``+`` の結果を EulerRotate で返す。

        Args:
            other (object): MEulerRotation 系。回転順序が違えば、自身の回転順序へ変換してから足す。

        Returns:
            EulerRotate | types.NotImplementedType: 和。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MEuler):
            return NotImplemented
        return EulerRotate._wrap(_MEuler.__add__(self, other))

    def __radd__(self, other):
        """左辺の MEulerRotation 系との和を返す。

        Args:
            other (object): MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 和。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MEuler):
            return NotImplemented
        return EulerRotate._wrap(_MEuler.__add__(other, self))

    def __iadd__(self, other):
        """MEulerRotation 系の値を自身へ足す。

        Args:
            other (object): MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MEuler):
            return NotImplemented
        return _MEuler.__iadd__(self, other)

    def __sub__(self, other):
        """om2 の ``-`` の結果を EulerRotate で返す。

        Args:
            other (object): MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 差。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MEuler):
            return NotImplemented
        return EulerRotate._wrap(_MEuler.__sub__(self, other))

    def __rsub__(self, other):
        """左辺の MEulerRotation 系から自身を引いた値を返す。

        Args:
            other (object): MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 差。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MEuler):
            return NotImplemented
        return EulerRotate._wrap(_MEuler.__sub__(other, self))

    def __isub__(self, other):
        """MEulerRotation 系の値を自身から引く。

        Args:
            other (object): MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MEuler):
            return NotImplemented
        return _MEuler.__isub__(self, other)

    def __mul__(self, other):
        """om2 の ``*`` の結果を EulerRotate で返す。

        Args:
            other (object): 数値(成分を拡大縮小する)、または MEulerRotation 系 /
                MQuaternion 系(自身を先に回す、回転の合成)。

        Returns:
            EulerRotate | types.NotImplementedType: 結果。対応しない型は NotImplemented。
        """
        if not isinstance(other, (int, float, _MEuler, _MQuaternion)):
            return NotImplemented
        return EulerRotate._wrap(_MEuler.__mul__(self, other))

    def __rmul__(self, other):
        """左から掛ける。計算の意味は om2 と同じ。

        Args:
            other (object): 数値、または左辺の MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 結果。対応しない型は NotImplemented。
        """
        if isinstance(other, _NUMBER):
            return EulerRotate._wrap(_MEuler.__mul__(self, other))
        if isinstance(other, _MEuler):
            return EulerRotate._wrap(_MEuler.__mul__(other, self))
        return NotImplemented

    def __imul__(self, other):
        """自身を数値倍する、または自身に回転を合成する。

        Args:
            other (object): 数値、MEulerRotation 系、または MQuaternion 系。

        Returns:
            EulerRotate | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        if not isinstance(other, (int, float, _MEuler, _MQuaternion)):
            return NotImplemented
        return _MEuler.__imul__(self, other)

    def __truediv__(self, other):
        """成分ごとに数値で割った値を返す(om2 には無く、mlib で加えたもの)。

        回転順序はそのままで、それぞれの成分を other で割る。

        Args:
            other (object): 割る数。int か float。

        Returns:
            EulerRotate | types.NotImplementedType: 新しい回転。対応しない型は NotImplemented。

        Raises:
            ZeroDivisionError: other が 0 の場合。
        """
        if not isinstance(other, _NUMBER):
            return NotImplemented
        if other == 0:
            raise ZeroDivisionError("EulerRotateを0で割ることはできません")
        result = EulerRotate._wrap(self)
        result.x = self.x / other
        result.y = self.y / other
        result.z = self.z / other
        return result

    def __itruediv__(self, other):
        """自身のそれぞれの成分を数値で割る(mlib で加えたもの。回転順序は変えない)。

        Args:
            other (object): 割る数。int か float。

        Returns:
            EulerRotate | types.NotImplementedType: 自身。対応しない型は NotImplemented。

        Raises:
            ZeroDivisionError: other が 0 の場合。
        """
        if not isinstance(other, _NUMBER):
            return NotImplemented
        if other == 0:
            raise ZeroDivisionError("EulerRotateを0で割ることはできません")
        self.x = self.x / other
        self.y = self.y / other
        self.z = self.z / other
        return self

    def __neg__(self):
        """om2 の単項 ``-`` (成分の符号を反対にした回転)を EulerRotate で返す。

        Returns:
            EulerRotate: 新しい回転。
        """
        return EulerRotate._wrap(_MEuler.__neg__(self))

    def __round__(self, ndigits=None):
        """組み込みの ``round`` から呼ばれ、度で丸める :meth:`round` を呼ぶ。

        Args:
            ndigits (int | None): roundと同じ桁数。

        Returns:
            EulerRotate: 同じ型の新しい回転。
        """
        return self.round(ndigits)

    @classmethod
    def fromIterable(cls, values, order="xyz"):
        """3つの値の並びから作る。

        Args:
            values (Iterable[float]): ラジアンの3つの成分。
            order (str | int): 回転順序。既定は ``"xyz"``。

        Returns:
            EulerRotate: 呼び出したクラスの新しいインスタンス。

        Raises:
            ValueError: 要素の数が3でない場合、または対応していない回転順序の場合。
        """
        values = tuple(values)
        if len(values) != 3:
            raise ValueError(f"{cls.__name__}には3つの値を指定してください")
        return cls(values[0], values[1], values[2], order)

    @classmethod
    def fromDegrees(cls, x, y, z, order="xyz"):
        """度で表した3つの成分から作る。

        Args:
            x (float): X の回転角度(度)。
            y (float): Y の回転角度(度)。
            z (float): Z の回転角度(度)。
            order (str | int): 回転順序。既定は ``"xyz"``。

        Returns:
            EulerRotate: ラジアンに変換した回転。

        Raises:
            ValueError: 対応していない回転順序の場合。
        """
        return cls(math.radians(x), math.radians(y), math.radians(z), order)

    @classmethod
    def fromYawPitch(cls, direction, order="xyz"):
        """基準軸を指定した方向へ向ける回転を作る。

        基準軸は回転順序の最初の軸。ピッチとヨーの2軸だけで向ける。

        回転順序の3文字は「基準軸・ピッチの軸・ヨーの軸」を表す(``"xyz"`` なら、X軸を
        Y軸周りのピッチの後にZ軸周りのヨーで向ける)。基準軸の成分はいつも0で、ロール(基準軸周りのひねり)は含まない。
        ピッチは -90〜90 度、ヨーは -180〜180 度の範囲になる。真上・真下(ヨーの軸の方向)では、ヨーを0にする。

        Args:
            direction (om2.MVector | om2.MPoint | Iterable[float]): 向ける方向。長さは問わない。
            order (str | int): 回転順序。既定は ``"xyz"``。

        Returns:
            EulerRotate: 呼び出したクラスの新しい回転(ラジアン)。``asMatrix()`` の基準軸の行が direction の向きになる。

        Raises:
            TypeError: directionが3つの数値でない場合。
            ValueError: directionが0のベクトルか有限な値でない場合、または対応していない回転順序の場合。
        """
        index = orderIndex(order)
        if isinstance(direction, (om2.MVector, om2.MPoint, om2.MFloatVector, om2.MFloatPoint)):
            direction = (direction.x, direction.y, direction.z)
        vector = _finite_vector(direction, 3, "direction")
        length = math.sqrt(sum(value * value for value in vector))
        if length == 0.0:
            raise ValueError("directionに0のベクトルは指定できません")
        name = ORDER_NAMES[index]
        base, pitch_axis, yaw_axis = ("xyz".index(letter) for letter in name)
        # 巡回する順(xyz・yzx・zxy)とそれ以外では、ピッチの軸周りに回した基準軸の向きの符号が反対になる。
        sign = 1.0 if name in ("xyz", "yzx", "zxy") else -1.0
        along, side, up = vector[base] / length, vector[pitch_axis] / length, vector[yaw_axis] / length
        values = [0.0, 0.0, 0.0]
        values[pitch_axis] = math.atan2(-sign * up, math.hypot(along, side))
        values[yaw_axis] = math.atan2(sign * side, along) if (along or side) else 0.0
        return cls(values[0], values[1], values[2], index)

    @staticmethod
    def computeAlternateSolution(*args):
        """同じ向きを表す、別のオイラー回転を計算する。

        各軸に一周を足しただけのものとは違う解を返す。
        入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 回転rotを1つ指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.computeAlternateSolution(*args))

    @staticmethod
    def computeBound(*args):
        """それぞれの角度を±πの範囲に収めた、同じ向きのオイラー回転を計算する。

        入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 回転rotを1つ指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.computeBound(*args))

    @staticmethod
    def computeClosestCut(*args):
        """それぞれの軸へ一周の整数倍を足して、基準に近い同じ向きの回転を計算する。

        入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 元の回転srcと基準targetを指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.computeClosestCut(*args))

    @staticmethod
    def computeClosestSolution(*args):
        """基準に最も近い、同じ向きのオイラー回転を計算する。

        入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 元の回転srcと基準targetを指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.computeClosestSolution(*args))

    @staticmethod
    def decompose(*args):
        """マトリクスを、指定した回転順序のオイラー回転へ分解する。

        入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: MMatrix系のmatrixと、OpenMayaの回転順序の定数orderを指定する。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.decompose(*args))

    @property
    def orderName(self):
        """回転順序の名前(``"xyz"`` など)を取得・設定する。

        設定するときは、名前(大文字と小文字は区別しない)と om2 の番号のどちらも使える。
        成分は並べ替えない。対応していない値は ValueError になる。

        Returns:
            str: 小文字の回転順序名。
        """
        return ORDER_NAMES[self.order]

    @orderName.setter
    def orderName(self, value):
        """回転順序を、名前か番号で設定する。

        Args:
            value (str | int): 回転順序。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: 対応していない回転順序の場合。
        """
        self.order = orderIndex(value)

    def asDegrees(self):
        """XYZの角度を、度に換算したtupleで取得する。

        MayaのUIの角度の単位は見ない。回転順序は変えない。
        同じ向きの別の解に直したり、決まった角度の範囲に収めたりはしない。

        Returns:
            tuple[float, float, float]: XYZの角度(度)。新しいtupleで、自身は変わらない。
        """
        return (math.degrees(self.x), math.degrees(self.y), math.degrees(self.z))

    def asQuaternion(self):
        """オイラー角と回転順序から、新しいQuaternionを作る。

        自身は変えない。Quaternionが表すのは回転の向きだけ。元のオイラー角が何周回っているかや、
        回転順序の番号、利用者がPythonで加えた状態は残らない。

        Returns:
            Quaternion: 新しい単位Quaternion。
        """
        return Quaternion._wrap(self)

    def mirror(self, axis="x"):
        """向きをビヘイビアミラーしたコピーを返す。

        ミラーの決まりはMatrixと同じ。

        Args:
            axis (str | int): 反転する軸 ``"x"``・``"y"``・``"z"``、ミラーの面 ``"YZ"``・``"XZ"``・``"XY"``
                (x⇔YZ、y⇔XZ、z⇔XY。文字の順番や大文字・小文字は問わない)、または0/1/2。

        Returns:
            EulerRotate: 同じ型の新しい回転。回転順序はそのまま保つ。

        Raises:
            TypeError: axisが文字列でもintでもない場合。
            ValueError: axisが正しくない場合。
        """
        matrix = self.asMatrix().mirror(axis)
        rotation = matrix.quaternion.asEulerRotate()
        rotation.reorderIt(self.order)
        return type(self)._wrap(rotation)

    def mirrorIt(self, axis="x"):
        """自身の向きをビヘイビアミラーする。

        Args:
            axis (str | int): mirrorと同じ反転軸。

        Returns:
            EulerRotate: 更新した自身。
        """
        self.setValue(self.mirror(axis))
        return self

    def round(self, ndigits=None, *, unit="deg"):
        """XYZの角度を丸めたコピーを返す。

        unitの単位で、小数点以下ndigits桁に丸める。
        既定では度に換算して丸め、ラジアンに戻して持つ(``89.99999`` 度は ``90`` 度になる)。
        中の値はラジアンなので、丸めた後の :meth:`asDegrees` には、浮動小数点のわずかな誤差が残ることがある。

        - それぞれの成分に組み込みの ``round`` を使う(端数がちょうど半分なら偶数の側)。-0.0 は 0.0 にそろえる。
        - 回転順序はそのまま。同じ向きの別の解に直したり、角度の範囲に収めたりはしない。
        - 組み込みの ``round(value, ndigits)`` は度で丸める。

        Args:
            ndigits (int | None): 小数点以下の桁数。負の値なら整数の部分を丸める。Noneなら整数に丸める。
            unit (str): 丸める単位。既定は ``"deg"`` で度、``"rad"`` ならラジアン
                (``"degree"`` / ``"radians"`` などの別名も使える)。

        Returns:
            EulerRotate: 同じ型の新しい回転。

        Raises:
            TypeError: ndigitsがintでもNoneでもない場合(boolも不可)、またはunitが文字列でもNoneでもない場合。
            ValueError: unitが対応していない単位の場合。
        """
        ndigits = _checked_digits(ndigits)
        unit = _angle_unit(unit)
        values = [_to_radians(_round_float(_from_radians(value, unit), ndigits), unit) for value in self]
        return type(self)(values[0], values[1], values[2], self.order)

    def roundIt(self, ndigits=None, *, unit="deg"):
        """自身のXYZの角度を丸める。

        Args:
            ndigits (int | None): roundと同じ桁数。
            unit (str): roundと同じ丸める単位。

        Returns:
            EulerRotate: 更新した自身。

        Raises:
            TypeError: ndigitsがintでもNoneでもない場合(boolも不可)、またはunitが文字列でもNoneでもない場合。
                自身は変えない。
            ValueError: unitが対応していない単位の場合。自身は変えない。
        """
        self.setValue(self.round(ndigits, unit=unit))
        return self

    def asMatrix(self):
        """回転順序に合わせた回転マトリクスを返す。

        Returns:
            Matrix: 回転だけを持つ4行4列のマトリクス。
        """
        # 循環参照の回避: 同じパッケージの中でお互いに参照するので、使うときに読み込む。
        from .matrix import Matrix

        return Matrix._wrap(_MEuler.asMatrix(self))

    def isEquivalent(self, other, tolerance=1e-10):
        """許容誤差の範囲で、ほぼ等しいかを判定する。

        om2 の ``isEquivalent`` で判定する。回転順序が同じで、それぞれの成分の差が
        tolerance 以内のときだけ True になる。

        Args:
            other (om2.MEulerRotation | Iterable[float]): 比べる相手。並びは、回転順序がxyzの
                ラジアンとして扱う。
            tolerance (float): それぞれの成分の許容誤差。

        Returns:
            bool: ほぼ等しければ True。
        """
        if not isinstance(other, _MEuler):
            other = EulerRotate(other)
        return _MEuler.isEquivalent(self, other, tolerance)

    def alternateSolution(self, *args):
        """同じ向き・同じ回転順序の、別の解のオイラー回転を返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: OpenMayaの同じ名前のメソッドへ渡す位置引数。ふつうは指定しない。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.alternateSolution(self, *args))

    def bound(self, *args):
        """それぞれの角度を±πの範囲に収めた、同じ向きの回転のコピーを返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: OpenMayaの同じ名前のメソッドへ渡す位置引数。ふつうは指定しない。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.bound(self, *args))

    def closestCut(self, *args):
        """それぞれの軸へ一周の整数倍を足して、基準に近い同じ向きの回転を返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 基準にする回転targetを指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.closestCut(self, *args))

    def closestSolution(self, *args):
        """基準に最も近い、同じ向きのオイラー回転を返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 基準にする回転targetを指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.closestSolution(self, *args))

    def inverse(self, *args):
        """逆の回転を表す、新しいオイラー回転を返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: OpenMayaの同じ名前のメソッドへ渡す位置引数。ふつうは指定しない。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.inverse(self, *args))

    def reorder(self, *args):
        """指定した回転順序で同じ向きを表す、新しい回転を返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: OpenMayaの回転順序の定数orderを指定する。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        return EulerRotate._wrap(_MEuler.reorder(self, *args))

    def asVector(self, *args):
        """XYZの角度の成分を、radのVectorとして返す。回転順序は含まない。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: OpenMayaの同じ名前のメソッドへ渡す位置引数。ふつうは指定しない。

        Returns:
            Vector: 計算した結果の、新しいmlibの値。
        """
        # 循環参照の回避: 同じパッケージの中でお互いに参照するので、使うときに読み込む。
        from .vector import Vector

        return Vector(_MEuler.asVector(self, *args))

    def isGimbalLocked(self, tolerance=1e-10):
        """ジンバルロックの姿勢かを判定する。

        中間の軸(回転順序の2文字目)の角度が ±90 度に近いと、ジンバルロックになる。
        このとき、最初の軸と最後の軸の回転が同じ向きの回転になり、軸1つ分の自由度がなくなる。

        Args:
            tolerance (float): ±90 度からの差の許容誤差(ラジアン)。0以上。

        Returns:
            bool: 中間の軸の角度を -180〜180 度に収め、その絶対値と 90 度の差が tolerance 以下ならTrue。

        Raises:
            TypeError: toleranceが数値でない場合。
            ValueError: toleranceが負の場合、または有限な値でない場合。
        """
        limit = _checked_tolerance(tolerance)
        middle = "xyz".index(ORDER_NAMES[self.order][1])
        angle = math.remainder(self[middle], 2.0 * math.pi)
        return abs(abs(angle) - math.pi / 2.0) <= limit

    def reverseDirection(self):
        """同じ姿勢へ、逆回りでたどり着く回転を返す。

        絶対値がいちばん大きい成分(同じなら x・y・z の順で先のもの)へ、符号と反対の向きに360度を足す
        (``asQuaternion()`` の符号が反対になる。マトリクスは変わらない)。
        オイラーのフィルターや、補間で回る向きを調整するときに使う。

        Returns:
            EulerRotate: 同じ型・同じ回転順序の、新しい回転。
        """
        values = list(self)
        index = max(range(3), key=lambda number: abs(values[number]))
        values[index] += -2.0 * math.pi if values[index] >= 0.0 else 2.0 * math.pi
        return type(self)(values[0], values[1], values[2], self.order)

    def reverseDirectionIt(self):
        """自身を、同じ姿勢へ逆回りでたどり着く回転(:meth:`reverseDirection`)に置き換える。

        Returns:
            EulerRotate: 更新した自身。
        """
        self.setValue(self.reverseDirection())
        return self

    @classmethod
    def _wrap(cls, value):
        """om2 の値をコピーした、cls のインスタンスを返す。

        Python の ``__new__`` / ``__init__`` を通さず(利用者の派生クラスの ``__init__`` も
        呼ばない)、基底クラスの ``__init__`` で C++ の実体を用意する。

        Args:
            value (om2.MEulerRotation | om2.MQuaternion | om2.MMatrix): コピー元。
                ``setValue`` が受け付ける値。MEulerRotation なら回転順序もコピーする。

        Returns:
            EulerRotate: cls の新しいインスタンス。
        """
        result = _NEW(cls)
        _INIT(result)
        result.setValue(value)
        return result


# reloadしたときにも、廃止した公開名を残さない。
for _obsolete_name in ("order_index",):
    globals().pop(_obsolete_name, None)
