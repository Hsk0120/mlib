# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
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
from typing import Any, Iterable, Iterator, Sequence
from typing_extensions import Self
import types

_MMatrix: Any
_MVector: Any
_MPoint: Any
_MQuaternion: Any
_MEuler: Any
_MTransformationMatrix: Any
_K_TRANSFORM: Any
_GET: Any
_SET: Any
_SCALED: Any
_VECTOR_NEW: Any
_VECTOR_INIT: Any
_VECTOR_IADD: Any
_VECTOR_RMUL: Any
_NUMBER: tuple
_INT: Any
_CELL_INDEX: dict
_POINT_TYPES: tuple
_MATRIX_SOURCES: tuple
_MATRIX_ERROR: str
_PARALLEL_TOLERANCE: float

def _reinit_is_safe() -> bool:
    """om2 の ``MMatrix.__init__`` を確保済みのインスタンスへ再適用してよい版か判定する。

    Maya 2022 の om2 は ``__init__`` を再び呼ぶたびに確保済みの C++ の実体をリークする
    (計測で約150バイト/回)。Maya 2024〜2027 ではリークせず、受け付けない引数で失敗した
    場合も値は変わらないことを確認している(2023 は未検証のためリークする版として扱う)。

    Returns:
        bool: API バージョンが 2024 以降なら True。
    """
    ...
_REINIT: Any

def _set_sequence(target: om2.MMatrix, values: list | tuple) -> bool:
    """om2 のコンストラクタが受け付ける列を target へ書き込む。

    Args:
        target (om2.MMatrix): 書き込み先。
        values (list | tuple): 16要素、または4要素の行を4つ並べた列。

    Returns:
        bool: 書き込めたら True。om2 が受け付けない形(文字列の要素など)なら False で、
        target は変わらない。
    """
    ...

def _xyz(value: om2.MVector | om2.MPoint | Iterable[float]) -> tuple:
    """3成分の値を (x, y, z) の tuple として取り出す。

    Args:
        value (om2.MVector | om2.MPoint | Iterable[float]): 取り出し元。MPoint の w は無視する。

    Returns:
        tuple: (x, y, z)。

    Raises:
        ValueError: 反復可能オブジェクトの要素数が3でない場合。
    """
    ...

def _finite_xyz(value: om2.MVector | om2.MPoint | Iterable[float], name: str) -> tuple[float, float, float]:
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
    ...

def _lerp3(start: Sequence[float], end: Sequence[float], weight: float) -> tuple[float, float, float]:
    """3成分の線形補間 ``start + (end - start) * weight`` を返す。

    Args:
        start (Sequence[float]): 補間元。
        end (Sequence[float]): 補間先。
        weight (float): 補間係数。

    Returns:
        tuple[float, float, float]: 補間した値。
    """
    ...

def _new(cls) -> Matrix:
    """Python の ``__new__`` / ``__init__`` を通さずに cls の単位マトリクスを作る。

    om2 の型は C++ の実体を基底の ``__init__`` で確保するため、``__new__`` の直後に
    必ず基底の ``__init__`` を呼ぶ。

    Args:
        cls (type): 生成する Matrix 系のクラス。

    Returns:
        Matrix: cls の単位マトリクス。
    """
    ...

def _assign(target: om2.MMatrix, source: om2.MMatrix) -> om2.MMatrix:
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
    ...

def _number(value: object) -> float:
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
    ...

def _flat_values(values: Sequence) -> list[float]:
    """om2 が直接受け付けない入力を、float の16要素リストへ変換する。

    Args:
        values (Sequence): 16要素、または4要素の行を4つ並べた列。要素は数値。

    Returns:
        list[float]: 行優先順の16要素。

    Raises:
        ValueError: 16要素の数値として解釈できない場合(文字列の要素を含む)。
    """
    ...

def _rotate_matrix(rotate: Iterable[float] | om2.MEulerRotation | om2.MQuaternion) -> om2.MMatrix:
    """回転の指定を回転だけの om2.MMatrix へ変換する。

    Args:
        rotate (Iterable[float] | om2.MEulerRotation | om2.MQuaternion): XYZ 順の
            ラジアン3成分、回転順序を持つ Euler 回転、またはクォータニオン(正規化して使う)。

    Returns:
        om2.MMatrix: 回転マトリクス。

    Raises:
        ValueError: ゼロクォータニオン、または3成分として解釈できない場合。
    """
    ...

def _compose_into(target: om2.MMatrix, translate: tuple[float, float, float] | None, rotation: om2.MMatrix | None, scale: tuple[float, float, float] | None, shear: tuple[float, float, float] | None) -> om2.MMatrix:
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
    ...

def _components(translate: Iterable[float] | None, rotate: Iterable[float] | om2.MEulerRotation | om2.MQuaternion | None, scale: Iterable[float] | None, shear: Iterable[float] | None) -> tuple:
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
    ...


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
    __slots__: tuple
    __hash__: None
    def __new__(cls, *args, **kwargs) -> Self:
        """基底初期化でC++実体を確保し、clsの単位マトリクスを作る。

        ``__init__`` を省略・失敗しても実体へアクセスできるよう、先に確保する。
        詳細は :meth:`mlib.maths.vector.Vector.__new__` を参照。

        Args:
            *args: ここでは使わない生成引数。
            **kwargs: ここでは使わないキーワード引数。

        Returns:
            Matrix: clsの単位マトリクス。
        """
        ...
    def __init__(self, values: om2.MMatrix | om2.MFloatMatrix | Iterable[float] | Iterable[Iterable[float]] | None = ..., *, translate: Iterable[float] | None = ..., rotate: Iterable[float] | om2.MEulerRotation | om2.MQuaternion | None = ..., scale: Iterable[float] | None = ..., shear: Iterable[float] | None = ...) -> None:
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
        ...
    def __getitem__(self, index: int | slice | tuple[int, int]) -> float | tuple[float, ...]:
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
        ...
    def __setitem__(self, index: int | tuple[int, int], value: float) -> None:
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
        ...
    def __iter__(self) -> Iterator[float]:
        """行優先順の16要素を反復する。

        要素は反復を始めた時点の値(素の om2.MMatrix へ写した値)を返す。

        Returns:
            Iterator[float]: 16要素のイテレータ。
        """
        ...
    def __reduce__(self) -> tuple:
        """copy / pickle 用に、コンストラクタを通さずに再構築する情報を返す。

        Returns:
            tuple: ``(_rebuild, (type(self), 16要素の tuple)[, state])``。
            利用者の派生クラスの ``__init__`` は呼ばず、``__dict__`` と ``__slots__`` の
            アトリビュートは再構築時に復元する。
        """
        ...
    def __reduce_ex__(self, protocol: int) -> tuple:
        """pickle のプロトコルにかかわらず __reduce__ と同じ情報を返す。

        Args:
            protocol (int): pickle のプロトコル番号。使用しない。

        Returns:
            tuple: ``__reduce__()`` の結果。
        """
        ...
    def __copy__(self) -> Matrix:
        """同じ型・同じ値の複製を返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートも浅く写す。

        Returns:
            Matrix: 自身と同じクラスの新しいインスタンス。
        """
        ...
    def __deepcopy__(self, memo: dict) -> Matrix:
        """同じ型・同じ値の複製を返す。

        利用者の派生クラスが ``__dict__`` / ``__slots__`` に持つアトリビュートは深く複製する。

        Args:
            memo (dict): copy.deepcopy の memo。

        Returns:
            Matrix: 自身と同じクラスの新しいインスタンス。
        """
        ...
    def __repr__(self) -> str:
        """4行の値を含むデバッグ表現を返す。

        Returns:
            str: 型名と現在の成分を含む文字列表現。
        """
        ...
    __str__: Any
    def __eq__(self, other: object) -> bool | types.NotImplementedType:
        """MMatrix 系との全要素の完全一致を判定する。

        Args:
            other (object): 比較対象。

        Returns:
            bool | types.NotImplementedType: MMatrix 系なら om2 と同じ比較の結果。
            その他の om2 の型は False。それ以外の型は NotImplemented(相手の比較に委ね、
            どちらも判断しなければ False になる)。
        """
        ...
    def __ne__(self, other: object) -> bool | types.NotImplementedType:
        """``__eq__`` の否定を返す。

        Args:
            other (object): 比較対象。

        Returns:
            bool | types.NotImplementedType: MMatrix 系なら om2 と同じ比較の結果。
            その他の om2 の型は True。それ以外の型は NotImplemented。
        """
        ...
    def __mul__(self, other: object) -> Matrix | Vector | types.NotImplementedType:
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
        ...
    def __rmul__(self, other: object) -> Matrix | types.NotImplementedType:
        """左辺の MMatrix 系とのマトリクスの積、またはスカラー倍を返す。

        Args:
            other (object): 左側の MMatrix 系、または数値。

        Returns:
            Matrix | types.NotImplementedType: ``type(self)`` の新しいマトリクス。
            対応しない型は NotImplemented。
        """
        ...
    def __imul__(self, other: object) -> Matrix | types.NotImplementedType:
        """自身へ右からマトリクスを掛ける、またはスカラー倍する。

        Args:
            other (object): MMatrix 系または数値。

        Returns:
            Matrix | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        ...
    def __matmul__(self, other: object) -> Matrix | types.NotImplementedType:
        """``@`` 演算子によるマトリクスの積(``*`` と同じ)。

        Args:
            other (object): 右側の MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: マトリクスの積。マトリクス以外は NotImplemented(TypeError)。
        """
        ...
    def __rmatmul__(self, other: object) -> Matrix | types.NotImplementedType:
        """左辺の MMatrix 系との ``@`` によるマトリクスの積。

        Args:
            other (object): 左側の MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: マトリクスの積。マトリクス以外は NotImplemented。
        """
        ...
    def __imatmul__(self, other: object) -> Matrix | types.NotImplementedType:
        """``@=`` で自身へ右からマトリクスを掛ける(``*=`` と同じ in-place のマトリクスの積)。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: 自身。マトリクス以外は NotImplemented(TypeError)。
        """
        ...
    def __add__(self, other: object) -> Matrix | types.NotImplementedType:
        """成分ごとの和を返す。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: ``type(self)`` の新しいマトリクス。
        """
        ...
    def __radd__(self, other: object) -> Matrix | types.NotImplementedType:
        """左辺の MMatrix 系との成分ごとの和を返す。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: ``type(self)`` の新しいマトリクス。
        """
        ...
    def __iadd__(self, other: object) -> Matrix | types.NotImplementedType:
        """MMatrix 系を成分ごとに自身へ加算する。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        ...
    def __sub__(self, other: object) -> Matrix | types.NotImplementedType:
        """成分ごとの差を返す。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: ``type(self)`` の新しいマトリクス。
        """
        ...
    def __rsub__(self, other: object) -> Matrix | types.NotImplementedType:
        """左辺の MMatrix 系から自身を引いた成分ごとの差を返す。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: ``type(self)`` の新しいマトリクス。
        """
        ...
    def __isub__(self, other: object) -> Matrix | types.NotImplementedType:
        """MMatrix 系を成分ごとに自身から減算する。

        Args:
            other (object): MMatrix 系。

        Returns:
            Matrix | types.NotImplementedType: 自身。対応しない型は NotImplemented。
        """
        ...
    @classmethod
    def identity(cls) -> Matrix:
        """単位マトリクスを生成する。

        引数なしの ``Matrix()`` と同じ結果だが、意図を明示できる。

        Returns:
            Matrix: 呼び出したクラスの単位マトリクス。
        """
        ...
    @classmethod
    def compose(cls, translate: Iterable[float] = ..., rotate: Iterable[float] | om2.MEulerRotation | om2.MQuaternion = ..., scale: Iterable[float] = ..., shear: Iterable[float] = ...) -> Matrix:
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
        ...
    @classmethod
    def fromMMatrix(cls, matrix: om2.MMatrix | om2.MFloatMatrix) -> Matrix:
        """OpenMayaのマトリクスをコピーして、mlibのマトリクスを作る。

        Matrixはそれ自体がom2.MMatrixなので、OpenMayaへ渡すときに変換する必要はない。

        Args:
            matrix (om2.MMatrix | om2.MFloatMatrix): 複製元のマトリクス。

        Returns:
            Matrix: 呼び出したクラスの新しいマトリクス。
        """
        ...
    @classmethod
    def fromTransformation(cls, transformation: om2.MTransformationMatrix) -> Matrix:
        """Maya API 2.0の変換情報からマトリクスを生成する。

        Args:
            transformation (om2.MTransformationMatrix): 合成する変換情報。

        Returns:
            Matrix: 呼び出したクラスの新しいマトリクス。
        """
        ...
    @classmethod
    def fromAxes(cls, x: om2.MVector | om2.MPoint | Iterable[float], y: om2.MVector | om2.MPoint | Iterable[float], z: om2.MVector | om2.MPoint | Iterable[float], position: om2.MVector | om2.MPoint | Iterable[float] = ...) -> Matrix:
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
        ...
    @classmethod
    def fromAim(cls, aim: om2.MVector | om2.MPoint | Iterable[float], up: om2.MVector | om2.MPoint | Iterable[float], *, aimAxis: str = ..., upAxis: str = ..., position: om2.MVector | om2.MPoint | Iterable[float] = ...) -> Matrix:
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
        ...
    @property
    def values(self) -> tuple[float, ...]:
        """マトリクスの16個の成分を、行の順に並べたtupleとして取得する。

        Mayaの行ベクトルの規約で、平行移動は番号12・13・14にある。
        取得した時点の値のコピーなので、後でマトリクスを書き換えてもこのtupleは変わらない。

        Returns:
            tuple[float, ...]: 16要素。4行の入れ子形式はrowsを使う。
        """
        ...
    @property
    def rows(self) -> tuple[tuple[float, float, float, float], ...]:
        """マトリクスの16個の成分を、行ごとに区切った4行4列のtupleとして取得する。

        各行もtupleで、元のマトリクスとはつながっていない。
        並べ方を変えるだけで、転置や、座標空間・UIの単位の変換はしない。

        Returns:
            tuple[tuple[float, float, float, float], ...]: 行優先の4行。
        """
        ...
    @property
    def translate(self) -> Translate:
        """平行移動の成分(番号12〜14)を取得・設定する。

        取得した値はコピーになる。設定するときは3成分を渡す。マトリクスを分解せず、番号12〜14へ
        直接書き込むので、スケールが0の軸があるなど、分解できないマトリクスにも使える。
        ``matrix.translate.x = value`` はコピーだけを書き換える。マトリクスを書き換えるときは
        ``matrix.translate = value`` を使う。

        Returns:
            Translate: マトリクスの平行移動成分。
        """
        ...
    @translate.setter
    def translate(self, value: Iterable[float]) -> None:
        """番号12〜14へ平行移動を直接書き込む。

        Args:
            value (Iterable[float]): 新しい平行移動。3成分。

        Returns:
            None: 値を返さない。
        """
        ...
    @property
    def scale(self) -> Scale:
        """スケールの成分を取得・設定する。

        om2.MTransformationMatrixと同じ規約で分解する(行列式が負ならZが負になる)。
        設定するときはXYZの3成分を渡す。回転・シアー・平行移動はそのままにして、マトリクスを組み立て直す。
        取得・設定のどちらも、分解できないときはValueErrorになる。

        Returns:
            Scale: 分解したスケール成分。
        """
        ...
    @scale.setter
    def scale(self, value: Iterable[float]) -> None:
        """スケール成分を置き換えて再合成する。

        Args:
            value (Iterable[float]): 新しいスケール。3成分。

        Returns:
            None: 値を返さない。
        """
        ...
    @property
    def shear(self) -> Shear:
        """シアーの成分(XY・XZ・YZ)を取得・設定する。

        設定するときは3成分を渡す。回転・スケール・平行移動はそのままにして、マトリクスを組み立て直す。
        取得・設定のどちらも、分解できないときはValueErrorになる。

        Returns:
            Shear: 分解したシアー成分。
        """
        ...
    @shear.setter
    def shear(self, value: Iterable[float]) -> None:
        """シアー成分を置き換えて再合成する。

        Args:
            value (Iterable[float]): 新しいシアー。3成分。

        Returns:
            None: 値を返さない。
        """
        ...
    @property
    def quaternion(self) -> Quaternion:
        """回転成分を Quaternion として取得する。

        Returns:
            Quaternion: 分解した回転値。

        Raises:
            ValueError: 分解できない場合(いずれかのスケール軸がゼロなど)。
        """
        ...
    @property
    def euler(self) -> EulerRotate:
        """回転の成分を、XYZ順のEulerRotateとして取得する。

        om2.MTransformationMatrix.rotation()と同じ角度を返す。
        同じ向きを表す別の解として、中間の軸が90度を超える値になることがある。

        Returns:
            EulerRotate: 分解した回転値(ラジアン)。

        Raises:
            ValueError: 分解できない場合(いずれかのスケール軸がゼロなど)。
        """
        ...
    @property
    def rotate(self) -> EulerRotate:
        """回転の成分を、XYZ順のEulerRotateとして取得・設定する。

        設定するときは、XYZ順のラジアンの3成分、EulerRotate(回転順序も反映する)、
        またはQuaternionを渡す。スケール・シアー・平行移動はそのままにして、マトリクスを組み立て直す。
        取得・設定のどちらも、分解できないときはValueErrorになる。
        取得したEulerRotateを書き換えても、元のマトリクスは変わらない。書き換えるときはrotateへ代入する。

        Returns:
            EulerRotate: 分解した回転値(ラジアン)。
        """
        ...
    @rotate.setter
    def rotate(self, value: Iterable[float] | om2.MEulerRotation | om2.MQuaternion) -> None:
        """回転成分を置き換えて再合成する。

        Args:
            value (Iterable[float] | om2.MEulerRotation | om2.MQuaternion): 新しい回転。

        Returns:
            None: 値を返さない。
        """
        ...
    def decompose(self) -> dict[str, object]:
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
        ...
    def getAxis(self, axis: str | int = ...) -> Vector:
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
        ...
    def getAxes(self) -> tuple[Vector, Vector, Vector]:
        """3x3部分の3行(X・Y・Z軸)を Vector で取得する。

        Returns:
            tuple[Vector, Vector, Vector]: :meth:`getAxis` の ``"x"``・``"y"``・``"z"`` と同じ新しい値。
        """
        ...
    def asTranslateMatrix(self) -> Matrix:
        """平行移動(番号12〜14)だけを持つマトリクスを返す。

        Returns:
            Matrix: 自身と同じクラスの新しいマトリクス。3x3部分は単位マトリクス。
        """
        ...
    def asRotateMatrix(self) -> Matrix:
        """回転だけを持つマトリクスを返す(スケール・シアー・平行移動を除く)。

        :attr:`quaternion` と同じく、MTransformationMatrixの規約で分解する。
        行列式が負のときは、負のZスケールと180度の補償回転に分ける。

        Returns:
            Matrix: 自身と同じクラスの新しい正規直交のマトリクス。

        Raises:
            ValueError: 分解できない場合(いずれかのスケール軸がゼロなど)。
        """
        ...
    def asScaleMatrix(self) -> Matrix:
        """スケールとシアーだけを持つマトリクスを返す(回転・平行移動を除く)。

        ``asScaleMatrix() * asRotateMatrix() * asTranslateMatrix()`` が自身(誤差の範囲)になる。

        Returns:
            Matrix: 自身と同じクラスの新しいマトリクス。

        Raises:
            ValueError: 分解できない場合(いずれかのスケール軸がゼロなど)。
        """
        ...
    def as3x3(self) -> Matrix:
        """3x3部分(回転・スケール・シアー)だけを残したマトリクスを返す。

        平行移動と4列目は、単位マトリクスの値にする。

        Returns:
            Matrix: 自身と同じクラスの新しいマトリクス。分解は行わないため、ゼロスケールでも使える。
        """
        ...
    def isEquivalent(self, other: om2.MMatrix | Iterable[float], tolerance: float = ...) -> bool:
        """許容誤差付きでほぼ等しいか判定する。

        ``==`` は完全一致なので、浮動小数点誤差を許容した比較にはこちらを使う。

        Args:
            other (om2.MMatrix | Iterable[float]): 比較対象。16要素や4行4列も受け付ける。
            tolerance (float): 各成分の差の許容誤差。

        Returns:
            bool: 全16成分の差が tolerance 以内なら True。
        """
        ...
    def isIdentity(self, tolerance: float = ...) -> bool:
        """許容誤差付きで単位マトリクスか判定する。

        Args:
            tolerance (float): 各成分の差の許容誤差。0以上。

        Returns:
            bool: 全16成分と単位マトリクスの差が tolerance 以下ならTrue。

        Raises:
            TypeError: toleranceが数値でない場合。
            ValueError: toleranceが負・有限でない場合。
        """
        ...
    def hasNonUniformScale(self, tolerance: float = ...) -> bool:
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
        ...
    def inverse(self) -> Matrix:
        """逆マトリクスを新しく作って返す。

        まずisSingular()で、逆マトリクスを求められるかを調べる。求められるときだけMMatrix.inverse()を呼ぶ。
        判定はOpenMayaに任せ、行列式が0かを独自に比べたり、UIの単位で判定の基準を変えたりはしない。
        自身は変更しない。ノードの親子関係やシーンを書き換えるものでもない。

        Returns:
            Matrix: 自身と同じクラスの新しい逆マトリクス。派生クラスで足したPythonの状態はコピーしない。

        Raises:
            ValueError: OpenMayaのisSingular()がTrueと判定した場合。
        """
        ...
    def transpose(self) -> Matrix:
        """転置したマトリクスを返す。

        Returns:
            Matrix: 自身と同じクラスの転置マトリクス。
        """
        ...
    def transposeIt(self) -> Matrix:
        """自身を転置する。

        Returns:
            Matrix: 更新した自身。
        """
        ...
    def blend(self, other: om2.MMatrix | Iterable[float], weight: float) -> Matrix:
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
        ...
    def transformPoint(self, value: om2.MVector | om2.MPoint | Iterable[float]) -> Translate:
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
        ...
    def transformVector(self, value: om2.MVector | om2.MPoint | Iterable[float]) -> Vector:
        """方向をこのマトリクスで変換する。平行移動は含めない。

        XYZをw=0として扱い、``Vector(value) * matrix`` と同じ変換をする。MPointのwは無視する。
        正規化・法線向けの逆転置での変換・UIの単位への換算はしない。
        スケールやシアーで長さが変わる分も、そのまま結果に入る。自身と入力値は変更しない。

        Args:
            value (om2.MVector | om2.MPoint | Iterable[float]): 変換するXYZの方向。

        Returns:
            Vector: 変換した方向の新しい値。入力の型が派生クラスでも引き継がず、派生クラスで足したPythonの状態も引き継がない。
        """
        ...
    def mirror(self, axis: str | int = ..., pivot: Iterable[float] = ...) -> Matrix:
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
        ...
    def mirrorIt(self, axis: str | int = ..., pivot: Iterable[float] = ...) -> Matrix:
        """自身を「ビヘイビア」でミラーする。

        反転の仕方は :meth:`mirror` と同じ。

        Args:
            axis (str | int): 反転する軸。:meth:`mirror` と同じ。
            pivot (Iterable[float]): ミラーの中心。平行移動と同じ単位・空間で指定する。

        Returns:
            Matrix: 更新した自身。
        """
        ...
    def adjoint(self, *args) -> Matrix:
        """随伴マトリクスを、新しいMatrixとして返す。

        計算はOpenMayaのMMatrix.adjointで行う。自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: OpenMayaの同名メソッドへ渡す位置引数。通常は指定しない。

        Returns:
            Matrix: 計算結果の新しいMatrix。
        """
        ...
    def cofactor(self, row: int, column: int) -> float:
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
        ...
    def homogenize(self, *args) -> Matrix:
        """同次座標を正規化した、新しいMatrixを返す。

        計算はOpenMayaのMMatrix.homogenizeで行う。自身と入力値は変更しない。引数と0の値の扱いはOpenMayaに従う。

        Args:
            *args: OpenMayaの同名メソッドへ渡す位置引数。通常は指定しない。

        Returns:
            Matrix: 計算結果の新しいMatrix。
        """
        ...
    @classmethod
    def _wrap(cls, value: om2.MMatrix | om2.MFloatMatrix) -> Matrix:
        """om2 のマトリクスを複製した cls のインスタンスを返す。

        Python の ``__new__`` / ``__init__`` を通さない(利用者の派生クラスの
        ``__init__`` も呼ばない)。:func:`_assign` で写すため、符号付きゼロ・inf・NaN を
        含めて値は value と一致し、om2 のコピーコンストラクタ(多重定義の解決が遅い)より速い。

        Args:
            value (om2.MMatrix | om2.MFloatMatrix): 複製元。

        Returns:
            Matrix: cls の新しいインスタンス。
        """
        ...
    def _checked_transformation(self) -> om2.MTransformationMatrix:
        """分解できることを確かめてから MTransformationMatrix を作る。

        om2 はゼロスケールのマトリクスも黙って分解するため、3x3 の行列式が 0 なら
        ValueError にする。

        Returns:
            om2.MTransformationMatrix: 自身から作ったマトリクス。

        Raises:
            ValueError: いずれかのスケール軸がゼロなど、3x3 部分が特異な場合。
        """
        ...
    def _translate(self) -> Translate:
        """番号12〜14を Translate として返す。

        Returns:
            Translate: 平行移動成分の新しいインスタンス。
        """
        ...
    def _recompose(self, rotate: Iterable[float] | om2.MEulerRotation | om2.MQuaternion | None = ..., scale: Iterable[float] | None = ..., shear: Iterable[float] | None = ...) -> None:
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
        ...

def _flat_index(index: tuple[int, int]) -> int:
    """(行, 列) を平坦な番号へ変換する。

    Args:
        index (tuple[int, int]): 行と列。それぞれ -4〜3。

    Returns:
        int: 0〜15 の番号。

    Raises:
        TypeError: 行・列が整数として扱えない場合。
        IndexError: 範囲外、または2要素でない場合。
    """
    ...
