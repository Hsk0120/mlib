"""om2.MVector を継承した3成分ベクトルと基本演算。"""

import math
from typing import Any, Sequence

import maya.api.OpenMaya as om2

from ..util import (
    _checked_digits,
    _checked_index,
    _checked_tolerance,
    _copy_state,
    _finite,
    _foreign_comparison,
    _instance_state,
    _rethrow_init_error,
    _round_float,
)

_MVector = om2.MVector
_MPoint = om2.MPoint
_MMatrix = om2.MMatrix
_MQuaternion = om2.MQuaternion
_MEuler = om2.MEulerRotation
_NEW = _MVector.__new__
_INIT = _MVector.__init__
_GET = _MVector.__getitem__
_SET = _MVector.__setitem__
#: スカラーとして扱う数値型。bool は int の派生として含まれる(om2 と同じ)。
_NUMBER = (int, float)
#: MVector のコンストラクタへそのまま渡せる om2 の3成分型。
_OM2_POINT_TYPES = (_MPoint, om2.MFloatVector, om2.MFloatPoint)
#: 軸の名前(小文字)から (成分の番号, 向き) への表。
_AXIS_NAMES = {"x": (0, 1.0), "+x": (0, 1.0), "-x": (0, -1.0), "y": (1, 1.0), "+y": (1, 1.0), "-y": (1, -1.0), "z": (2, 1.0), "+z": (2, 1.0), "-z": (2, -1.0)}


def _resolve_mvector(value):
    """値を om2.MVector として扱える形へ変換する。

    MVector 系(mlib の Vector 派生を含む)はそのまま返す。MPoint などの om2 の
    3成分型は MVector へ変換し(MPoint の w では割らない)、それ以外は
    3要素の反復可能オブジェクトとして展開する。

    Args:
        value (om2.MVector | om2.MPoint | Iterable[float]): 変換元。

    Returns:
        om2.MVector: value 自身、または新しい MVector。

    Raises:
        TypeError: 反復できない値の場合。
        ValueError: 反復可能オブジェクトの要素数が3でない場合。
    """
    if isinstance(value, _MVector):
        return value
    if isinstance(value, _OM2_POINT_TYPES):
        return _MVector(value)
    x, y, z = value
    result = _MVector()
    result.x = x
    result.y = y
    result.z = z
    return result


def _vector_operand(value):
    """加減算・比較の相手を om2.MVector として扱える形へそろえる。

    MVector 系はそのまま返し、3個の数値(int/float。boolを除く)を持つ tuple/list は新しい
    MVector へ変換する。MPoint などそれ以外の型は対応しないため None を返す。

    Args:
        value (object): 演算・比較の相手。

    Returns:
        om2.MVector | None: 相手の値。対応しない型は None。
    """
    if isinstance(value, _MVector):
        return value
    if type(value) in (tuple, list) and len(value) == 3:
        x, y, z = value
        if (
            isinstance(x, _NUMBER)
            and isinstance(y, _NUMBER)
            and isinstance(z, _NUMBER)
            and not isinstance(x, bool)
            and not isinstance(y, bool)
            and not isinstance(z, bool)
        ):
            result = _MVector()
            result.x = x
            result.y = y
            result.z = z
            return result
    return None


def _zero(cls):
    """Python の ``__new__`` / ``__init__`` を通さずに cls のゼロベクトルを作る。

    om2 の型は C++ の実体を基底の ``__init__`` で確保するため、``__new__`` の直後に
    必ず基底の ``__init__`` を呼ぶ。演算結果の生成など内部の高速な経路で使う。

    Args:
        cls (type): 生成する Vector 系のクラス。

    Returns:
        Vector: cls のゼロベクトル。
    """
    result = _NEW(cls)
    _INIT(result)
    return result


def _vector_of(cls, value):
    """om2 の MVector または3要素の列から cls のインスタンスを作る。

    引数付きコンストラクタは om2 の多重定義の解決が遅いため、引数なしで確保した
    インスタンスへ成分を代入する。

    Args:
        cls (type): 生成する Vector 系のクラス。
        value (om2.MVector | Sequence[float]): 値の取得元。

    Returns:
        Vector: cls の新しいインスタンス。
    """
    result = _NEW(cls)
    _INIT(result)
    if isinstance(value, _MVector):
        result.x = value.x
        result.y = value.y
        result.z = value.z
    else:
        result.x = value[0]
        result.y = value[1]
        result.z = value[2]
    return result


def _vectors_of_points(points):
    """om2 の MPoint の列から、XYZを写した Vector のリストを作る。

    MPoint の w では割らない。引数付きコンストラクタの多重定義の解決を通さず、
    引数なしで確保したインスタンスへ成分を代入する(:func:`_vector_of` と同じ理由)。

    Args:
        points (Iterable[om2.MPoint]): 変換元の点列(MPointArray など)。

    Returns:
        list[Vector]: 入力順の新しい Vector。
    """
    result = []
    append = result.append
    for point in points:
        vector = _NEW(Vector)
        _INIT(vector)
        vector.x = point.x
        vector.y = point.y
        vector.z = point.z
        append(vector)
    return result


def _vector_keywords(x=0.0, y=0.0, z=0.0):
    """キーワード引数付きの Vector の生成引数を (x, y, z) へまとめる。

    Args:
        x (float): X 成分。
        y (float): Y 成分。
        z (float): Z 成分。

    Returns:
        tuple: (x, y, z)。
    """
    return x, y, z


def _rebuild(cls, values):
    """copy / pickle の再構築関数。cls の ``__init__`` を呼ばずに値を復元する。

    om2 の型は C++ の実体を基底の ``__init__`` で確保するため、基底の ``__new__`` と
    ``__init__`` で確保してから成分を設定する。利用者の派生クラスが独自の引数の
    ``__init__`` を持っていても呼ばない。追加のアトリビュート(``__dict__`` / ``__slots__``)は
    pickle の標準の手順(``__reduce__`` の3番目の要素)で後から復元される。

    Args:
        cls (type): 復元するクラス。om2.MVector / MQuaternion / MEulerRotation /
            MMatrix のいずれかの派生。
        values (tuple): 成分。MVector 系は (x, y, z)、MQuaternion 系は (x, y, z, w)、
            MEulerRotation 系は (x, y, z, order)、MMatrix 系は行優先の16要素。

    Returns:
        object: 復元した cls のインスタンス。

    Raises:
        TypeError: cls が対応する om2 の型の派生でない場合。
        ValueError: values の要素数が型と合わない場合。
    """
    if issubclass(cls, _MVector):
        result = _NEW(cls)
        _INIT(result)
        result.x, result.y, result.z = values
    elif issubclass(cls, _MQuaternion):
        result = _MQuaternion.__new__(cls)
        _MQuaternion.__init__(result)
        result.x, result.y, result.z, result.w = values
    elif issubclass(cls, _MEuler):
        result = _MEuler.__new__(cls)
        _MEuler.__init__(result)
        result.x, result.y, result.z, result.order = values
    elif issubclass(cls, _MMatrix):
        values = tuple(values)
        if len(values) != 16:
            raise ValueError("Matrixには16個の値を指定してください")
        result = _MMatrix.__new__(cls)
        _MMatrix.__init__(result)
        for position, item in enumerate(values):
            _MMatrix.__setitem__(result, position, item)
    else:
        raise TypeError(f"{cls.__name__}を再構築できません")
    return result


def _reduce_value(value, values):
    """copy / pickle 用に、:func:`_rebuild` で再構築する情報を返す。

    利用者の派生クラスが持つ追加のアトリビュートは、pickle の標準形式の state(``__dict__`` の
    辞書、``__slots__`` もあれば ``(辞書, slots の辞書)``)として3番目の要素に置く。
    インスタンスの生成後に設定されるため、自身を参照するアトリビュートも復元できる。

    Args:
        value (object): 複製・保存する mlib の値。
        values (tuple): :func:`_rebuild` へ渡す成分。

    Returns:
        tuple: ``(_rebuild, (type(value), values))``、または state を加えた3要素の tuple。
    """
    state, slots = _instance_state(value)
    if slots:
        return (_rebuild, (type(value), values), (state, slots))
    if state:
        return (_rebuild, (type(value), values), state)
    return (_rebuild, (type(value), values))


def _iterable(value, name):
    """点列の引数を list へ変換する。

    Args:
        value (Iterable): 点列。文字列・単独のベクトルは点列として受け付けない。
        name (str): 例外メッセージに使う引数名。

    Returns:
        list: 点のリスト。

    Raises:
        TypeError: 反復できない値、文字列、または単独のom2ベクトル・点の場合。
    """
    if isinstance(value, (str, bytes, _MVector, _MPoint)):
        raise TypeError(f"{name}は点の並びで指定してください")
    try:
        return list(value)
    except TypeError:
        raise TypeError(f"{name}は点の並びで指定してください") from None


def _axis_name(axis, name):
    """軸の名前を (成分の番号, 向き) へ変換する。

    Args:
        axis (str): ``"x"``・``"-y"``・``"+Z"`` などの軸の名前。大文字小文字は問わない。
        name (str): 例外メッセージに使う引数名。

    Returns:
        tuple[int, float]: 成分の番号(0〜2)と向き(1.0 または -1.0)。

    Raises:
        TypeError: axisが文字列でない場合。
        ValueError: axisが軸の名前でない場合。
    """
    if not isinstance(axis, str):
        raise TypeError(f"{name}は'x'や'-y'のようなstrで指定してください")
    result = _AXIS_NAMES.get(axis.lower())
    if result is None:
        raise ValueError(f"{name}は'x'・'y'・'z'・'-x'・'-y'・'-z'のどれかで指定してください: {axis!r}")
    return result


class Vector(om2.MVector):
    """om2.MVectorを継承した、XYZのベクトル。

    値は後から書き換えられ、ハッシュはできない(dictのキーやsetの要素にできない)。
    OpenMayaのAPIへそのまま渡せる。作り方は ``__init__`` を参照する。作るときは成分をコピーする。
    MPointから作るときも、wで割らずにXYZをそのまま写す。

    演算はOpenMayaに従う。結果がベクトルになる演算は、派生クラスでも基底のVectorを返す。
    左辺が ``om2.MVector`` の ``+`` / ``-`` / ``^`` もVectorになる。

    * ``+`` / ``-`` は成分ごとの足し算・引き算。相手はMVector系か、3個の数値のtuple/list
      (``v + (1, 1, 1)``・``(1, 1, 1) + v``・``v - [0, 1, 0]``)。結果はVectorになる。
    * ``v * 数値`` / ``数値 * v`` / ``v / 数値`` は数値倍と割り算。0で割るとZeroDivisionErrorになる。
    * ``v * w`` は内積(float)、``v ^ w`` は外積。
    * ``v * m`` は行ベクトルとしての方向の変換で、平行移動を含まない。
      ``m * v`` は列ベクトルの積(``v * mᵀ``)。

    ``+=`` / ``-=`` / ``*=`` / ``/=`` / ``^=`` は自身を書き換え、派生クラスの型を保つ。
    ただし ``v *= w`` は内積なので、変数はfloatに置き換わる。
    新しい値を返す操作と、自身を書き換える操作は区別している。
    継承したメソッドのうち数学値を返すものも、対応するmlibの型を返す。OpenMayaのクラスが共有する定数は変更しない。

    成分と番号へ代入できる。番号は-3〜2で、範囲外はIndexErrorになる。
    スライスでは代入できないtupleを返し、反復はXYZの順になる。

    ``==`` は、MVector系か3個の数値のtuple/listと、成分が完全に一致するかを比べる。派生クラスの型が違っても等しくなることがある。
    MPointなど、それ以外のOpenMayaの型との比較はFalseになる。そのほかの型は相手の比較に任せ、どちらも判断しなければFalseになる。
    左辺がOpenMayaの型の比較は、OpenMaya側でTypeErrorになることがある。
    """

    __slots__ = ()
    __hash__ = None

    def __new__(cls, *args, **kwargs):
        """基底クラスの初期化でC++の実体を確保し、clsのゼロベクトルを作る。

        派生クラスが ``__init__`` を呼ばなかったり、途中で失敗したりしても、確保していない実体へ
        触れないように、ここで確保しておく。mlibの ``__init__`` は成分を設定するだけにしている。
        Maya 2022では、基底クラスの初期化をもう一度呼ぶと、そのたびに実体がメモリに残ったままになる(リーク)。

        Args:
            *args: ここでは使わない生成引数。
            **kwargs: ここでは使わないキーワード引数。

        Returns:
            Vector: clsのゼロベクトル。
        """
        self = _NEW(cls)
        _INIT(self)
        return self

    def __init__(self, *args, **kwargs):
        """成分を設定する。

        Args:
            *args: ``()``、``(x, y, z)``、``(x, y)``、``(values)``、または
                ``(MVector | MPoint | MFloatVector | MFloatPoint)`` など om2 の
                MVector のコンストラクタが受け付ける引数。
            **kwargs: ``x``、``y``、``z``。位置引数と合わせて使える。省略した成分は 0。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 未知のキーワード引数、または同じ成分を二重に指定した場合。
            ValueError: om2 のコンストラクタが受け付けない引数(文字列の成分など)の場合。
        """
        if kwargs:
            try:
                args = _vector_keywords(*args, **kwargs)
            except TypeError as error:
                _rethrow_init_error(type(self), error)
        count = len(args)
        # 成分の形はom2のコンストラクタと同じく実行時に判定するため、任意の値として扱う。
        values: Sequence[Any] = args
        if count == 1:
            source: Any = args[0]
            if isinstance(source, _MVector):
                self.x = source.x
                self.y = source.y
                self.z = source.z
                return
            if type(source) in (tuple, list) and len(source) == 3:
                values = source
        elif count == 0:
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            return
        if len(values) == 3:
            x, y, z = values
            if isinstance(x, _NUMBER) and isinstance(y, _NUMBER) and isinstance(z, _NUMBER):
                self.x = x
                self.y = y
                self.z = z
                return
        # その他の形(MPoint など)は om2 の多重定義の解決に任せる(不正な引数も om2 と同じ ValueError)。
        source = _MVector(*args)
        self.x = source.x
        self.y = source.y
        self.z = source.z

    def __getitem__(self, index):
        """成分を取得する。

        Args:
            index (int | slice): -3〜2 の番号、またはスライス。

        Returns:
            float | tuple[float, ...]: 指定成分。スライスでは成分の tuple。

        Raises:
            TypeError: 番号が整数・スライス以外の場合。
            IndexError: 番号が範囲外の場合。
        """
        if index.__class__ is int and -3 <= index < 3:
            return _GET(self, index)
        if isinstance(index, slice):
            return (self.x, self.y, self.z)[index]
        return _GET(self, _checked_index(index, 3, "Vector"))

    def __setitem__(self, index, value):
        """成分を設定する。

        Args:
            index (int): -3〜2 の番号。
            value (float): 設定する値。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 番号が整数以外の場合。
            IndexError: 番号が範囲外の場合。
        """
        if index.__class__ is not int or not -3 <= index < 3:
            index = _checked_index(index, 3, "Vector")
        _SET(self, index, value)

    def __iter__(self):
        """X、Y、Z の順に成分を反復する。

        Returns:
            Iterator[float]: 3成分のイテレータ。
        """
        return iter((self.x, self.y, self.z))

    def __reduce__(self):
        """copy / pickle 用に、コンストラクタを通さずに再構築する情報を返す。

        om2 の型は C++ の実体を基底の ``__init__`` で確保するため、再構築関数で
        確保してから成分を設定する。利用者の派生クラスの ``__init__`` は呼ばず、
        ``__dict__`` と ``__slots__`` のアトリビュートは再構築時に復元する。

        Returns:
            tuple: ``(_rebuild, (type(self), (x, y, z))[, state])``。
        """
        return _reduce_value(self, (self.x, self.y, self.z))

    def __reduce_ex__(self, protocol):
        """pickle のプロトコルにかかわらず __reduce__ と同じ情報を返す。

        Args:
            protocol (int): pickle のプロトコル番号。使用しない。

        Returns:
            tuple: ``__reduce__()`` の結果。
        """
        return self.__reduce__()

    def __copy__(self):
        """同じ型・同じ成分の複製を返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートも浅く写す。

        Returns:
            Vector: 自身と同じクラスの新しいインスタンス。
        """
        return _copy_state(self, type(self)._wrap(self))

    def __deepcopy__(self, memo):
        """同じ型・同じ成分の複製を返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートは深く複製する。

        Args:
            memo (dict): copy.deepcopy の memo。

        Returns:
            Vector: 自身と同じクラスの新しいインスタンス。
        """
        return _copy_state(self, type(self)._wrap(self), memo)

    def __repr__(self):
        """クラス名と3成分を含むデバッグ表現を返す。

        Returns:
            str: ``Translate(1.0, 2.0, 3.0)`` の形式の文字列。
        """
        return f"{type(self).__name__}({self.x!r}, {self.y!r}, {self.z!r})"

    __str__ = __repr__

    def __eq__(self, other):
        """MVector 系との成分の完全一致を判定する。

        Args:
            other (object): 比較対象。

        Returns:
            bool | types.NotImplementedType: MVector 系と3個の数値の tuple/list は成分比較の結果。
            その他の om2 の型は False。それ以外の型は NotImplemented(相手の比較に委ね、
            どちらも判断しなければ False になる)。
        """
        operand = _vector_operand(other)
        if operand is not None:
            return _MVector.__eq__(self, operand)
        return _foreign_comparison(other, False)

    def __ne__(self, other):
        """``__eq__`` の否定を返す。

        Args:
            other (object): 比較対象。

        Returns:
            bool | types.NotImplementedType: MVector 系と3個の数値の tuple/list は成分比較の結果。
            その他の om2 の型は True。それ以外の型は NotImplemented。
        """
        operand = _vector_operand(other)
        if operand is not None:
            return _MVector.__ne__(self, operand)
        return _foreign_comparison(other, True)

    def __add__(self, other):
        """MVector 系との成分ごとの加算を返す。

        Args:
            other (object): 加算する MVector 系、または3個の数値の tuple/list。

        Returns:
            Vector | types.NotImplementedType: 新しい Vector。対応しない型は NotImplemented。
        """
        other = _vector_operand(other)
        if other is None:
            return NotImplemented
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, self)
        _MVector.__iadd__(result, other)
        return result

    def __radd__(self, other):
        """左辺の MVector 系との成分ごとの加算を返す。

        Args:
            other (object): 左辺の MVector 系、または3個の数値の tuple/list。

        Returns:
            Vector | types.NotImplementedType: 新しい Vector。対応しない型は NotImplemented。
        """
        other = _vector_operand(other)
        if other is None:
            return NotImplemented
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, other)
        _MVector.__iadd__(result, self)
        return result

    def __iadd__(self, other):
        """MVector 系を自身へ加算する。

        om2 の MVector を継承した型では、対応しない型との ``+=`` が例外にならず
        NotImplemented が代入されてしまうため、型を検査してから委譲する。

        Args:
            other (object): 加算する MVector 系、または3個の数値の tuple/list。

        Returns:
            Vector | types.NotImplementedType: 自身。対応しない型は NotImplemented(TypeError になる)。
        """
        other = _vector_operand(other)
        if other is None:
            return NotImplemented
        return _MVector.__iadd__(self, other)

    def __sub__(self, other):
        """MVector 系との成分ごとの減算を返す。

        Args:
            other (object): 減算する MVector 系、または3個の数値の tuple/list。

        Returns:
            Vector | types.NotImplementedType: 新しい Vector。対応しない型は NotImplemented。
        """
        other = _vector_operand(other)
        if other is None:
            return NotImplemented
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, self)
        _MVector.__isub__(result, other)
        return result

    def __rsub__(self, other):
        """左辺の MVector 系から自身を引いた値を返す。

        Args:
            other (object): 左辺の MVector 系、または3個の数値の tuple/list。

        Returns:
            Vector | types.NotImplementedType: 新しい Vector。対応しない型は NotImplemented。
        """
        other = _vector_operand(other)
        if other is None:
            return NotImplemented
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, other)
        _MVector.__isub__(result, self)
        return result

    def __isub__(self, other):
        """MVector 系を自身から減算する。

        Args:
            other (object): 減算する MVector 系、または3個の数値の tuple/list。

        Returns:
            Vector | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        other = _vector_operand(other)
        if other is None:
            return NotImplemented
        return _MVector.__isub__(self, other)

    def __mul__(self, other):
        """om2と同じ意味で掛け算をする。

        Args:
            other (object): 数値、MVector 系、または MMatrix 系。

        Returns:
            Vector | float | types.NotImplementedType: 相手によって次のようになる。
            数値なら数値倍のVector。MVector系なら内積のfloat。
            MMatrix系なら行ベクトルとして方向を変換したVector(平行移動を含まない)。
            対応しない型はNotImplemented。
        """
        if isinstance(other, _NUMBER):
            result = _NEW(Vector)
            _INIT(result)
            _MVector.__iadd__(result, self)
            _MVector.__imul__(result, other)
            return result
        if isinstance(other, _MVector):
            return _MVector.__mul__(self, other)
        if isinstance(other, _MMatrix):
            result = _NEW(Vector)
            _INIT(result)
            _MVector.__iadd__(result, self)
            _MVector.__imul__(result, other)
            return result
        return NotImplemented

    def __rmul__(self, other):
        """左辺からの掛け算を、om2と同じ意味で行う。

        ``m * v`` (mはMMatrix系)は、om2と同じく列ベクトルとしての積(``v * mᵀ``)になる。
        位置をマトリクスで変換するときは :meth:`mlib.maths.matrix.Matrix.transformPoint` を、
        方向を変換するときは ``v * m`` を使う。

        Args:
            other (object): 数値または MMatrix 系。

        Returns:
            Vector | types.NotImplementedType: 新しい Vector。対応しない型は NotImplemented。
        """
        if isinstance(other, _NUMBER):
            result = _NEW(Vector)
            _INIT(result)
            _MVector.__iadd__(result, self)
            _MVector.__imul__(result, other)
            return result
        if isinstance(other, _MMatrix):
            value = _MVector.__rmul__(self, other)
            if value is NotImplemented:
                return value
            result = _NEW(Vector)
            _INIT(result)
            _MVector.__iadd__(result, value)
            return result
        return NotImplemented

    def __imul__(self, other):
        """自身を数値倍する。またはMMatrix系で、行ベクトルとして方向を変換する。

        Args:
            other (object): 数値または MMatrix 系。

        Returns:
            Vector | types.NotImplementedType: 自身。対応しない型はNotImplemented。
            MVector系を渡した場合は、om2と同じく内積の計算になり、変数はfloatに置き換わる。
        """
        if not isinstance(other, (int, float, _MMatrix)):
            return NotImplemented
        return _MVector.__imul__(self, other)

    def __truediv__(self, other):
        """数値による成分ごとの除算を返す。

        Args:
            other (object): 除数の int または float。

        Returns:
            Vector | types.NotImplementedType: 新しい Vector。対応しない型は NotImplemented。

        Raises:
            ZeroDivisionError: other が 0 の場合(Maya のバージョンにかかわらない)。
        """
        if not isinstance(other, _NUMBER):
            return NotImplemented
        if other == 0:
            raise ZeroDivisionError("Vectorを0で割ることはできません")
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, self)
        _MVector.__itruediv__(result, other)
        return result

    def __itruediv__(self, other):
        """数値で自身を除算する。

        Args:
            other (object): 除数の int または float。

        Returns:
            Vector | types.NotImplementedType: 自身。対応しない型は NotImplemented。

        Raises:
            ZeroDivisionError: other が 0 の場合。
        """
        if not isinstance(other, _NUMBER):
            return NotImplemented
        if other == 0:
            raise ZeroDivisionError("Vectorを0で割ることはできません")
        return _MVector.__itruediv__(self, other)

    def __xor__(self, other):
        """MVector 系との外積を返す(om2 の ``^``)。

        Args:
            other (object): 外積の相手となる MVector 系。

        Returns:
            Vector | types.NotImplementedType: 新しい Vector。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MVector):
            return NotImplemented
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, _MVector.__xor__(self, other))
        return result

    def __rxor__(self, other):
        """左辺のMVector系と自身の外積 ``other ^ self`` を返す。

        Vectorはom2.MVectorの派生なので、``om2.MVector ^ Vector`` ではPythonがこのメソッドを先に呼ぶ。
        このメソッドが無いと、結果はom2の ``om2.MVector`` になる。

        Args:
            other (object): 左辺の MVector 系。

        Returns:
            Vector | types.NotImplementedType: 新しい Vector。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MVector):
            return NotImplemented
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, _MVector.__xor__(other, self))
        return result

    def __ixor__(self, other):
        """MVector 系との外積で自身を書き換える(om2 の MVector には無い in-place 版)。

        Args:
            other (object): 外積の相手となる MVector 系。

        Returns:
            Vector | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MVector):
            return NotImplemented
        result = _MVector.__xor__(self, other)
        self.x = result.x
        self.y = result.y
        self.z = result.z
        return self

    def __neg__(self):
        """各成分の符号を反転した値を返す。

        Returns:
            Vector: 新しい Vector。派生クラスの型は保持しない。
        """
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, self)
        _MVector.__imul__(result, -1.0)
        return result

    def __round__(self, ndigits=None):
        """組み込みの ``round`` から :meth:`round` を呼ぶ。

        Args:
            ndigits (int | None): roundと同じ桁数。

        Returns:
            Vector: 同型の新しい値。
        """
        return self.round(ndigits)

    @classmethod
    def fromIterable(cls, values):
        """3つの値を順に取り出せるもの(listやtupleなど)から作る。

        Args:
            values (Iterable[float]): 3つの値を持つ、反復できるもの。

        Returns:
            Vector: 呼び出したクラスの新しいインスタンス。

        Raises:
            ValueError: 要素数が3でない場合。
        """
        values = tuple(values)
        if len(values) != 3:
            raise ValueError(f"{cls.__name__}には3つの値を指定してください")
        return cls(values[0], values[1], values[2])

    @classmethod
    def fromAxis(cls, axis):
        """軸の名前から、その軸の向きの長さ1のベクトルを作る。

        ``"x"``・``"y"``・``"z"`` は正の向き、``"-x"``・``"-y"``・``"-z"`` は負の向きになる。
        ``"+x"`` のように正の符号を付けた名前と、大文字(``"X"``・``"-Y"``)も使える。
        前後に空白があると受け付けない。

        Args:
            axis (str): 軸の名前。

        Returns:
            Vector: 呼び出したクラスの新しいインスタンス(``Translate.fromAxis("y")`` はTranslate)。

        Raises:
            TypeError: axisが文字列でない場合。
            ValueError: axisが軸の名前でない場合。
        """
        index, sign = _axis_name(axis, "axis")
        values = [0.0, 0.0, 0.0]
        values[index] = sign
        return cls(values[0], values[1], values[2])

    @classmethod
    def getCenter(cls, points):
        """点列の重心(位置の平均)を返す。

        Args:
            points (Iterable[om2.MVector | om2.MPoint | Iterable[float]]): 1点以上の点列。

        Returns:
            Vector: 呼び出したクラスの新しい値(``Translate.getCenter(...)`` はTranslate)。

        Raises:
            TypeError: 点列が反復できない場合。
            ValueError: 点列が空の場合。
        """
        vectors = [_resolve_mvector(point) for point in _iterable(points, "points")]
        if not vectors:
            raise ValueError("点がないため、中心を計算できません")
        total = _MVector()
        for vector in vectors:
            _MVector.__iadd__(total, vector)
        _MVector.__itruediv__(total, float(len(vectors)))
        return cls._wrap(total)

    @classmethod
    def isPlanar(cls, points, tolerance=1e-10):
        """点がすべて同じ平面の上にあるか判定する。

        一直線上にない最初の3点で平面を決める。すべての点の、その平面からの距離がtolerance以下ならTrueを返す。
        点が3つ以下の場合と、すべての点が一直線上にある場合は、常にTrueになる。

        Args:
            points (Iterable[om2.MVector | om2.MPoint | Iterable[float]]): 点列。
            tolerance (float): 平面からの距離の許容誤差(点と同じ単位)。0以上。

        Returns:
            bool: 同一平面上ならTrue。

        Raises:
            TypeError: 点列が反復できない、またはtoleranceが数値でない場合。
            ValueError: toleranceが負・有限でない場合。
        """
        limit = _checked_tolerance(tolerance)
        vectors = [_resolve_mvector(point) for point in _iterable(points, "points")]
        if len(vectors) <= 3:
            return True
        origin = vectors[0]
        normal = None
        for index in range(1, len(vectors)):
            first = _MVector.__sub__(vectors[index], origin)
            for other in vectors[index + 1 :]:
                cross = _MVector.__xor__(first, _MVector.__sub__(other, origin))
                if cross.length() > 1e-12:
                    normal = cross.normal()
                    break
            if normal is not None:
                break
        if normal is None:
            return True
        return all(abs(_MVector.__mul__(_MVector.__sub__(vector, origin), normal)) <= limit for vector in vectors)

    def mirror(self, axis="x", pivot=(0.0, 0.0, 0.0)):
        """指定した中心で成分を反転した、新しい値を返す。

        Translate・Scale・Shearでも、数値をそのまま反転する用途に使える。
        Scale・Shearをマトリクスとして鏡映するときは、Matrix.mirrorを使う。

        Args:
            axis (str | int): 反転する軸。``"x"``・``"y"``・``"z"``、ミラー面の ``"YZ"``・``"XZ"``・``"XY"``、
                または0/1/2で指定する。x⇔YZ、y⇔XZ、z⇔XYが同じ意味になる。文字の順序と大文字・小文字は問わない。
            pivot (Iterable[float]): ミラーの中心。値と同じ単位で指定する。方向のベクトルには原点を使う。

        Returns:
            Vector: 自身と同じ型の新しい値。

        Raises:
            TypeError: axisが文字列・int以外の場合。
            ValueError: axisが不正、またはpivotが有限の3成分でない場合。
        """
        # ミラーの引数解決だけで使うため、使う時点で読み込む(util は標準ライブラリしか参照しない)。
        from ..util import mirrorArguments

        axes, center = mirrorArguments(axis, pivot)
        values = list(self)
        for index in axes:
            values[index] = 2 * center[index] - values[index]
        return type(self)(values)

    def mirrorIt(self, axis="x", pivot=(0.0, 0.0, 0.0)):
        """自身の成分を反転する。

        Args:
            axis (str | int): 反転する軸。:meth:`mirror` と同じ。
            pivot (Iterable[float]): ミラーの中心。値と同じ単位で指定する。

        Returns:
            Vector: 更新した自身。
        """
        self.x, self.y, self.z = self.mirror(axis, pivot)
        return self

    def round(self, ndigits=None):
        """各成分を小数点以下ndigits桁に丸めた、新しい値を返す。

        各成分に組み込みの ``round`` を使う(端数がちょうど半分なら偶数の側へ丸める)。
        丸めた結果の-0.0は0.0にそろえる。組み込みの ``round(value, ndigits)`` でも同じ結果になる。

        Args:
            ndigits (int | None): 小数点以下の桁数。負の値は整数部を丸める。Noneは整数の値へ丸める
                (成分はfloatのまま)。

        Returns:
            Vector: 自身と同じ型の新しい値。

        Raises:
            TypeError: ndigitsがint・None以外(boolを含む)の場合。
        """
        ndigits = _checked_digits(ndigits)
        return type(self)([_round_float(value, ndigits) for value in self])

    def roundIt(self, ndigits=None):
        """自身の3成分を丸める。

        Args:
            ndigits (int | None): roundと同じ桁数。

        Returns:
            Vector: 更新した自身。

        Raises:
            TypeError: ndigitsがint・None以外(boolを含む)の場合。自身は変更しない。
        """
        self.x, self.y, self.z = self.round(ndigits)
        return self

    def dot(self, other):
        """内積を返す。

        Args:
            other (om2.MVector | om2.MPoint | Iterable[float]): 内積の相手。

        Returns:
            float: 内積。
        """
        return _MVector.__mul__(self, _resolve_mvector(other))

    def cross(self, other):
        """外積を返す。

        Args:
            other (om2.MVector | om2.MPoint | Iterable[float]): 外積の相手。

        Returns:
            Vector: 外積。派生クラスの型は保持しない。
        """
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, _MVector.__xor__(self, _resolve_mvector(other)))
        return result

    def lengthSq(self):
        """長さの2乗(自身との内積)を返す。

        平方根を計算しないため、長さの比較だけが目的なら length() より速い。

        Returns:
            float: 長さの2乗。
        """
        return _MVector.__mul__(self, self)

    def normal(self, *args):
        """OpenMayaの規則で正規化した、新しいVectorを返す。

        自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: OpenMayaの同名メソッドへ渡す位置引数。通常は指定しない。

        Returns:
            Vector: 計算結果の新しい値。
        """
        return _vector_of(Vector, _MVector.normal(self, *args))

    def rotateBy(self, *args):
        """XYZのベクトルを、OpenMayaの規則で回転した新しいVectorを返す。

        引数はMVector.rotateBy()へそのまま渡す。自身と回転の引数は変更しない。
        クォータニオンを先に正規化したり、0のクォータニオンを例外にしたりはしない。
        そのため、正規化したコピーで回すQuaternion.rotateVector()とは、受け付ける入力の条件が違う。

        Args:
            *args: Quaternion・EulerRotateなどの回転、またはOpenMayaの軸の定数とラジアンの角度。
                受け付ける型の組み合わせはMVector.rotateBy()に従う。

        Returns:
            Vector: 基底のVectorの新しい値。派生クラスの型と、派生クラスで足したPythonの状態は引き継がない。
        """
        return _vector_of(Vector, _MVector.rotateBy(self, *args))

    def rotateTo(self, *args):
        """自身の方向を、指定した方向へ向ける回転のQuaternionを返す。

        自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: 向けたい方向(target)をMVector系で指定する。

        Returns:
            Quaternion: 計算結果の新しい値。
        """
        # 循環参照の回避: 同じパッケージ内で相互に参照するため、使う時点で読み込む。
        from .quaternion import Quaternion

        return Quaternion._wrap(_MVector.rotateTo(self, *args))

    def transformAsNormal(self, *args):
        """法線としてマトリクスで変換し、正規化した新しいVectorを返す。

        法線の変換には、マトリクスの逆転置を使う。自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: 変換に使うマトリクス(matrix)をMMatrix系で指定する。

        Returns:
            Vector: 計算結果の新しい値。
        """
        return _vector_of(Vector, _MVector.transformAsNormal(self, *args))

    def unitIt(self):
        """自身を正規化する。

        0のベクトルは正規化できないので、例外にする。

        Returns:
            Vector: 更新した自身。

        Raises:
            ValueError: 0のベクトルの場合。自身は変更しない。
        """
        value = self.unit()
        self.x, self.y, self.z = value
        return self

    def unit(self):
        """正規化した新しいベクトルを返す。

        om2の ``normal()`` は、0のベクトルでも例外にならず ``om2.MVector`` を返す。
        このメソッドはmlibのVectorを返し、0のベクトルは例外にする。

        Returns:
            Vector: 長さ1のベクトル。派生クラスの型は保たない。

        Raises:
            ValueError: 0のベクトルの場合。
        """
        length = self.length()
        if length == 0.0:
            raise ValueError("0のベクトルは正規化できません")
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, self)
        _MVector.__itruediv__(result, length)
        return result

    def distanceTo(self, other):
        """2点間のユークリッド距離を返す。

        Args:
            other (om2.MVector | om2.MPoint | Iterable[float]): 距離を測る相手。

        Returns:
            float: 距離。
        """
        return _MVector.__sub__(self, _resolve_mvector(other)).length()

    def angleTo(self, other):
        """別のベクトルとのなす角を、ラジアンで返す。

        ``atan2(|a × b|, a · b)`` で計算するので、ほぼ平行・反平行の場合も精度が落ちない
        (om2の ``angle()`` は、約1e-5ラジアン未満の角度を0として返す)。

        Args:
            other (om2.MVector | om2.MPoint | Iterable[float]): 角度を測る相手。

        Returns:
            float: 0からpiまでのラジアンの角度。

        Raises:
            ValueError: 自身またはotherが0のベクトルの場合。
        """
        other = _resolve_mvector(other)
        if _MVector.__mul__(self, self) == 0.0 or _MVector.__mul__(other, other) == 0.0:
            raise ValueError("0のベクトルとの角度は測れません")
        return math.atan2(_MVector.__xor__(self, other).length(), _MVector.__mul__(self, other))

    def isEquivalent(self, other, tolerance=1e-10):
        """許容誤差付きでほぼ等しいか判定する。

        判定はom2の ``isEquivalent`` で行う。2点間の距離がtolerance以下ならTrueになる。

        Args:
            other (om2.MVector | om2.MPoint | Iterable[float]): 比較対象。
            tolerance (float): 距離の許容誤差。

        Returns:
            bool: ほぼ等しければ True。
        """
        return _MVector.isEquivalent(self, _resolve_mvector(other), tolerance)

    def lerp(self, other, t):
        """別のベクトルとの線形補間 ``self + (other - self) * t`` を返す。

        Args:
            other (om2.MVector | om2.MPoint | Iterable[float]): 補間先。
            t (float): 補間の割合。0で自身、1でotherになる。0〜1の外を指定すると、その先へ延長する。

        Returns:
            Vector: 補間した結果。派生クラスの型は保たない。
        """
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, _resolve_mvector(other))
        _MVector.__isub__(result, self)
        _MVector.__imul__(result, t)
        _MVector.__iadd__(result, self)
        return result

    def projected(self, axis):
        """指定した軸の方向の成分(軸への正射影)を返す。

        Args:
            axis (om2.MVector | om2.MPoint | Iterable[float]): 射影する軸。長さは問わない。

        Returns:
            Vector: ``axis`` と平行な成分。派生クラスの型は保持しない。

        Raises:
            ValueError: axisがゼロベクトルの場合。
        """
        axis = _resolve_mvector(axis)
        length_sq = _MVector.__mul__(axis, axis)
        if length_sq == 0.0:
            raise ValueError("0のベクトルへは投影できません")
        result = _NEW(Vector)
        _INIT(result)
        _MVector.__iadd__(result, axis)
        _MVector.__imul__(result, _MVector.__mul__(self, axis) / length_sq)
        return result

    def orthogonal(self, axis):
        """指定した軸に直交する成分(軸の方向の成分を取り除いた値)を返す。

        ポールベクターやアップベクターを、主軸に直交させるときなどに使う(グラム・シュミットの直交化の1段分)。

        Args:
            axis (om2.MVector | om2.MPoint | Iterable[float]): 直交させる軸。長さは問わない。

        Returns:
            Vector: ``axis`` に直交する成分。派生クラスの型は保持しない。自身が軸と平行ならゼロベクトル。

        Raises:
            ValueError: axisがゼロベクトルの場合。
        """
        result = self.projected(axis)
        _MVector.__imul__(result, -1.0)
        _MVector.__iadd__(result, self)
        return result

    def orthogonalIt(self, axis):
        """自身を、指定した軸に直交する成分へ置き換える。

        Args:
            axis (om2.MVector | om2.MPoint | Iterable[float]): :meth:`orthogonal` と同じ軸。

        Returns:
            Vector: 更新した自身。

        Raises:
            ValueError: axisがゼロベクトルの場合。自身は変更しない。
        """
        self.x, self.y, self.z = self.orthogonal(axis)
        return self

    def distanceSqTo(self, other):
        """2点間の距離の2乗を返す。

        平方根を計算しないため、距離の比較だけが目的なら :meth:`distanceTo` より速い。

        Args:
            other (om2.MVector | om2.MPoint | Iterable[float]): 距離を測る相手。

        Returns:
            float: 距離の2乗。
        """
        difference = _MVector.__sub__(self, _resolve_mvector(other))
        return _MVector.__mul__(difference, difference)

    def isZero(self, tolerance=1e-10):
        """長さが tolerance 以下(ほぼゼロベクトル)か判定する。

        Args:
            tolerance (float): 長さの許容誤差。0以上。

        Returns:
            bool: 長さが tolerance 以下ならTrue。

        Raises:
            TypeError: toleranceが数値でない場合。
            ValueError: toleranceが負・有限でない場合。
        """
        limit = _checked_tolerance(tolerance)
        return _MVector.__mul__(self, self) <= limit * limit

    def abs(self):
        """各成分を絶対値にした、新しい値を返す。

        組み込みの ``abs()`` と混同しないよう、``__abs__`` は定義しない(``abs()`` で長さは求められない)。
        長さは :meth:`length` で取得する。

        Returns:
            Vector: 自身と同じ型の新しい値。
        """
        return type(self)([math.fabs(value) for value in self])

    def cotan(self, other):
        """別のベクトルとのなす角の、コタンジェント(``内積 / |外積|``)を返す。

        メッシュのラプラシアン(コタンジェントの重み)などに使う。

        Args:
            other (om2.MVector | om2.MPoint | Iterable[float]): 角度を測る相手。

        Returns:
            float: コタンジェント。鋭角は正、鈍角は負。

        Raises:
            ValueError: 自身またはotherが0のベクトルの場合、または2つが平行(角度が0かpi)な場合。
        """
        other = _resolve_mvector(other)
        if _MVector.__mul__(self, self) == 0.0 or _MVector.__mul__(other, other) == 0.0:
            raise ValueError("0のベクトルではコタンジェントを計算できません")
        sine = _MVector.__xor__(self, other).length()
        if sine == 0.0:
            raise ValueError("平行なベクトルではコタンジェントを計算できません")
        return _MVector.__mul__(self, other) / sine

    def slerp(self, other, t, spin=0):
        """別のベクトルとの間を補間する。向きは球面線形補間、長さは線形補間にする。

        2つのベクトルが作る平面の中で、自身の向きをotherの向きへ、角度のtの割合だけ回す
        (回す角度は ``(なす角 + 2pi * spin) * t``)。長さは ``|自身| + (|other| - |自身|) * t`` になる。
        2つが平行・反平行で平面が決まらないときは、自身の成分のうち絶対値が最も小さい座標軸と自身との外積を軸にして、その周りに回す。

        Args:
            other (om2.MVector | om2.MPoint | Iterable[float]): 補間先。
            t (float): 補間の割合。0で自身、1でother(spin=0の場合)になる。0〜1の外を指定すると、その先へ延長する。
            spin (int): 余分に回る周の数。0は最短経路、-1は逆回り(長い経路)。既定は0。

        Returns:
            Vector: 補間した結果。派生クラスの型は保たない。

        Raises:
            TypeError: tが数値でない場合、またはspinが整数でない場合(boolを含む)。
            ValueError: tが有限でない場合、または自身・otherが0のベクトルの場合。
        """
        weight = _finite(t, "t")
        if isinstance(spin, bool) or not isinstance(spin, int):
            raise TypeError("spinはintで指定してください")
        other = _resolve_mvector(other)
        start_length = self.length()
        end_length = other.length()
        if start_length == 0.0 or end_length == 0.0:
            raise ValueError("0のベクトルの方向は補間できません")
        start = _MVector.__truediv__(self, start_length)
        end = _MVector.__truediv__(other, end_length)
        axis = _MVector.__xor__(start, end)
        sine = axis.length()
        angle = math.atan2(sine, _MVector.__mul__(start, end))
        if sine < 1e-12:
            # 平行・反平行は回転の平面が決まらないため、自身に直交する軸を使う。
            index = min(range(3), key=lambda number: abs(start[number]))
            base = _MVector()
            base[index] = 1.0
            axis = _MVector.__xor__(start, base)
        axis = axis.normal()
        turn = (angle + 2.0 * math.pi * spin) * weight
        # ロドリゲスの回転の式(axis は start に直交する単位ベクトル)。
        direction = start * math.cos(turn) + _MVector.__xor__(axis, start) * math.sin(turn)
        result = _zero(Vector)
        _MVector.__iadd__(result, direction * (start_length + (end_length - start_length) * weight))
        return result

    def getClosestAxis(self, includeNegative=True):
        """ベクトルの向きに最も近い座標軸の名前を返す。

        :meth:`Transform.getClosestAxisToVector <mlib.nodes.transform.Transform.getClosestAxisToVector>` を
        値だけで行う版。候補の軸のうち、内積が最も大きいものを選ぶ。同じ値ならx・y・zの順で先のものを選ぶ。

        Args:
            includeNegative (bool): Trueなら負の軸(``"-x"`` など)も候補にする。Falseなら ``"x"``・``"y"``・``"z"`` だけ。

        Returns:
            str: ``"x"``・``"y"``・``"z"``・``"-x"``・``"-y"``・``"-z"`` のいずれか。:meth:`fromAxis` へ渡せる。

        Raises:
            TypeError: includeNegativeがbool以外の場合。
            ValueError: ゼロベクトルの場合。
        """
        if type(includeNegative) is not bool:
            raise TypeError("includeNegativeはboolで指定してください")
        if _MVector.__mul__(self, self) == 0.0:
            raise ValueError("0のベクトルに最も近い軸は求められません")
        best_name = None
        best_value = None
        for index, name in enumerate(("x", "y", "z")):
            value = self[index]
            candidates = [(name, value)]
            if includeNegative:
                candidates.append(("-" + name, -value))
            for candidate, dot in candidates:
                if best_value is None or dot > best_value:
                    best_name, best_value = candidate, dot
        return best_name

    def getBarycentricWeights(self, *points):
        """自身の位置を、2点(線分)または3点(三角形)の重心座標のウェイトに分ける。

        ウェイトの合計は1になる。``points[0] * w0 + points[1] * w1 (+ points[2] * w2)`` が自身の位置になる。
        ただし、線分では直線の上へ、三角形では平面の上へ射影した位置になる。
        線分・三角形の範囲の外では、負のウェイトになる。

        Args:
            *points (om2.MVector | om2.MPoint | Iterable[float]): 2点または3点。

        Returns:
            tuple[float, ...]: 点と同じ数のウェイト。

        Raises:
            TypeError: 点の数が2・3以外の場合。
            ValueError: 線分の長さが0、または三角形の面積が0(3点が一直線上)の場合。
        """
        if len(points) not in (2, 3):
            raise TypeError(f"getBarycentricWeightsには点を2個か3個指定してください: {len(points)}個")
        vectors = [_resolve_mvector(point) for point in points]
        offset = _MVector.__sub__(self, vectors[0])
        if len(vectors) == 2:
            edge = _MVector.__sub__(vectors[1], vectors[0])
            length_sq = _MVector.__mul__(edge, edge)
            if length_sq == 0.0:
                raise ValueError("長さ0の線分ではウェイトを計算できません")
            weight = _MVector.__mul__(offset, edge) / length_sq
            return 1.0 - weight, weight
        first = _MVector.__sub__(vectors[1], vectors[0])
        second = _MVector.__sub__(vectors[2], vectors[0])
        normal = _MVector.__xor__(first, second)
        area_sq = _MVector.__mul__(normal, normal)
        if area_sq == 0.0:
            raise ValueError("縮退した三角形ではウェイトを計算できません")
        weight1 = _MVector.__mul__(_MVector.__xor__(offset, second), normal) / area_sq
        weight2 = _MVector.__mul__(_MVector.__xor__(first, offset), normal) / area_sq
        return 1.0 - weight1 - weight2, weight1, weight2

    @classmethod
    def _wrap(cls, value):
        """3成分の値を複製した cls のインスタンスを返す(追加のアトリビュートは写さない)。

        Python の ``__new__`` / ``__init__`` を通さない(利用者の派生クラスの
        ``__init__`` も呼ばない)。

        Args:
            value (om2.MVector): 複製元。x・y・zを持つ値。

        Returns:
            Vector: cls の新しいインスタンス。
        """
        result = _NEW(cls)
        _INIT(result)
        result.x = value.x
        result.y = value.y
        result.z = value.z
        return result
