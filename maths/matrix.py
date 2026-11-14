"""om2.MMatrix を継承した、Maya の行ベクトル規約の4行4列のマトリクス。"""

from operator import index as _as_index

import maya.api.OpenMaya as om2

from ..util import _checked_index, _checked_tolerance, _copy_state, _finite, _finite_vector, _foreign_comparison
from .eulerRotate import EulerRotate
from .quaternion import Quaternion
from .scale import Scale
from .shear import Shear
from .translate import Translate
from .vector import Vector, _axis_name, _reduce_value, _vector_of, _zero

_MMatrix = om2.MMatrix
_MVector = om2.MVector
_MPoint = om2.MPoint
_MQuaternion = om2.MQuaternion
_MEuler = om2.MEulerRotation
_MTransformationMatrix = om2.MTransformationMatrix
_K_TRANSFORM = om2.MSpace.kTransform
_GET = _MMatrix.__getitem__
_SET = _MMatrix.__setitem__
#: om2 のスカラー倍。結果は素の om2.MMatrix で、1.0 倍は符号付きゼロ・inf・NaN を含めて
#: 値を変えない。mlib の ``__getitem__`` (Python)を経由せず、om2 の C 実装の添字で
#: 16要素を読むために使う(:attr:`Matrix.values` など)。
_SCALED = _MMatrix.__mul__
#: ``m * v`` で Vector を作る om2 の関数(Python の ``__new__`` / ``__init__`` を通さない)。
_VECTOR_NEW = _MVector.__new__
_VECTOR_INIT = _MVector.__init__
_VECTOR_IADD = _MVector.__iadd__
#: om2 の列ベクトルとしての積 ``m * v`` (``_VECTOR_RMUL(v, m)``)。
_VECTOR_RMUL = _MVector.__rmul__
_NUMBER = (int, float)
#: 添字の型の判定用(組み込み名より速く引けるモジュールの名前)。
_INT = int
#: ``m[行, 列]`` の (行, 列)(それぞれ -4〜3)から平坦な添字(0〜15)への表。
_CELL_INDEX = {(row, column): (row % 4) * 4 + column % 4 for row in range(-4, 4) for column in range(-4, 4)}
_POINT_TYPES = (_MVector, om2.MPoint, om2.MFloatVector, om2.MFloatPoint)
_MATRIX_SOURCES = (_MMatrix, om2.MFloatMatrix)
_MATRIX_ERROR = "MatrixにはMMatrix、4x4の行、16個の値のどれかを指定してください"
#: fromAim で aim と up を平行とみなす、単位ベクトルの外積の長さ(sin)の上限。
_PARALLEL_TOLERANCE = 1e-10


def _reinit_is_safe():
    """om2 の ``MMatrix.__init__`` を確保済みのインスタンスへ再適用してよい版か判定する。

    Maya 2022 の om2 は ``__init__`` を再び呼ぶたびに確保済みの C++ の実体をリークする
    (計測で約150バイト/回)。Maya 2024〜2027 ではリークせず、受け付けない引数で失敗した
    場合も値は変わらないことを確認している(2023 は未検証のためリークする版として扱う)。

    Returns:
        bool: API バージョンが 2024 以降なら True。
    """
    try:
        return om2.MGlobal.apiVersion() >= 20240000
    except Exception:
        return False


#: 列(16要素・4行4列)からの設定で、om2 のコンストラクタを自身へ再適用するか。
#: Matrix(16要素の list) の計測では、再適用できない 2022 は一時的な MMatrix を作って写す経路
#: (要素ごとの書き込み 2.29µs → 1.44µs)、2024 以降は再適用の方が写す経路より約1割速い
#: (2027 で 2.39µs → 1.51µs)。どちらも om2 が要素を検査し、受け付けない値では失敗する。
_REINIT = _reinit_is_safe()


def _set_sequence(target, values):
    """om2 のコンストラクタが受け付ける列を target へ書き込む。

    Args:
        target (om2.MMatrix): 書き込み先。
        values (list | tuple): 16要素、または4要素の行を4つ並べた列。

    Returns:
        bool: 書き込めたら True。om2 が受け付けない形(文字列の要素など)なら False で、
        target は変わらない。
    """
    try:
        if _REINIT:
            _MMatrix.__init__(target, values)
        else:
            _assign(target, _MMatrix(values))
    except (TypeError, ValueError):
        return False
    return True


def _xyz(value):
    """3成分の値を (x, y, z) の tuple として取り出す。

    Args:
        value (om2.MVector | om2.MPoint | Iterable[float]): 取り出し元。MPoint の w は無視する。

    Returns:
        tuple: (x, y, z)。

    Raises:
        ValueError: 反復可能オブジェクトの要素数が3でない場合。
    """
    if isinstance(value, _POINT_TYPES):
        return value.x, value.y, value.z
    x, y, z = value
    return x, y, z


def _finite_xyz(value, name):
    """3成分の有限な数値を (x, y, z) の float の tuple として取り出す。

    Args:
        value (om2.MVector | om2.MPoint | Iterable[float]): 取り出し元。MPoint の w は無視する。
        name (str): 例外メッセージに使う引数名。

    Returns:
        tuple[float, float, float]: (x, y, z)。

    Raises:
        TypeError: 数値の列でない場合(boolを含む)。
        ValueError: 成分数が3でない、または有限でない成分がある場合。
    """
    if isinstance(value, _POINT_TYPES):
        value = (value.x, value.y, value.z)
    elif isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{name}は3つの数値の並びで指定してください")
    return _finite_vector(value, 3, name)


def _lerp3(start, end, weight):
    """3成分の線形補間 ``start + (end - start) * weight`` を返す。

    Args:
        start (Sequence[float]): 補間元。
        end (Sequence[float]): 補間先。
        weight (float): 補間係数。

    Returns:
        tuple[float, float, float]: 補間した値。
    """
    return tuple(a + (b - a) * weight for a, b in zip(start, end))


def _new(cls):
    """Python の ``__new__`` / ``__init__`` を通さずに cls の単位マトリクスを作る。

    om2 の型は C++ の実体を基底の ``__init__`` で確保するため、``__new__`` の直後に
    必ず基底の ``__init__`` を呼ぶ。

    Args:
        cls (type): 生成する Matrix 系のクラス。

    Returns:
        Matrix: cls の単位マトリクス。
    """
    result = _MMatrix.__new__(cls)
    _MMatrix.__init__(result)
    return result


def _assign(target, source):
    """source の16要素を target へそのまま写す(C++ の実体は確保し直さない)。

    単位マトリクスを -0.0 倍した「すべて -0.0」のマトリクスへ source を加算する。-0.0 は加算の
    単位元なので、符号付きゼロ・inf・NaN を含めて source と同じ値になる(0.0 を
    使うと -0.0 が 0.0 になる)。

    Args:
        target (om2.MMatrix): 書き込み先。
        source (om2.MMatrix): 複製元。

    Returns:
        om2.MMatrix: target。
    """
    target.setToIdentity()
    _MMatrix.__imul__(target, -0.0)
    _MMatrix.__iadd__(target, source)
    return target


def _number(value):
    """マトリクスの要素を float へ変換する。

    om2 のコンストラクタと同じく数値だけを受け付け、文字列は拒否する
    (``float("1")`` のような文字列からの変換はしない)。

    Args:
        value (object): 要素。

    Returns:
        float: 変換した値。

    Raises:
        TypeError: 文字列など数値でない場合。
    """
    if isinstance(value, (str, bytes, bytearray)):
        raise TypeError("Matrixの値は数値で指定してください")
    return float(value)


def _flat_values(values):
    """om2 が直接受け付けない入力を、float の16要素リストへ変換する。

    Args:
        values (Sequence): 16要素、または4要素の行を4つ並べた列。要素は数値。

    Returns:
        list[float]: 行優先順の16要素。

    Raises:
        ValueError: 16要素の数値として解釈できない場合(文字列の要素を含む)。
    """
    try:
        if len(values) == 16:
            return [_number(value) for value in values]
        if len(values) == 4:
            rows = [tuple(row) for row in values]
            if all(len(row) == 4 for row in rows):
                return [_number(value) for row in rows for value in row]
    except (TypeError, ValueError):
        pass
    raise ValueError(_MATRIX_ERROR)


def _rotate_matrix(rotate):
    """回転の指定を回転だけの om2.MMatrix へ変換する。

    Args:
        rotate (Iterable[float] | om2.MEulerRotation | om2.MQuaternion): XYZ 順の
            ラジアン3成分、回転順序を持つ Euler 回転、またはクォータニオン(正規化して使う)。

    Returns:
        om2.MMatrix: 回転マトリクス。

    Raises:
        ValueError: ゼロクォータニオン、または3成分として解釈できない場合。
    """
    if isinstance(rotate, _MQuaternion):
        if rotate.x * rotate.x + rotate.y * rotate.y + rotate.z * rotate.z + rotate.w * rotate.w == 0.0:
            raise ValueError("0のクォータニオンは正規化できません")
        # mlibの派生クラスで包み直さないよう、om2の関数を直接呼ぶ(値は rotate.normal().asMatrix() と同じ)。
        return _MQuaternion.asMatrix(_MQuaternion.normal(rotate))
    if isinstance(rotate, _MEuler):
        return rotate.asMatrix()
    x, y, z = rotate
    euler = _MEuler()
    euler.x = x
    euler.y = y
    euler.z = z
    return euler.asMatrix()


def _compose_into(target, translate, rotation, scale, shear):
    """S * Sh * R に平行移動を置いた値を、単位マトリクスの target へ書き込む。

    ``MTransformationMatrix.setScale`` は絶対値が 1e-12 未満のスケールを 1e-12 に
    丸めるため使わず、要素を直接書き込む。

    Args:
        target (om2.MMatrix): 単位マトリクスで初期化済みの書き込み先。
        translate (tuple[float, float, float] | None): 平行移動。None は 0。
        rotation (om2.MMatrix | None): 回転マトリクス。None は回転なし。
        scale (tuple[float, float, float] | None): スケール。None は 1。
        shear (tuple[float, float, float] | None): XY、XZ、YZ のシアー。None は 0。

    Returns:
        om2.MMatrix: target。
    """
    if scale is not None or shear is not None:
        sx, sy, sz = (1.0, 1.0, 1.0) if scale is None else scale
        xy, xz, yz = (0.0, 0.0, 0.0) if shear is None else shear
        _SET(target, 0, sx)
        _SET(target, 4, sy * xy)
        _SET(target, 5, sy)
        _SET(target, 8, sz * xz)
        _SET(target, 9, sz * yz)
        _SET(target, 10, sz)
    if rotation is not None:
        _MMatrix.__imul__(target, rotation)
    if translate is not None:
        _SET(target, 12, translate[0])
        _SET(target, 13, translate[1])
        _SET(target, 14, translate[2])
    return target


def _components(translate, rotate, scale, shear):
    """合成用の引数を検証し、_compose_into へ渡す形へ変換する。

    Args:
        translate (Iterable[float] | None): 平行移動。
        rotate (Iterable[float] | om2.MEulerRotation | om2.MQuaternion | None): 回転。
        scale (Iterable[float] | None): スケール。
        shear (Iterable[float] | None): シアー。

    Returns:
        tuple: (translate, rotation_matrix, scale, shear)。未指定は None のまま。

    Raises:
        ValueError: 3成分として解釈できない値、またはゼロクォータニオンの場合。
    """
    return (
        None if translate is None else _xyz(translate),
        None if rotate is None else _rotate_matrix(rotate),
        None if scale is None else _xyz(scale),
        None if shear is None else _xyz(shear),
    )


class Matrix(om2.MMatrix):
    """om2.MMatrixを継承した、4行4列のマトリクス。

    Mayaと同じ行ベクトルの規約を使い、値は後から書き換えられる。OpenMayaのAPIへそのまま渡せる。

    - 作るときに渡した値はコピーする。
    - 16個の要素は行の順に並ぶ。平行移動は番号12〜14にある。
    - Mayaへ渡す平行移動はcmのまま使い、UIの単位へ換算しない。
    - 合成と分解はアフィン変換を前提にする。分解はMTransformationMatrixの規約に従う。
      行列式が負のときは、Zスケールを負にして180度の補償回転を入れる(cmds.xform・decomposeMatrixと同じ)。

    演算子の意味は次のとおり。

    * ``a * b`` / ``a @ b`` はマトリクスの積で、aを先に適用する。結果の型は ``type(a)`` になる。
      ``om2.MMatrix * Matrix`` もMatrixを返す。
    * 数値倍と足し算・引き算は、OpenMayaの成分ごとの演算になる。
    * ``Vector * m`` は方向の変換で、平行移動を含まない。
      左辺が ``om2.MVector`` / ``om2.MPoint`` なら、OpenMaya側で計算してOpenMayaの型を返す。
    * ``m * v`` はMVector系との列ベクトルの積(``v * mᵀ``)で、Vectorを返す。
      ``m * om2.MPoint`` も列ベクトルの積のXYZをVectorで返す。結果のwは捨て、wで割らない。
    * ``m @ v`` はTypeErrorになる。位置の変換には :meth:`transformPoint` か ``om2.MPoint(p) * m`` を使う。

    ``*=`` / ``@=`` / ``+=`` / ``-=`` は自身を書き換える。継承したメソッドのうち数学値を返すものも、mlibの型を返す。
    名前にItが付かない操作は新しい値を返し、Itが付く操作は自身を書き換える。
    成分のプロパティで取得した値も複製なので、書き換えてもマトリクスは変わらない。

    ハッシュはできない(dictのキーやsetの要素にできない)。
    ``m[i]`` は-16〜15、``m[行, 列]`` は行・列それぞれ-4〜3で指定し、代入もできる。範囲外はIndexErrorになる。
    ``==`` はMMatrix系との完全一致を比べる。違う型との比較は :class:`~mlib.maths.vector.Vector` と同じ扱いになる。
    """

    __slots__ = ()
    __hash__ = None

    def __new__(cls, *args, **kwargs):
        """基底初期化でC++実体を確保し、clsの単位マトリクスを作る。

        ``__init__`` を省略・失敗しても実体へアクセスできるよう、先に確保する。
        詳細は :meth:`mlib.maths.vector.Vector.__new__` を参照。

        Args:
            *args: ここでは使わない生成引数。
            **kwargs: ここでは使わないキーワード引数。

        Returns:
            Matrix: clsの単位マトリクス。
        """
        self = _MMatrix.__new__(cls)
        _MMatrix.__init__(self)
        return self

    def __init__(self, values=None, *, translate=None, rotate=None, scale=None, shear=None):
        """マトリクス、または平行移動・回転・スケール・シアーの成分から値を設定する。

        入力をすべて確かめてから書き込む。そのため、例外になったときは値が変わらない。

        Args:
            values (om2.MMatrix | om2.MFloatMatrix | Iterable[float] | Iterable[Iterable[float]] | None):
                16要素、または4行4列のマトリクス。指定すると、ほかの成分の引数はすべて無視する。
            translate (Iterable[float] | None): XYZの平行移動。Noneは0。
            rotate (Iterable[float] | om2.MEulerRotation | om2.MQuaternion | None): 回転。次のどれかで指定する。
                Noneは回転なし。

                - XYZ順のラジアンの3成分。
                - EulerRotate(om2.MEulerRotation)。回転順序も反映する。
                - クォータニオン。正規化してから使う。
            scale (Iterable[float] | None): XYZのスケール。Noneは1。0や、ごく小さい値もそのまま書き込む。
            shear (Iterable[float] | None): XY・XZ・YZのシアー。Noneは0。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: マトリクス入力が16要素として解釈できない場合、成分が3要素でない場合、
                または回転クォータニオンがゼロの場合。
        """
        if values is not None:
            kind = values.__class__
            if kind is not list and kind is not tuple:
                if isinstance(values, _MMatrix):
                    _assign(self, values)
                    return
                if isinstance(values, om2.MFloatMatrix):
                    _assign(self, _MMatrix(values))
                    return
                try:
                    values = list(values)
                except TypeError:
                    raise ValueError(_MATRIX_ERROR) from None
            # om2 が受け付けない形(数値以外の要素や行の列以外)は検証してから書き込む。
            # om2 は失敗時に値を変えないため、例外時も自身は変わらない。
            if not _set_sequence(self, values):
                _set_sequence(self, _flat_values(values))
            return
        if translate is None and rotate is None and scale is None and shear is None:
            self.setToIdentity()
            return
        parts = _components(translate, rotate, scale, shear)
        self.setToIdentity()
        _compose_into(self, *parts)

    def __getitem__(self, index):
        """マトリクスの要素を取得する。

        Args:
            index (int | slice | tuple[int, int]): 平坦な番号(負の番号も可)、スライス、
                または (行, 列)。行・列はそれぞれ -4〜3。

        Returns:
            float | tuple[float, ...]: 指定要素。スライスでは tuple。

        Raises:
            TypeError: 番号が整数・スライス・tuple 以外の場合。
            IndexError: 番号が範囲外の場合(平坦な番号は -16〜15)。
        """
        if index.__class__ is _INT:
            if -16 <= index < 16:
                # -16〜15 の範囲では ``index & 15`` が負の添字を 0〜15 へ正規化する。
                return _GET(self, index & 15)
        elif index.__class__ is tuple:
            # よく使う m[行, 列](-4〜3 の int)は表を引いて _flat_index を通さない。表は
            # 1.0 や True とも一致するため、行・列が int そのものか確かめてから使う。
            try:
                flat = _CELL_INDEX.get(index)
            except TypeError:  # ハッシュできない要素は _flat_index で TypeError にする。
                flat = None
            if flat is not None and index[0].__class__ is _INT is index[1].__class__:
                return _GET(self, flat)
        if isinstance(index, tuple):
            return _GET(self, _flat_index(index))
        if isinstance(index, slice):
            return tuple(_SCALED(self, 1.0))[index]
        return _GET(self, _checked_index(index, 16, "Matrix"))

    def __setitem__(self, index, value):
        """マトリクスの要素を設定する。

        Args:
            index (int | tuple[int, int]): 平坦な番号(-16〜15)、または (行, 列)。
            value (float): 設定する値。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 番号が整数・tuple 以外の場合。
            IndexError: 番号が範囲外の場合。
        """
        if index.__class__ is _INT:
            if -16 <= index < 16:
                _SET(self, index & 15, value)
                return
        elif index.__class__ is tuple:
            # __getitem__ と同じく、m[行, 列](-4〜3 の int)は表を引く。
            try:
                flat = _CELL_INDEX.get(index)
            except TypeError:
                flat = None
            if flat is not None and index[0].__class__ is _INT is index[1].__class__:
                _SET(self, flat, value)
                return
        if isinstance(index, tuple):
            index = _flat_index(index)
        else:
            index = _checked_index(index, 16, "Matrix")
        _SET(self, index, value)

    def __iter__(self):
        """行優先順の16要素を反復する。

        要素は反復を始めた時点の値(素の om2.MMatrix へ写した値)を返す。

        Returns:
            Iterator[float]: 16要素のイテレータ。
        """
        return iter(_SCALED(self, 1.0))

    def __reduce__(self):
        """copy / pickle 用に、コンストラクタを通さずに再構築する情報を返す。

        Returns:
            tuple: ``(_rebuild, (type(self), 16要素の tuple)[, state])``。
            利用者の派生クラスの ``__init__`` は呼ばず、``__dict__`` と ``__slots__`` の
            アトリビュートは再構築時に復元する。
        """
        return _reduce_value(self, tuple(_SCALED(self, 1.0)))

    def __reduce_ex__(self, protocol):
        """pickle のプロトコルにかかわらず __reduce__ と同じ情報を返す。

        Args:
            protocol (int): pickle のプロトコル番号。使用しない。

        Returns:
            tuple: ``__reduce__()`` の結果。
        """
        return self.__reduce__()

    def __copy__(self):
        """同じ型・同じ値の複製を返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートも浅く写す。

        Returns:
            Matrix: 自身と同じクラスの新しいインスタンス。
        """
        return _copy_state(self, type(self)._wrap(self))

    def __deepcopy__(self, memo):
        """同じ型・同じ値の複製を返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートは深く複製する。

        Args:
            memo (dict): copy.deepcopy の memo。

        Returns:
            Matrix: 自身と同じクラスの新しいインスタンス。
        """
        return _copy_state(self, type(self)._wrap(self), memo)

    def __repr__(self):
        """4行の値を含むデバッグ表現を返す。

        Returns:
            str: 型名と現在の成分を含む文字列表現。
        """
        return f"{type(self).__name__}({self.rows!r})"

    __str__ = __repr__

    def __eq__(self, other):
        """MMatrix 系との全要素の完全一致を判定する。

        Args:
            other (object): 比較対象。

        Returns:
            bool | types.NotImplementedType: MMatrix 系なら om2 と同じ比較の結果。
            その他の om2 の型は False。それ以外の型は NotImplemented(相手の比較に委ね、
            どちらも判断しなければ False になる)。
        """
        if isinstance(other, _MMatrix):
            return _MMatrix.__eq__(self, other)
        return _foreign_comparison(other, False)

    def __ne__(self, other):
        """``__eq__`` の否定を返す。

        Args:
            other (object): 比較対象。

        Returns:
            bool | types.NotImplementedType: MMatrix 系なら om2 と同じ比較の結果。
            その他の om2 の型は True。それ以外の型は NotImplemented。
        """
        if isinstance(other, _MMatrix):
            return _MMatrix.__ne__(self, other)
        return _foreign_comparison(other, True)

    def __mul__(self, other):
        """マトリクスの積、スカラー倍、またはベクトル・点との列ベクトルとしての積を返す。

        ベクトルと点は om2 と同じ列ベクトルとしての積(``v * mᵀ``)を計算し、
        om2 の型(``om2.MVector`` / ``om2.MPoint``)が右辺でも mlib の Vector で返す。

        Args:
            other (object): 右側の MMatrix 系、数値、MVector 系、または om2.MPoint。

        Returns:
            Matrix | Vector | types.NotImplementedType: マトリクス・数値なら ``type(self)`` の
            新しいマトリクス。MVector 系なら om2 の列ベクトルとしての積の Vector。om2.MPoint なら
            om2 の列ベクトルとしての積(同次座標の4成分)の x、y、z を持つ Vector(w は捨て、
            w で割らない)。対応しない型は NotImplemented。
        """
        if isinstance(other, _MMatrix):
            result = _new(type(self))
            result.setToProduct(self, other)
            return result
        if isinstance(other, _NUMBER):
            return type(self)._wrap(_MMatrix.__mul__(self, other))
        if isinstance(other, _MVector):
            result = _VECTOR_NEW(Vector)
            _VECTOR_INIT(result)
            _VECTOR_IADD(result, _VECTOR_RMUL(other, self))
            return result
        if isinstance(other, _MPoint):
            value = _MPoint.__rmul__(other, self)
            result = _VECTOR_NEW(Vector)
            _VECTOR_INIT(result)
            result.x = value.x
            result.y = value.y
            result.z = value.z
            return result
        return NotImplemented

    def __rmul__(self, other):
        """左辺の MMatrix 系とのマトリクスの積、またはスカラー倍を返す。

        Args:
            other (object): 左側の MMatrix 系、または数値。

        Returns:
            Matrix | types.NotImplementedType: ``type(self)`` の新しいマトリクス。
            対応しない型は NotImplemented。
        """
        if isinstance(other, _MMatrix):
            result = _new(type(self))
            result.setToProduct(other, self)
            return result
        if isinstance(other, _NUMBER):
            return type(self)._wrap(_MMatrix.__mul__(self, other))
        return NotImplemented

    def __imul__(self, other):
        """自身へ右からマトリクスを掛ける、またはスカラー倍する。

        Args:
            other (object): MMatrix 系または数値。

        Returns:
            Matrix | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        if not isinstance(other, (int, float, _MMatrix)):
            return NotImplemented
        return _MMatrix.__imul__(self, other)

    def __matmul__(self, other):
        """``@`` 演算子によるマトリクスの積(``*`` と同じ)。

        Args:
            other (object): 右側の MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: マトリクスの積。マトリクス以外は NotImplemented(TypeError)。
        """
        if isinstance(other, _MMatrix):
            return self.__mul__(other)
        return NotImplemented

    def __rmatmul__(self, other):
        """左辺の MMatrix 系との ``@`` によるマトリクスの積。

        Args:
            other (object): 左側の MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: マトリクスの積。マトリクス以外は NotImplemented。
        """
        if isinstance(other, _MMatrix):
            return self.__rmul__(other)
        return NotImplemented

    def __imatmul__(self, other):
        """``@=`` で自身へ右からマトリクスを掛ける(``*=`` と同じ in-place のマトリクスの積)。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: 自身。マトリクス以外は NotImplemented(TypeError)。
        """
        if not isinstance(other, _MMatrix):
            return NotImplemented
        return _MMatrix.__imul__(self, other)

    def __add__(self, other):
        """成分ごとの和を返す。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: ``type(self)`` の新しいマトリクス。
        """
        if not isinstance(other, _MMatrix):
            return NotImplemented
        return type(self)._wrap(_MMatrix.__add__(self, other))

    def __radd__(self, other):
        """左辺の MMatrix 系との成分ごとの和を返す。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: ``type(self)`` の新しいマトリクス。
        """
        if not isinstance(other, _MMatrix):
            return NotImplemented
        return type(self)._wrap(_MMatrix.__add__(other, self))

    def __iadd__(self, other):
        """MMatrix 系を成分ごとに自身へ加算する。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MMatrix):
            return NotImplemented
        return _MMatrix.__iadd__(self, other)

    def __sub__(self, other):
        """成分ごとの差を返す。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: ``type(self)`` の新しいマトリクス。
        """
        if not isinstance(other, _MMatrix):
            return NotImplemented
        return type(self)._wrap(_MMatrix.__sub__(self, other))

    def __rsub__(self, other):
        """左辺の MMatrix 系から自身を引いた成分ごとの差を返す。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: ``type(self)`` の新しいマトリクス。
        """
        if not isinstance(other, _MMatrix):
            return NotImplemented
        return type(self)._wrap(_MMatrix.__sub__(other, self))

    def __isub__(self, other):
        """MMatrix 系を成分ごとに自身から減算する。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        if not isinstance(other, _MMatrix):
            return NotImplemented
        return _MMatrix.__isub__(self, other)

    @classmethod
    def identity(cls):
        """単位マトリクスを生成する。

        引数なしの ``Matrix()`` と同じ結果だが、意図を明示できる。

        Returns:
            Matrix: 呼び出したクラスの単位マトリクス。
        """
        return _new(cls)

    @classmethod
    def compose(cls, translate=(0.0, 0.0, 0.0), rotate=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0), shear=(0.0, 0.0, 0.0)):
        """平行移動・回転・スケール・シアーの成分からマトリクスを作る。

        Args:
            translate (Iterable[float]): XYZの平行移動。
            rotate (Iterable[float] | om2.MEulerRotation | om2.MQuaternion): 回転。XYZ順のラジアンの3成分、
                EulerRotate(回転順序も反映する)、またはクォータニオンで指定する。
            scale (Iterable[float]): XYZのスケール。
            shear (Iterable[float]): XY・XZ・YZのシアー。

        Returns:
            Matrix: 呼び出したクラスの新しいマトリクス。

        Raises:
            ValueError: 成分が3要素でない場合、または回転クォータニオンがゼロの場合。
        """
        return cls(translate=translate, rotate=rotate, scale=scale, shear=shear)

    @classmethod
    def fromMMatrix(cls, matrix):
        """OpenMayaのマトリクスをコピーして、mlibのマトリクスを作る。

        Matrixはそれ自体がom2.MMatrixなので、OpenMayaへ渡すときに変換する必要はない。

        Args:
            matrix (om2.MMatrix | om2.MFloatMatrix): 複製元のマトリクス。

        Returns:
            Matrix: 呼び出したクラスの新しいマトリクス。
        """
        if isinstance(matrix, _MATRIX_SOURCES):
            return cls._wrap(matrix)
        return cls(matrix)

    @classmethod
    def fromTransformation(cls, transformation):
        """Maya API 2.0の変換情報からマトリクスを生成する。

        Args:
            transformation (om2.MTransformationMatrix): 合成する変換情報。

        Returns:
            Matrix: 呼び出したクラスの新しいマトリクス。
        """
        return cls._wrap(transformation.asMatrix())

    @classmethod
    def fromAxes(cls, x, y, z, position=(0.0, 0.0, 0.0)):
        """3つの軸のベクトルと位置を、そのまま各行へ入れたマトリクスを作る。

        Mayaの行ベクトルの規約で、次のように書き込む。

        - x・y・zは、番号0〜2・4〜6・8〜10の行へ入れる。
        - positionは、番号12〜14へ入れる。
        - 4列目は (0, 0, 0, 1) にする。

        軸の正規化や直交化、右手系への補正はしない。そのため、渡した軸の長さと傾きが
        そのままスケールとシアーになる。正規直交の向きが必要なときは :meth:`fromAim` を使う。

        Args:
            x (om2.MVector | om2.MPoint | Iterable[float]): X軸の行。MPointのwは無視する。
            y (om2.MVector | om2.MPoint | Iterable[float]): Y軸の行。
            z (om2.MVector | om2.MPoint | Iterable[float]): Z軸の行。
            position (om2.MVector | om2.MPoint | Iterable[float]): 平行移動(cm)。既定は原点。

        Returns:
            Matrix: 呼び出したクラスの新しいマトリクス。

        Raises:
            TypeError: 3成分の数値でない場合(boolを含む)。
            ValueError: 成分数が3でない、または有限でない成分がある場合。
        """
        rows = (_finite_xyz(x, "x"), _finite_xyz(y, "y"), _finite_xyz(z, "z"), _finite_xyz(position, "position"))
        result = _new(cls)
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                _SET(result, row * 4 + column, value)
        return result

    @classmethod
    def fromAim(cls, aim, up, *, aimAxis="x", upAxis="y", position=(0.0, 0.0, 0.0)):
        """向ける方向とアップ方向から、正規直交の向きのマトリクスを作る。

        aimConstraint(``worldUpType="vector"``)と同じ決め方で、軸を次のように決める。

        - aimAxisの軸を、aimの方向へ向ける。
        - upAxisの軸を、upからaim方向の成分を除いた方向へ向ける。
        - 残りの軸は、右手系になるよう外積で決める。

        aimとupは方向だけを使い、長さは無視する。結果のマトリクスは回転と平行移動だけを持ち、
        スケールは1、シアーは無い。``aimAxis="-y"`` のように負の軸を指定すると、その軸の逆向きをaimへ向ける。

        Args:
            aim (om2.MVector | om2.MPoint | Iterable[float]): 向ける方向(ワールドなど、親の空間で指定する)。
            up (om2.MVector | om2.MPoint | Iterable[float]): アップ方向。aimと平行にはできない。
            aimAxis (str): aimへ向ける軸。``"x"``・``"y"``・``"z"``・``"-x"``・``"-y"``・``"-z"`` のどれか。既定は ``"x"``。
            upAxis (str): upへ向ける軸。aimAxisと違う軸にする。既定は ``"y"``。
            position (om2.MVector | om2.MPoint | Iterable[float]): 平行移動(cm)。既定は原点。

        Returns:
            Matrix: 呼び出したクラスの新しいマトリクス。

        Raises:
            TypeError: aim・up・positionが3成分の数値でない場合、またはaimAxis・upAxisが文字列でない場合。
            ValueError: 次のどれかの場合。成分が有限でない。軸の名前が正しくない。
                aimAxisとupAxisが同じ軸(符号だけ違う場合を含む)。aim・upの長さが0。aimとupが平行。
        """
        aim_index, aim_sign = _axis_name(aimAxis, "aimAxis")
        up_index, up_sign = _axis_name(upAxis, "upAxis")
        if aim_index == up_index:
            raise ValueError("aimAxisとupAxisは別の軸で指定してください")
        aim = _MVector(_finite_xyz(aim, "aim"))
        up = _MVector(_finite_xyz(up, "up"))
        aim_length = aim.length()
        up_length = up.length()
        if aim_length == 0.0:
            raise ValueError("aimに0のベクトルは指定できません")
        if up_length == 0.0:
            raise ValueError("upに0のベクトルは指定できません")
        aim /= aim_length
        up /= up_length
        side = aim ^ up
        if side.length() <= _PARALLEL_TOLERANCE:
            raise ValueError("aimとupは平行にできません")
        # upからaim方向の成分を除いた方向(aimに直交する単位ベクトル)。
        up = (side ^ aim).normal()
        rows = [None, None, None]
        rows[aim_index] = aim * aim_sign
        rows[up_index] = up * up_sign
        # 残りの軸は x = y ^ z、y = z ^ x、z = x ^ y で右手系にする。
        other = 3 - aim_index - up_index
        rows[other] = rows[(other + 1) % 3] ^ rows[(other + 2) % 3]
        rows.append(_MVector(_finite_xyz(position, "position")))
        result = _new(cls)
        for row, vector in enumerate(rows):
            _SET(result, row * 4, vector.x)
            _SET(result, row * 4 + 1, vector.y)
            _SET(result, row * 4 + 2, vector.z)
        return result

    @property
    def values(self):
        """マトリクスの16個の成分を、行の順に並べたtupleとして取得する。

        Mayaの行ベクトルの規約で、平行移動は番号12・13・14にある。
        取得した時点の値のコピーなので、後でマトリクスを書き換えてもこのtupleは変わらない。

        Returns:
            tuple[float, ...]: 16要素。4行の入れ子形式はrowsを使う。
        """
        return tuple(_SCALED(self, 1.0))

    @property
    def rows(self):
        """マトリクスの16個の成分を、行ごとに区切った4行4列のtupleとして取得する。

        各行もtupleで、元のマトリクスとはつながっていない。
        並べ方を変えるだけで、転置や、座標空間・UIの単位の変換はしない。

        Returns:
            tuple[tuple[float, float, float, float], ...]: 行優先の4行。
        """
        values = tuple(_SCALED(self, 1.0))
        return (values[0:4], values[4:8], values[8:12], values[12:16])

    @property
    def translate(self):
        """平行移動の成分(番号12〜14)を取得・設定する。

        取得した値はコピーになる。設定するときは3成分を渡す。マトリクスを分解せず、番号12〜14へ
        直接書き込むので、スケールが0の軸があるなど、分解できないマトリクスにも使える。
        ``matrix.translate.x = value`` はコピーだけを書き換える。マトリクスを書き換えるときは
        ``matrix.translate = value`` を使う。

        Returns:
            Translate: マトリクスの平行移動成分。
        """
        return self._translate()

    @translate.setter
    def translate(self, value):
        """番号12〜14へ平行移動を直接書き込む。

        Args:
            value (Iterable[float]): 新しい平行移動。3成分。

        Returns:
            None: 値を返さない。
        """
        x, y, z = _xyz(value)
        _SET(self, 12, x)
        _SET(self, 13, y)
        _SET(self, 14, z)

    @property
    def scale(self):
        """スケールの成分を取得・設定する。

        om2.MTransformationMatrixと同じ規約で分解する(行列式が負ならZが負になる)。
        設定するときはXYZの3成分を渡す。回転・シアー・平行移動はそのままにして、マトリクスを組み立て直す。
        取得・設定のどちらも、分解できないときはValueErrorになる。

        Returns:
            Scale: 分解したスケール成分。
        """
        return _vector_of(Scale, self._checked_transformation().scale(_K_TRANSFORM))

    @scale.setter
    def scale(self, value):
        """スケール成分を置き換えて再合成する。

        Args:
            value (Iterable[float]): 新しいスケール。3成分。

        Returns:
            None: 値を返さない。
        """
        self._recompose(scale=value)

    @property
    def shear(self):
        """シアーの成分(XY・XZ・YZ)を取得・設定する。

        設定するときは3成分を渡す。回転・スケール・平行移動はそのままにして、マトリクスを組み立て直す。
        取得・設定のどちらも、分解できないときはValueErrorになる。

        Returns:
            Shear: 分解したシアー成分。
        """
        return _vector_of(Shear, self._checked_transformation().shear(_K_TRANSFORM))

    @shear.setter
    def shear(self, value):
        """シアー成分を置き換えて再合成する。

        Args:
            value (Iterable[float]): 新しいシアー。3成分。

        Returns:
            None: 値を返さない。
        """
        self._recompose(shear=value)

    @property
    def quaternion(self):
        """回転成分を Quaternion として取得する。

        Returns:
            Quaternion: 分解した回転値。

        Raises:
            ValueError: 分解できない場合(いずれかのスケール軸がゼロなど)。
        """
        return Quaternion._wrap(self._checked_transformation().rotation(asQuaternion=True))

    @property
    def euler(self):
        """回転の成分を、XYZ順のEulerRotateとして取得する。

        om2.MTransformationMatrix.rotation()と同じ角度を返す。
        同じ向きを表す別の解として、中間の軸が90度を超える値になることがある。

        Returns:
            EulerRotate: 分解した回転値(ラジアン)。

        Raises:
            ValueError: 分解できない場合(いずれかのスケール軸がゼロなど)。
        """
        return EulerRotate._wrap(self._checked_transformation().rotation())

    @property
    def rotate(self):
        """回転の成分を、XYZ順のEulerRotateとして取得・設定する。

        設定するときは、XYZ順のラジアンの3成分、EulerRotate(回転順序も反映する)、
        またはQuaternionを渡す。スケール・シアー・平行移動はそのままにして、マトリクスを組み立て直す。
        取得・設定のどちらも、分解できないときはValueErrorになる。
        取得したEulerRotateを書き換えても、元のマトリクスは変わらない。書き換えるときはrotateへ代入する。

        Returns:
            EulerRotate: 分解した回転値(ラジアン)。
        """
        return EulerRotate._wrap(self._checked_transformation().rotation())

    @rotate.setter
    def rotate(self, value):
        """回転成分を置き換えて再合成する。

        Args:
            value (Iterable[float] | om2.MEulerRotation | om2.MQuaternion): 新しい回転。

        Returns:
            None: 値を返さない。
        """
        self._recompose(rotate=value)

    def decompose(self):
        """マトリクスを分解して、平行移動・回転・スケール・シアーを取得する。

        回転・スケール・シアーは、1つのMTransformationMatrixで分解する。平行移動は番号12〜14から取る。
        分解の規約はOpenMayaに従い、UIの単位へは換算しない。

        分解した結果は、元の値をそのまま取り戻すものではない。ピボット、Eulerの何回転目か、
        どの軸のスケールが負だったかは元に戻らない。

        Returns:
            dict[str, object]: 次のキーを持つ新しい辞書。translate(Translate)、euler(EulerRotate。XYZ順・ラジアン)、
                quaternion(Quaternion)、scale(Scale)、shear(Shear)。
                どの値もコピーなので、書き換えても元のMatrixは変わらない。

        Raises:
            ValueError: スケールが0の軸があるなど、分解の前の検査で分解できないと判断した場合。
        """
        tm = self._checked_transformation()
        euler = tm.rotation()
        return {
            "translate": self._translate(),
            "quaternion": Quaternion._wrap(tm.rotation(asQuaternion=True)),
            "euler": EulerRotate._wrap(euler),
            "scale": _vector_of(Scale, tm.scale(_K_TRANSFORM)),
            "shear": _vector_of(Shear, tm.shear(_K_TRANSFORM)),
        }

    def getAxis(self, axis="x"):
        """3x3部分の1行(X・Y・Z軸のどれかの向きと長さ)をVectorで取得する。

        Mayaの行ベクトルの規約では、行0〜2は、ローカルのX・Y・Z軸をこのマトリクスで変換した向きになる。
        向きにはスケールも含む。``"-y"`` のように負の軸を指定すると、その行の符号を反転した向きを返す。

        Args:
            axis (str | int): ``"x"``・``"y"``・``"z"``・``"-x"``・``"-y"``・``"-z"`` (:meth:`Vector.fromAxis
                <mlib.maths.vector.Vector.fromAxis>` と同じ名前)、または行の番号 0〜2。

        Returns:
            Vector: 新しい軸のベクトル。正規化しない(長さはその軸のスケール)。

        Raises:
            TypeError: axisが文字列・int以外(boolを含む)の場合。
            ValueError: axisが軸の名前でない、または番号が0〜2でない場合。
        """
        if isinstance(axis, str):
            index, sign = _axis_name(axis, "axis")
        elif isinstance(axis, bool) or not isinstance(axis, int):
            raise TypeError("axisは'x'や'-y'のようなstrか、0〜2のintで指定してください")
        elif 0 <= axis <= 2:
            index, sign = axis, 1.0
        else:
            raise ValueError(f"axisは0・1・2のどれかで指定してください: {axis!r}")
        result = _zero(Vector)
        result.x = _GET(self, index * 4) * sign
        result.y = _GET(self, index * 4 + 1) * sign
        result.z = _GET(self, index * 4 + 2) * sign
        return result

    def getAxes(self):
        """3x3部分の3行(X・Y・Z軸)を Vector で取得する。

        Returns:
            tuple[Vector, Vector, Vector]: :meth:`getAxis` の ``"x"``・``"y"``・``"z"`` と同じ新しい値。
        """
        return self.getAxis(0), self.getAxis(1), self.getAxis(2)

    def asTranslateMatrix(self):
        """平行移動(番号12〜14)だけを持つマトリクスを返す。

        Returns:
            Matrix: 自身と同じクラスの新しいマトリクス。3x3部分は単位マトリクス。
        """
        result = _new(type(self))
        _SET(result, 12, _GET(self, 12))
        _SET(result, 13, _GET(self, 13))
        _SET(result, 14, _GET(self, 14))
        return result

    def asRotateMatrix(self):
        """回転だけを持つマトリクスを返す(スケール・シアー・平行移動を除く)。

        :attr:`quaternion` と同じく、MTransformationMatrixの規約で分解する。
        行列式が負のときは、負のZスケールと180度の補償回転に分ける。

        Returns:
            Matrix: 自身と同じクラスの新しい正規直交のマトリクス。

        Raises:
            ValueError: 分解できない場合(いずれかのスケール軸がゼロなど)。
        """
        return type(self)._wrap(_MQuaternion.asMatrix(self._checked_transformation().rotation(asQuaternion=True)))

    def asScaleMatrix(self):
        """スケールとシアーだけを持つマトリクスを返す(回転・平行移動を除く)。

        ``asScaleMatrix() * asRotateMatrix() * asTranslateMatrix()`` が自身(誤差の範囲)になる。

        Returns:
            Matrix: 自身と同じクラスの新しいマトリクス。

        Raises:
            ValueError: 分解できない場合(いずれかのスケール軸がゼロなど)。
        """
        tm = self._checked_transformation()
        return _compose_into(_new(type(self)), None, None, tuple(tm.scale(_K_TRANSFORM)), tuple(tm.shear(_K_TRANSFORM)))

    def as3x3(self):
        """3x3部分(回転・スケール・シアー)だけを残したマトリクスを返す。

        平行移動と4列目は、単位マトリクスの値にする。

        Returns:
            Matrix: 自身と同じクラスの新しいマトリクス。分解は行わないため、ゼロスケールでも使える。
        """
        result = _new(type(self))
        for row in range(3):
            for column in range(3):
                _SET(result, row * 4 + column, _GET(self, row * 4 + column))
        return result

    def isEquivalent(self, other, tolerance=1e-10):
        """許容誤差付きでほぼ等しいか判定する。

        ``==`` は完全一致なので、浮動小数点誤差を許容した比較にはこちらを使う。

        Args:
            other (om2.MMatrix | Iterable[float]): 比較対象。16要素や4行4列も受け付ける。
            tolerance (float): 各成分の差の許容誤差。

        Returns:
            bool: 全16成分の差が tolerance 以内なら True。
        """
        if not isinstance(other, _MMatrix):
            other = Matrix(other)
        return _MMatrix.isEquivalent(self, other, tolerance)

    def isIdentity(self, tolerance=1e-10):
        """許容誤差付きで単位マトリクスか判定する。

        Args:
            tolerance (float): 各成分の差の許容誤差。0以上。

        Returns:
            bool: 全16成分と単位マトリクスの差が tolerance 以下ならTrue。

        Raises:
            TypeError: toleranceが数値でない場合。
            ValueError: toleranceが負・有限でない場合。
        """
        limit = _checked_tolerance(tolerance)
        return all(abs(_GET(self, index) - (1.0 if index % 5 == 0 else 0.0)) <= limit for index in range(16))

    def hasNonUniformScale(self, tolerance=1e-10):
        """XYZで違うスケール、またはシアーを含むか判定する。

        MTransformationMatrixの規約で分解して調べる。スケールの絶対値の差か、シアーの成分が
        toleranceを超えればTrueを返す。行列式が負(鏡映)の場合はZスケールが負になるが、
        絶対値で比べるので一様とみなす。
        非一様スケールがあると、ジョイントやコンストレイントの計算が崩れる。その検査に使う。

        Args:
            tolerance (float): スケールの差・シアーの許容誤差。0以上。

        Returns:
            bool: 非一様スケールかシアーがあればTrue。

        Raises:
            TypeError: toleranceが数値でない場合。
            ValueError: toleranceが負・有限でない、または分解できない場合(いずれかのスケール軸がゼロなど)。
        """
        limit = _checked_tolerance(tolerance)
        tm = self._checked_transformation()
        scale = [abs(value) for value in tm.scale(_K_TRANSFORM)]
        if any(abs(value) > limit for value in tm.shear(_K_TRANSFORM)):
            return True
        return max(scale) - min(scale) > limit

    def inverse(self):
        """逆マトリクスを新しく作って返す。

        まずisSingular()で、逆マトリクスを求められるかを調べる。求められるときだけMMatrix.inverse()を呼ぶ。
        判定はOpenMayaに任せ、行列式が0かを独自に比べたり、UIの単位で判定の基準を変えたりはしない。
        自身は変更しない。ノードの親子関係やシーンを書き換えるものでもない。

        Returns:
            Matrix: 自身と同じクラスの新しい逆マトリクス。派生クラスで足したPythonの状態はコピーしない。

        Raises:
            ValueError: OpenMayaのisSingular()がTrueと判定した場合。
        """
        if self.isSingular():
            raise ValueError("マトリクスが特異なため、逆マトリクスを求められません")
        return type(self)._wrap(_MMatrix.inverse(self))

    def transpose(self):
        """転置したマトリクスを返す。

        Returns:
            Matrix: 自身と同じクラスの転置マトリクス。
        """
        return type(self)._wrap(_MMatrix.transpose(self))

    def transposeIt(self):
        """自身を転置する。

        Returns:
            Matrix: 更新した自身。
        """
        _assign(self, _MMatrix.transpose(self))
        return self

    def blend(self, other, weight):
        """別のマトリクスとの間を、成分ごとに補間した新しいマトリクスを返す。

        両方のマトリクスをMTransformationMatrixの規約で分解し、次のように補間してから組み立て直す。

        - 平行移動・スケール・シアーは線形補間。
        - 回転はクォータニオンの球面線形補間(最短経路)。

        weightが0なら自身を、1ならotherをそのままコピーする(分解と組み立て直しの誤差は入らない)。
        自身とotherは変更しない。

        結果はblendMatrixノードの出力と一致する。自身を ``inputMatrix`` に、otherを1つ目の ``targetMatrix`` にして、
        ``weight`` を指定した場合と同じになる(行列式が負のマトリクスも含む)。
        ただし、blendMatrixの ``envelope``・複数のターゲット・成分ごとのウェイト(translateWeightなど)に当たる指定は無い。

        行列式が負のマトリクスは、負のZスケールと180度の補償回転に分けて分解する。
        そのため、行列式が正と負のマトリクスの間ではZスケールが0を通り、途中のウェイトで
        逆マトリクスを求められないマトリクスになることがある(blendMatrixも同じ)。

        pairBlendは、チャンネルの値をEuler(既定)かクォータニオンで補間するノードで、マトリクスを分解しない。
        そのため、スケールやシアーを含む場合は、このメソッドと結果が違う。

        Args:
            other (om2.MMatrix | Iterable[float]): 補間先。16要素や4行4列でも指定できる。
            weight (float): 補間の割合。0以上1以下の有限な数値(範囲の外へは延長しない)。

        Returns:
            Matrix: 自身と同じクラスの新しいマトリクス。

        Raises:
            TypeError: weightが数値でない(boolを含む)、またはotherをマトリクスとして解釈できない場合。
            ValueError: weightが有限でない・0〜1の範囲外、otherの要素が不正、
                または自身・otherを分解できない(いずれかのスケール軸がゼロなど)場合。
        """
        weight = _finite(weight, "weight")
        if not 0.0 <= weight <= 1.0:
            raise ValueError("weightは0〜1で指定してください")
        if not isinstance(other, _MMatrix):
            other = Matrix(other)
        start = self._checked_transformation()
        end = Matrix._checked_transformation(other)
        if weight == 0.0:
            return type(self)._wrap(self)
        if weight == 1.0:
            return type(self)._wrap(other)
        translate = _lerp3((_GET(self, 12), _GET(self, 13), _GET(self, 14)), (_GET(other, 12), _GET(other, 13), _GET(other, 14)), weight)
        scale = _lerp3(start.scale(_K_TRANSFORM), end.scale(_K_TRANSFORM), weight)
        shear = _lerp3(start.shear(_K_TRANSFORM), end.shear(_K_TRANSFORM), weight)
        rotation = _MQuaternion.slerp(start.rotation(asQuaternion=True), end.rotation(asQuaternion=True), weight)
        return _compose_into(_new(type(self)), translate, _rotate_matrix(rotation), scale, shear)

    def transformPoint(self, value):
        """位置をこのマトリクスで変換する。平行移動も含めて変換する。

        入力のXYZをw=1として扱う。MPointを渡した場合も、元のwは無視する。
        計算は ``om2.MPoint(x, y, z, 1.0) * matrix`` のXYZと同じで、wで割る処理(射影除算)はしない。
        自身と入力値は変更しない。ノードを動かしたり、シーンから座標を取得したりもしない。
        位置とマトリクスの平行移動は同じ距離の単位として扱い、UIの単位へは換算しない。

        Args:
            value (om2.MVector | om2.MPoint | Iterable[float]): 変換するXYZの位置。MPointのwは使わない。

        Returns:
            Translate: 変換した位置の新しい値。入力の型が派生クラスでも引き継がず、派生クラスで足したPythonの状態も引き継がない。
        """
        result = _zero(Translate)
        if isinstance(value, _MVector):
            _MVector.__iadd__(result, value)
        else:
            x, y, z = _xyz(value)
            result.x = x
            result.y = y
            result.z = z
        _MVector.__imul__(result, self)
        result.x += _GET(self, 12)
        result.y += _GET(self, 13)
        result.z += _GET(self, 14)
        return result

    def transformVector(self, value):
        """方向をこのマトリクスで変換する。平行移動は含めない。

        XYZをw=0として扱い、``Vector(value) * matrix`` と同じ変換をする。MPointのwは無視する。
        正規化・法線向けの逆転置での変換・UIの単位への換算はしない。
        スケールやシアーで長さが変わる分も、そのまま結果に入る。自身と入力値は変更しない。

        Args:
            value (om2.MVector | om2.MPoint | Iterable[float]): 変換するXYZの方向。

        Returns:
            Vector: 変換した方向の新しい値。入力の型が派生クラスでも引き継がず、派生クラスで足したPythonの状態も引き継がない。
        """
        result = _zero(Vector)
        if isinstance(value, _MVector):
            _MVector.__iadd__(result, value)
        else:
            x, y, z = _xyz(value)
            result.x = x
            result.y = y
            result.z = z
        _MVector.__imul__(result, self)
        return result

    def mirror(self, axis="x", pivot=(0.0, 0.0, 0.0)):
        """「ビヘイビア」でミラーしたマトリクスを返す。

        Mayaの ``mirrorJoint -mirrorBehavior`` と同じ規約で、次のように要素を反転する。

        - 平行移動は、pivotを中心にaxisの成分を反転する。
        - 3x3部分の各行は、axis以外の2成分を反転する。

        軸そのものは反転せず、180度回転した姿勢になる。そのため行列式の符号は変わらない。
        形をそのまま映す鏡像とは違い、対になったノードを同じローカルの操作で左右対称に動かせる。
        スケールとシアーは変わらない。要素の符号を反転するだけなので、分解できないマトリクスにも使える。

        Args:
            axis (str | int): 反転する軸。``"x"``・``"y"``・``"z"``、ミラー面の ``"YZ"``・``"XZ"``・``"XY"``、
                または0/1/2で指定する。x⇔YZ、y⇔XZ、z⇔XYが同じ意味になる。文字の順序と大文字・小文字は問わない。
            pivot (Iterable[float]): ミラーの中心の座標。平行移動と同じ単位・空間で指定する。

        Returns:
            Matrix: 呼び出したクラスのミラー後のマトリクス。

        Raises:
            TypeError: axisが文字列・int以外の場合。
            ValueError: axisが不正、またはpivotが有限の3成分でない場合。
        """
        # ミラーの引数解決だけで使うため、使う時点で読み込む(util は標準ライブラリしか参照しない)。
        from ..util import mirrorArguments

        axes, center = mirrorArguments(axis, pivot)
        result = type(self)._wrap(self)
        for axis in axes:
            for row in range(3):
                for column in range(3):
                    if column != axis:
                        index = row * 4 + column
                        _SET(result, index, -_GET(result, index))
            _SET(result, 12 + axis, 2 * center[axis] - _GET(result, 12 + axis))
        return result

    def mirrorIt(self, axis="x", pivot=(0.0, 0.0, 0.0)):
        """自身を「ビヘイビア」でミラーする。

        反転の仕方は :meth:`mirror` と同じ。

        Args:
            axis (str | int): 反転する軸。:meth:`mirror` と同じ。
            pivot (Iterable[float]): ミラーの中心。平行移動と同じ単位・空間で指定する。

        Returns:
            Matrix: 更新した自身。
        """
        result = self.mirror(axis, pivot)
        for index in range(16):
            _SET(self, index, _GET(result, index))
        return self

    def adjoint(self, *args):
        """随伴マトリクスを、新しいMatrixとして返す。

        計算はOpenMayaのMMatrix.adjointで行う。自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: OpenMayaの同名メソッドへ渡す位置引数。通常は指定しない。

        Returns:
            Matrix: 計算結果の新しいMatrix。
        """
        return Matrix._wrap(_MMatrix.adjoint(self, *args))

    def cofactor(self, row, column):
        """指定した位置の余因子を返す。

        余因子は、その行と列を除いた3x3の行列式に、位置に応じた符号を付けた値。
        :meth:`adjoint` (随伴マトリクス)は余因子を転置して並べたものなので、``adjoint()[column, row]`` と等しい。

        Args:
            row (int): 行の番号(-4〜3)。
            column (int): 列の番号(-4〜3)。

        Returns:
            float: 余因子。

        Raises:
            TypeError: 行・列が整数として扱えない場合。
            IndexError: 行・列が範囲外の場合。
        """
        index = _flat_index((row, column))
        row, column = divmod(index, 4)
        rows = [r for r in range(4) if r != row]
        columns = [c for c in range(4) if c != column]
        (a, b, c), (d, e, f), (g, h, i) = ([_GET(self, r * 4 + k) for k in columns] for r in rows)
        minor = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
        return -minor if (row + column) % 2 else minor

    def homogenize(self, *args):
        """同次座標を正規化した、新しいMatrixを返す。

        計算はOpenMayaのMMatrix.homogenizeで行う。自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: OpenMayaの同名メソッドへ渡す位置引数。通常は指定しない。

        Returns:
            Matrix: 計算結果の新しいMatrix。
        """
        return Matrix._wrap(_MMatrix.homogenize(self, *args))

    @classmethod
    def _wrap(cls, value):
        """om2 のマトリクスを複製した cls のインスタンスを返す。

        Python の ``__new__`` / ``__init__`` を通さない(利用者の派生クラスの
        ``__init__`` も呼ばない)。:func:`_assign` で写すため、符号付きゼロ・inf・NaN を
        含めて値は value と一致し、om2 のコピーコンストラクタ(多重定義の解決が遅い)より速い。

        Args:
            value (om2.MMatrix | om2.MFloatMatrix): 複製元。

        Returns:
            Matrix: cls の新しいインスタンス。
        """
        result = _MMatrix.__new__(cls)
        if isinstance(value, _MMatrix):
            _MMatrix.__init__(result)
            _MMatrix.__imul__(result, -0.0)
            _MMatrix.__iadd__(result, value)
        else:
            _MMatrix.__init__(result, value)
        return result

    def _checked_transformation(self):
        """分解できることを確かめてから MTransformationMatrix を作る。

        om2 はゼロスケールのマトリクスも黙って分解するため、3x3 の行列式が 0 なら
        ValueError にする。

        Returns:
            om2.MTransformationMatrix: 自身から作ったマトリクス。

        Raises:
            ValueError: いずれかのスケール軸がゼロなど、3x3 部分が特異な場合。
        """
        if self.det3x3() == 0.0:
            raise ValueError("スケールが0の軸があるマトリクスは分解できません")
        return _MTransformationMatrix(self)

    def _translate(self):
        """番号12〜14を Translate として返す。

        Returns:
            Translate: 平行移動成分の新しいインスタンス。
        """
        result = _zero(Translate)
        result.x = _GET(self, 12)
        result.y = _GET(self, 13)
        result.z = _GET(self, 14)
        return result

    def _recompose(self, rotate=None, scale=None, shear=None):
        """分解値の一部を置き換えて、自身の値を組み立て直す。

        入力の形と分解を先に検査する。要素代入で失敗した場合、先行変更は自動では戻さない。

        Args:
            rotate (Iterable[float] | om2.MEulerRotation | om2.MQuaternion | None): 新しい回転。None は現在の値。
            scale (Iterable[float] | None): 新しいスケール。None は現在の値。
            shear (Iterable[float] | None): 新しいシアー。None は現在の値。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: 現在のマトリクスを分解できない場合、または入力が不正な場合。
        """
        tm = self._checked_transformation()
        parts = _components(
            (_GET(self, 12), _GET(self, 13), _GET(self, 14)),
            tm.rotation(asQuaternion=True) if rotate is None else rotate,
            tm.scale(_K_TRANSFORM) if scale is None else scale,
            tm.shear(_K_TRANSFORM) if shear is None else shear,
        )
        self.setToIdentity()
        _compose_into(self, *parts)


def _flat_index(index):
    """(行, 列) を平坦な番号へ変換する。

    Args:
        index (tuple[int, int]): 行と列。それぞれ -4〜3。

    Returns:
        int: 0〜15 の番号。

    Raises:
        TypeError: 行・列が整数として扱えない場合。
        IndexError: 範囲外、または2要素でない場合。
    """
    try:
        row, column = index
    except ValueError:
        raise IndexError("Matrixの番号は(row, column)で指定してください") from None
    try:
        row, column = _as_index(row), _as_index(column)
    except TypeError:
        raise TypeError("Matrixのrowとcolumnは整数で指定してください") from None
    if row < 0:
        row += 4
    if column < 0:
        column += 4
    if not (0 <= row < 4 and 0 <= column < 4):
        raise IndexError("Matrixの番号が範囲外です")
    return row * 4 + column
