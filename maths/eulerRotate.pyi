# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""オイラー回転の値。om2.MEulerRotation を継承し、ラジアンの角度と回転順序を持つ。"""

import math
import operator
import maya.api.OpenMaya as om2
from ..util import _angle_unit, _checked_digits, _checked_index, _checked_tolerance, _copy_state, _finite_vector, _foreign_comparison, _from_radians, _rethrow_init_error, _round_float, _to_radians
from .quaternion import Quaternion
from .vector import _reduce_value
from typing import Any, Iterable, Iterator
from mlib.maths.matrix import Matrix
from mlib.maths.vector import Vector
from typing_extensions import Self
import types

_MEuler: Any
_MQuaternion: Any
_NEW: Any
_INIT: Any
_GET: Any
_SET: Any
_NUMBER: tuple
ORDER_NAMES: tuple
_ORDER_INDEX: dict

def orderIndex(order: str | int) -> int:
    """回転順序の名前か番号を、om2 の番号(0〜5)へ変換する。

    Args:
        order (str | int): ``"xyz"`` などの名前(大文字と小文字は区別しない)、または
            om2 の ``MEulerRotation.kXYZ``〜``kZYX`` (Maya の rotateOrder と同じ番号)。

    Returns:
        int: om2 の回転順序の番号。

    Raises:
        ValueError: 対応していない名前・番号の場合、または bool などの正しくない型の場合。
    """
    ...

def _euler_keywords(x: float = ..., y: float = ..., z: float = ..., order: str | int | None = ...) -> tuple:
    """キーワード引数で渡された EulerRotate の引数を、(x, y, z, order) にまとめる。

    Args:
        x (float): X 回転(ラジアン)。
        y (float): Y 回転(ラジアン)。
        z (float): Z 回転(ラジアン)。
        order (str | int | None): 回転順序。None は xyz。

    Returns:
        tuple: (x, y, z, order)。
    """
    ...


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
    __slots__: tuple
    __hash__: None
    def __new__(cls, *args, **kwargs) -> Self:
        """回転が0(xyzの順)のclsのインスタンスを作る。

        基底クラスの初期化で、C++の実体を先に用意しておく。こうすると、``__init__`` を通らなかったり
        失敗したりしても、実体へアクセスできる。詳しくは :meth:`mlib.maths.vector.Vector.__new__` を参照。

        Args:
            *args: ここでは使わない、作るときの引数。
            **kwargs: ここでは使わないキーワード引数。

        Returns:
            EulerRotate: 回転が0のclsのインスタンス。
        """
        ...
    def __init__(self, *args, **kwargs) -> None:
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
        ...
    def __getitem__(self, index: int | slice) -> float | tuple[float, ...]:
        """回転成分を取得する。

        Args:
            index (int | slice): -3〜2 の番号(X、Y、Z の順)、またはスライス。

        Returns:
            float | tuple[float, ...]: 指定した成分(ラジアン)。スライスでは成分の tuple。

        Raises:
            TypeError: 番号が整数でもスライスでもない場合。
            IndexError: 番号が範囲の外の場合。
        """
        ...
    def __setitem__(self, index: int, value: float) -> None:
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
        ...
    def __iter__(self) -> Iterator[float]:
        """X、Y、Z の順に、回転の成分を1つずつ返す。

        Returns:
            Iterator[float]: 3成分(ラジアン)のイテレータ。
        """
        ...
    def __reduce__(self) -> tuple:
        """copy・pickleのために、コンストラクタを通さずに作り直す情報を返す。

        Returns:
            tuple: ``(_rebuild, (type(self), (x, y, z, order))[, state])``。
            利用者の派生クラスの ``__init__`` は呼ばない。``__dict__`` と ``__slots__`` の
            アトリビュートは、作り直すときに元に戻す。
        """
        ...
    def __reduce_ex__(self, protocol: int) -> tuple:
        """pickle のプロトコルに関係なく、__reduce__ と同じ情報を返す。

        Args:
            protocol (int): pickle のプロトコル番号。使わない。

        Returns:
            tuple: ``__reduce__()`` の結果。
        """
        ...
    def __copy__(self) -> EulerRotate:
        """同じ型で、成分と回転順序が同じコピーを返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートも、浅くコピーする。

        Returns:
            EulerRotate: 自身と同じクラスの新しいインスタンス。
        """
        ...
    def __deepcopy__(self, memo: dict) -> EulerRotate:
        """同じ型で、成分と回転順序が同じコピーを返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートは、深くコピーする。

        Args:
            memo (dict): copy.deepcopy の memo。

        Returns:
            EulerRotate: 自身と同じクラスの新しいインスタンス。
        """
        ...
    def __repr__(self) -> str:
        """デバッグ用の表記を返す。回転の成分(度)と回転順序の名前を含む。

        Returns:
            str: ``EulerRotate(degrees=(90, 0, -45), order='xyz')`` の形の文字列。
            中の値はラジアンのまま。
        """
        ...
    __str__: Any
    def __eq__(self, other: object) -> bool | types.NotImplementedType:
        """MEulerRotation 系の値と比べる。

        om2 と同じく、回転順序も含めて完全に一致するかを調べる。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | types.NotImplementedType: MEulerRotation 系なら om2 で比べた結果。
            ほかの om2 の型なら False。それ以外の型なら NotImplemented(相手の比較に任せ、
            どちらも決めなければ False になる)。
        """
        ...
    def __ne__(self, other: object) -> bool | types.NotImplementedType:
        """``__eq__`` の否定を返す。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | types.NotImplementedType: MEulerRotation 系なら om2 で比べた結果。
            ほかの om2 の型なら True。それ以外の型なら NotImplemented。
        """
        ...
    def __add__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """om2 の ``+`` の結果を EulerRotate で返す。

        Args:
            other (object): MEulerRotation 系。回転順序が違えば、自身の回転順序へ変換してから足す。

        Returns:
            EulerRotate | types.NotImplementedType: 和。対応しない型は NotImplemented。
        """
        ...
    def __radd__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """左辺の MEulerRotation 系との和を返す。

        Args:
            other (object): MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 和。対応しない型は NotImplemented。
        """
        ...
    def __iadd__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """MEulerRotation 系の値を自身へ足す。

        Args:
            other (object): MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        ...
    def __sub__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """om2 の ``-`` の結果を EulerRotate で返す。

        Args:
            other (object): MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 差。対応しない型は NotImplemented。
        """
        ...
    def __rsub__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """左辺の MEulerRotation 系から自身を引いた値を返す。

        Args:
            other (object): MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 差。対応しない型は NotImplemented。
        """
        ...
    def __isub__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """MEulerRotation 系の値を自身から引く。

        Args:
            other (object): MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        ...
    def __mul__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """om2 の ``*`` の結果を EulerRotate で返す。

        Args:
            other (object): 数値(成分を拡大縮小する)、または MEulerRotation 系 /
                MQuaternion 系(自身を先に回す、回転の合成)。

        Returns:
            EulerRotate | types.NotImplementedType: 結果。対応しない型は NotImplemented。
        """
        ...
    def __rmul__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """左から掛ける。計算の意味は om2 と同じ。

        Args:
            other (object): 数値、または左辺の MEulerRotation 系。

        Returns:
            EulerRotate | types.NotImplementedType: 結果。対応しない型は NotImplemented。
        """
        ...
    def __imul__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """自身を数値倍する、または自身に回転を合成する。

        Args:
            other (object): 数値、MEulerRotation 系、または MQuaternion 系。

        Returns:
            EulerRotate | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        ...
    def __truediv__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """成分ごとに数値で割った値を返す(om2 には無く、mlib で加えたもの)。

        回転順序はそのままで、それぞれの成分を other で割る。

        Args:
            other (object): 割る数。int か float。

        Returns:
            EulerRotate | types.NotImplementedType: 新しい回転。対応しない型は NotImplemented。

        Raises:
            ZeroDivisionError: other が 0 の場合。
        """
        ...
    def __itruediv__(self, other: object) -> EulerRotate | types.NotImplementedType:
        """自身のそれぞれの成分を数値で割る(mlib で加えたもの。回転順序は変えない)。

        Args:
            other (object): 割る数。int か float。

        Returns:
            EulerRotate | types.NotImplementedType: 自身。対応しない型は NotImplemented。

        Raises:
            ZeroDivisionError: other が 0 の場合。
        """
        ...
    def __neg__(self) -> EulerRotate:
        """om2 の単項 ``-`` (成分の符号を反対にした回転)を EulerRotate で返す。

        Returns:
            EulerRotate: 新しい回転。
        """
        ...
    def __round__(self, ndigits: int | None = ...) -> EulerRotate:
        """組み込みの ``round`` から呼ばれ、度で丸める :meth:`round` を呼ぶ。

        Args:
            ndigits (int | None): roundと同じ桁数。

        Returns:
            EulerRotate: 同じ型の新しい回転。
        """
        ...
    @classmethod
    def fromIterable(cls, values: Iterable[float], order: str | int = ...) -> EulerRotate:
        """3つの値の並びから作る。

        Args:
            values (Iterable[float]): ラジアンの3つの成分。
            order (str | int): 回転順序。既定は ``"xyz"``。

        Returns:
            EulerRotate: 呼び出したクラスの新しいインスタンス。

        Raises:
            ValueError: 要素の数が3でない場合、または対応していない回転順序の場合。
        """
        ...
    @classmethod
    def fromDegrees(cls, x: float, y: float, z: float, order: str | int = ...) -> EulerRotate:
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
        ...
    @classmethod
    def fromYawPitch(cls, direction: om2.MVector | om2.MPoint | Iterable[float], order: str | int = ...) -> EulerRotate:
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
        ...
    @staticmethod
    def computeAlternateSolution(*args) -> EulerRotate:
        """同じ向きを表す、別のオイラー回転を計算する。

        各軸に一周を足しただけのものとは違う解を返す。
        入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 回転rotを1つ指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    @staticmethod
    def computeBound(*args) -> EulerRotate:
        """それぞれの角度を±πの範囲に収めた、同じ向きのオイラー回転を計算する。

        入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 回転rotを1つ指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    @staticmethod
    def computeClosestCut(*args) -> EulerRotate:
        """それぞれの軸へ一周の整数倍を足して、基準に近い同じ向きの回転を計算する。

        入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 元の回転srcと基準targetを指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    @staticmethod
    def computeClosestSolution(*args) -> EulerRotate:
        """基準に最も近い、同じ向きのオイラー回転を計算する。

        入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 元の回転srcと基準targetを指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    @staticmethod
    def decompose(*args) -> EulerRotate:
        """マトリクスを、指定した回転順序のオイラー回転へ分解する。

        入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: MMatrix系のmatrixと、OpenMayaの回転順序の定数orderを指定する。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    @property
    def orderName(self) -> str:
        """回転順序の名前(``"xyz"`` など)を取得・設定する。

        設定するときは、名前(大文字と小文字は区別しない)と om2 の番号のどちらも使える。
        成分は並べ替えない。対応していない値は ValueError になる。

        Returns:
            str: 小文字の回転順序名。
        """
        ...
    @orderName.setter
    def orderName(self, value: str | int) -> None:
        """回転順序を、名前か番号で設定する。

        Args:
            value (str | int): 回転順序。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: 対応していない回転順序の場合。
        """
        ...
    def asDegrees(self) -> tuple[float, float, float]:
        """XYZの角度を、度に換算したtupleで取得する。

        MayaのUIの角度の単位は見ない。回転順序は変えない。
        同じ向きの別の解に直したり、決まった角度の範囲に収めたりはしない。

        Returns:
            tuple[float, float, float]: XYZの角度(度)。新しいtupleで、自身は変わらない。
        """
        ...
    def asQuaternion(self) -> Quaternion:
        """オイラー角と回転順序から、新しいQuaternionを作る。

        自身は変えない。Quaternionが表すのは回転の向きだけ。元のオイラー角が何周回っているかや、
        回転順序の番号、利用者がPythonで加えた状態は残らない。

        Returns:
            Quaternion: 新しい単位Quaternion。
        """
        ...
    def mirror(self, axis: str | int = ...) -> EulerRotate:
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
        ...
    def mirrorIt(self, axis: str | int = ...) -> EulerRotate:
        """自身の向きをビヘイビアミラーする。

        Args:
            axis (str | int): mirrorと同じ反転軸。

        Returns:
            EulerRotate: 更新した自身。
        """
        ...
    def round(self, ndigits: int | None = ..., *, unit: str = ...) -> EulerRotate:
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
        ...
    def roundIt(self, ndigits: int | None = ..., *, unit: str = ...) -> EulerRotate:
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
        ...
    def asMatrix(self) -> Matrix:
        """回転順序に合わせた回転マトリクスを返す。

        Returns:
            Matrix: 回転だけを持つ4行4列のマトリクス。
        """
        ...
    def isEquivalent(self, other: om2.MEulerRotation | Iterable[float], tolerance: float = ...) -> bool:
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
        ...
    def alternateSolution(self, *args) -> EulerRotate:
        """同じ向き・同じ回転順序の、別の解のオイラー回転を返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: OpenMayaの同じ名前のメソッドへ渡す位置引数。ふつうは指定しない。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    def bound(self, *args) -> EulerRotate:
        """それぞれの角度を±πの範囲に収めた、同じ向きの回転のコピーを返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: OpenMayaの同じ名前のメソッドへ渡す位置引数。ふつうは指定しない。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    def closestCut(self, *args) -> EulerRotate:
        """それぞれの軸へ一周の整数倍を足して、基準に近い同じ向きの回転を返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 基準にする回転targetを指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    def closestSolution(self, *args) -> EulerRotate:
        """基準に最も近い、同じ向きのオイラー回転を返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: 基準にする回転targetを指定する。角度はrad。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    def inverse(self, *args) -> EulerRotate:
        """逆の回転を表す、新しいオイラー回転を返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: OpenMayaの同じ名前のメソッドへ渡す位置引数。ふつうは指定しない。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    def reorder(self, *args) -> EulerRotate:
        """指定した回転順序で同じ向きを表す、新しい回転を返す。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: OpenMayaの回転順序の定数orderを指定する。

        Returns:
            EulerRotate: 計算した結果の、新しいmlibの値。
        """
        ...
    def asVector(self, *args) -> Vector:
        """XYZの角度の成分を、radのVectorとして返す。回転順序は含まない。

        自身と入力の値は変えない。引数や、0の値の扱いはOpenMayaと同じ。

        Args:
            *args: OpenMayaの同じ名前のメソッドへ渡す位置引数。ふつうは指定しない。

        Returns:
            Vector: 計算した結果の、新しいmlibの値。
        """
        ...
    def isGimbalLocked(self, tolerance: float = ...) -> bool:
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
        ...
    def reverseDirection(self) -> EulerRotate:
        """同じ姿勢へ、逆回りでたどり着く回転を返す。

        絶対値がいちばん大きい成分(同じなら x・y・z の順で先のもの)へ、符号と反対の向きに360度を足す
        (``asQuaternion()`` の符号が反対になる。マトリクスは変わらない)。
        オイラーのフィルターや、補間で回る向きを調整するときに使う。

        Returns:
            EulerRotate: 同じ型・同じ回転順序の、新しい回転。
        """
        ...
    def reverseDirectionIt(self) -> EulerRotate:
        """自身を、同じ姿勢へ逆回りでたどり着く回転(:meth:`reverseDirection`)に置き換える。

        Returns:
            EulerRotate: 更新した自身。
        """
        ...
    @classmethod
    def _wrap(cls, value: om2.MEulerRotation | om2.MQuaternion | om2.MMatrix) -> EulerRotate:
        """om2 の値をコピーした、cls のインスタンスを返す。

        Python の ``__new__`` / ``__init__`` を通さず(利用者の派生クラスの ``__init__`` も
        呼ばない)、基底クラスの ``__init__`` で C++ の実体を用意する。

        Args:
            value (om2.MEulerRotation | om2.MQuaternion | om2.MMatrix): コピー元。
                ``setValue`` が受け付ける値。MEulerRotation なら回転順序もコピーする。

        Returns:
            EulerRotate: cls の新しいインスタンス。
        """
        ...
    x: Any
    y: Any
    z: Any
    order: Any
