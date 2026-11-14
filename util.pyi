# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""クラスに属さない汎用の関数と、数学の値・空間の指定を扱う内部の補助関数を提供する。

公開する関数は、名前の整形・処理時間の計測・ミラーの指定の確認の3つ。
番号の確認・比較・派生クラスの状態のコピーや、空間の指定の確認は、先頭が ``_`` の内部の関数に分けてある。
"""

import copy
import copyreg
import math
import numbers
import string
import time
from operator import index as _as_index
from typing import Any, Callable, Iterable, Literal, NoReturn, Sequence
from typing import overload
import types

__all__ = ['legalizeName', 'measure', 'mirrorArguments']
_UNSET: ellipsis
_MAX_COLOR_INDEX: int
_SEPARATOR: str
_FILLER: str
_PERMITTED: frozenset
_NOT_AT_HEAD: frozenset
_TYPE_CACHE_LIMIT: int
_OM2_TYPES: dict
_STATEFUL_TYPES: dict
_ANGLE_UNITS: dict
_MIRROR_PLANES: tuple
_MIRROR_AXIS_CHOICES: str
_TIME_UNITS: dict


class _ArgumentError(TypeError):
    """長い名前と短縮名の引数の重複や、必須の値の不足を伝える例外。複数形でもTypeErrorとして伝える。"""

def legalizeName(name: str) -> str:
    """文字列を、Mayaのノード名に使える形に整える。

    文字列を整えるだけで、ノードや名前空間は作らない。

    - コロンは名前空間の区切りとして残し、区切った各部分の前後の空白を除く。
    - ASCIIの英数字と_以外の文字が続く部分は、まとめて1つの_に変える。
    - 数字で始まる部分には、先頭に_を付ける。
    - 空の部分は捨てる。先頭のコロンは1つだけ残す。
    - 使える部分が1つも残らなければ、_を返す。

    Args:
        name (str): 整える文字列。

    Returns:
        str: 整えた名前。すでにあるノードの名前と重なるかは調べない。

    Raises:
        TypeError: nameがstrでない場合。

    Examples:
        >>> legalizeName("rig:2nd joint")
        'rig:_2nd_joint'
    """
    ...

def measure(operation: Callable[..., Any], samples: int = ..., warmup: int = ...) -> dict:
    """処理にかかる時間を、秒で計測する。

    Args:
        operation (callable): 計測する処理。入力の更新と評価を含める。計測の各回で呼ぶ。
        samples (int): 時間を記録する回数。
        warmup (int): 記録を始める前に、空で実行する回数。

    Returns:
        dict: samples(記録した回数)、median_seconds(中央値)、min_seconds(最小)、max_seconds(最大)。

    Raises:
        TypeError: operationが呼び出せない場合。
        ValueError: samplesが1以上のintでない場合、またはwarmupが0以上のintでない場合(intでない場合も含む)。

    Note:
        同じ値を読むだけでは、キャッシュから返る速さを計ることになる。必要なdirty化は呼び出し側で行う。
        処理の副作用や、現在の時間の位置も、呼び出し側で管理する。
    """
    ...

def _mirror_axis(axis: str | int) -> int:
    """ミラーの指定を、反転する軸の番号(0=x, 1=y, 2=z)にする。

    反転する軸(``"x"``)とミラー面(``"YZ"``)のどちらの書き方も受け付ける。
    対応は x⇔YZ、y⇔XZ、z⇔XY で、面の文字の順序(``"ZX"`` など)と大文字小文字は問わない。
    ミラー面の名前は ``_MIRROR_PLANES[番号]`` で得られる。

    Args:
        axis (str | int): ``"x"``・``"y"``・``"z"``、``"YZ"``・``"XZ"``・``"XY"``、または0/1/2。

    Returns:
        int: 反転する軸の番号。

    Raises:
        TypeError: axis が文字列・int 以外(bool を含む)の場合。
        ValueError: axis が上記のどれにも当たらない場合。
    """
    ...

def mirrorArguments(axis: str | int, pivot: Iterable[float]) -> tuple:
    """ミラーの軸と中心座標を確かめて、使いやすい形で返す。

    axis は、反転する軸(``"x"``)でも、ミラー面(``"YZ"``)でも書ける。
    対応は x⇔YZ、y⇔XZ(``"ZX"`` も可)、z⇔XY。文字の順番と大文字・小文字は問わない。

    Args:
        axis (str | int): ``"x"``・``"y"``・``"z"``、``"YZ"``・``"XZ"``・``"XY"``、または0/1/2。
        pivot (Iterable[float]): ミラーの中心座標(3成分)。

    Returns:
        tuple: 2つの値の組。1つ目は反転する軸の番号を1つだけ入れたtuple(例 ``(0,)``)、
            2つ目は中心座標のtuple。

    Raises:
        TypeError: axis が文字列でもintでもない場合。
        ValueError: axis が対応していない値の場合、または中心が有限な3成分でない場合。
    """
    ...

def _clean_segment(segment: str) -> str:
    """コロンで区切った1つの部分を、それだけで使える名前に整える。

    前後の空白を除き、使えない文字が続く部分は1文字の ``_`` にまとめる。
    もともと入っていた ``_`` はそのまま残す。整えた結果が数字で始まるなら、先頭に ``_`` を足す。

    Args:
        segment (str): コロンを含まない1つの部分。

    Returns:
        str: 整えた部分。空白だけの部分や空の部分なら空文字列。
    """
    ...

def _checked_index(index: int, size: int, name: str) -> int:
    """番号を確かめて、0〜size-1 の範囲の番号に直す。

    om2 は、範囲外の負の番号を確かめない。Python が長さを1回だけ足して渡すため、
    MVector の ``v[-4]`` は最後の成分を返し、MMatrix の -17 以下は範囲外のメモリを読み書きしてしまう。
    そのため、om2 へ渡す前に必ずここで確かめる。

    Args:
        index (int): 番号。負の値は末尾から数える。
        size (int): 要素数。
        name (str): 例外メッセージに使う型名。

    Returns:
        int: 0〜size-1 の番号。

    Raises:
        TypeError: 整数として扱えない場合。
        IndexError: 範囲外の場合。
    """
    ...

def _is_om2_type(cls) -> bool:
    """cls が OpenMaya の型(API 1.0 / 2.0。派生クラスを含む)か判定する。

    Args:
        cls (type): 判定する型。

    Returns:
        bool: MRO に OpenMaya のモジュールで定義された型を含めば True。
    """
    ...

def _foreign_comparison(other: object, result: bool) -> bool | types.NotImplementedType:
    """om2 の同じ系統に属さない値と ``==`` / ``!=`` で比べたときの結果を返す。

    - 相手が om2 の型(MPoint や MObject など。OpenMaya API 1.0 の型を含む)なら、result で結果を決める。
      om2 の型は、知らない型と比べると TypeError を送出するため、相手側の比較へは回さない。
    - それ以外の型には NotImplemented を返し、相手の ``__eq__`` (反対側からの比較)に判断を任せる。
      どちらも判断しなければ Python の既定の比較(同じオブジェクトか)になる。そのため、
      ``None`` や文字列と比べても例外にならない(``None`` には result を直接返す)。

    Args:
        other (object): 比較対象。
        result (bool): om2 の型だった場合の結果(``==`` なら False、``!=`` なら True)。

    Returns:
        bool | types.NotImplementedType: om2 の型か None なら result、それ以外は NotImplemented。
    """
    ...

def _instance_state(value: object) -> tuple:
    """利用者の派生クラスのインスタンスが持つ追加のアトリビュートを取り出す。

    mlib 自身の型のように ``__dict__`` も ``__slots__`` のアトリビュートも持たない型は、
    型ごとの判定をキャッシュしてすぐに返す。

    Args:
        value (object): mlib の値。

    Returns:
        tuple: (``__dict__`` の浅いコピー、または None, ``__slots__`` の値の辞書、または None)。
    """
    ...

def _restore_state(target: object, state: dict | None, slots: dict | None) -> Any:
    """_instance_state で取り出したアトリビュートを target へ設定する。

    Args:
        target (object): 設定先。
        state (dict | None): ``__dict__`` へ追加するアトリビュート。
        slots (dict | None): ``__slots__`` へ設定するアトリビュート。

    Returns:
        object: target。
    """
    ...

def _copy_state(source: object, target: object, memo: dict | None = ...) -> Any:
    """派生クラスが追加したPythonの状態だけを、コピー先へ写す。

    数学の成分はコピー先にすでに作ってある前提で、その確保とコピーは呼び出し側が受け持つ。
    この関数は __dict__・__slots__ の値を取り出して、コピー先へ設定する。

    - memo=Noneなら、追加した値への参照をそのまま(浅く)写す。
    - memoを指定したら、先に source→target を登録してから深くコピーする。
      自分自身への参照は、コピー先への参照に置き換わる。

    ふつうの演算や型の変換で、追加した状態を自動で引き継ぐ仕組みではない。

    Args:
        source (object): コピー元の数学の値。
        target (object): 同じ型のコピー先。数学の成分は別に確保してある。
        memo (dict | None): copy.deepcopyで共有する辞書。Noneなら浅いコピー。

    Returns:
        object: 渡されたtarget自身。sourceの数学の成分は変えない。
    """
    ...

@overload
def _angle_unit(unit: str | None, default: str = ...) -> str: ...
@overload
def _angle_unit(unit: str | None, default: None) -> str | None: ...
@overload
def _angle_unit(unit: str | None, default: str | None = ...) -> str | None:
    """角度の単位名を ``"deg"`` / ``"rad"`` へ正規化する。

    Args:
        unit (str | None): ``"deg"``・``"degree"``・``"degrees"``・``"rad"``・``"radian"``・
            ``"radians"`` のいずれか。Noneはdefaultを使う。
        default (str | None): unitがNoneの場合に返す値。

    Returns:
        str | None: ``"deg"`` または ``"rad"``。unitとdefaultがNoneならNone。

    Raises:
        TypeError: unitが文字列・None以外の場合。
        ValueError: 未対応の単位名の場合。
    """
    ...

def _time_unit(unit: str | None, default: str | None = ...) -> str | None:
    """時間の単位名を ``"frame"`` / ``"sec"`` へ正規化する。

    ``"frame"`` は現在のUI時間単位(``currentUnit -time``。film なら1/24秒)の1フレームを表す。

    Args:
        unit (str | None): ``"frame"``・``"frames"``・``"sec"``・``"second"``・``"seconds"`` のいずれか。
            Noneはdefaultを使う。
        default (str | None): unitがNoneの場合に返す値。

    Returns:
        str | None: ``"frame"`` または ``"sec"``。unitとdefaultがNoneならNone。

    Raises:
        TypeError: unitが文字列・None以外の場合。
        ValueError: 未対応の単位名の場合。
    """
    ...

def _to_radians(value: float, unit: str) -> float:
    """正規化済みの単位の数値をラジアンへ変換する。

    Args:
        value (float): 角度。
        unit (str): ``"deg"`` または ``"rad"``。

    Returns:
        float: ラジアンの値。radはそのまま返す。
    """
    ...

def _from_radians(value: float, unit: str) -> float:
    """ラジアンの数値を正規化済みの単位へ変換する。

    Args:
        value (float): ラジアンの角度。
        unit (str): ``"deg"`` または ``"rad"``。

    Returns:
        float: 指定単位の値。radはそのまま返す。
    """
    ...

def _world_space(value: bool) -> bool:
    """boolの空間指定を検証する。

    Args:
        value (bool): Trueはワールド空間、Falseはローカル空間。

    Returns:
        bool: 検証済みの指定。

    Raises:
        TypeError: bool以外を指定した場合。
    """
    ...

def _finite(value: numbers.Real, name: str) -> float:
    """有限な実数を検証し、floatへ変換する。

    Args:
        value (numbers.Real): 検証する値。boolは数値として受け付けない。
        name (str): 例外メッセージに使う引数名。

    Returns:
        float: 変換済みの値。

    Raises:
        TypeError: 実数以外(boolを含む)の場合。
        ValueError: 無限大・NaNの場合。
    """
    ...

def _finite_vector(value: Iterable[numbers.Real], size: int, name: str) -> tuple[float, ...]:
    """成分数の決まった有限な実数列を検証し、floatのtupleへ変換する。

    Args:
        value (Iterable[numbers.Real]): 検証する成分列。
        size (int): 期待する成分数。
        name (str): 例外メッセージに使う引数名。

    Returns:
        tuple[float, ...]: 変換済みの成分。

    Raises:
        TypeError: 反復できない値、または成分に実数以外(boolを含む)がある場合。
        ValueError: 成分数が異なる、または無限大・NaNの成分がある場合。
    """
    ...

def _color_value(color: int | Sequence[float] | None) -> tuple[int | None, tuple[float, float, float] | None]:
    """表示色の指定を確かめる。

    Args:
        color (int | Sequence[float] | None): Mayaの色の番号(0〜31)、(r, g, b)、または色を無効にするNone。

    Returns:
        tuple[int | None, tuple[float, float, float] | None]: 番号で指定したら (番号, None)、
            RGBで指定したら (None, (r, g, b))、Noneなら (None, None)。

    Raises:
        TypeError: 型が不正な場合。
        ValueError: 範囲・成分数が不正な場合。
    """
    ...

def _checked_tolerance(value: numbers.Real, *, positive: bool = ...) -> float:
    """許容誤差を検証し、floatへ変換する。

    Args:
        value (numbers.Real): 許容誤差。
        positive (bool): Trueなら0を拒否し、正の値だけを受け付ける。既定は0以上。

    Returns:
        float: 変換済みの許容誤差。

    Raises:
        TypeError: 実数以外(boolを含む)の場合。
        ValueError: 無限大・NaN・負、またはpositive=Trueで0の場合。
    """
    ...

def _checked_digits(ndigits: int | None) -> int | None:
    """丸めの桁数を検証する。

    Args:
        ndigits (int | None): 小数点以下の桁数。負の値は整数部を丸める。Noneは整数へ丸める。

    Returns:
        int | None: 検証済みの桁数。

    Raises:
        TypeError: int・None以外(boolを含む)の場合。
    """
    ...

def _round_float(value: float, ndigits: int | None) -> float:
    """組み込みの ``round`` で丸め、-0.0 を 0.0 にそろえたfloatを返す。

    Args:
        value (float): 丸める値。
        ndigits (int | None): :func:`_checked_digits` で検証済みの桁数。

    Returns:
        float: 丸めた値。
    """
    ...

def _unique_ordered(items: Iterable[object], key: Callable[..., Any] | None = ...) -> list:
    """最初の出現順を保ったまま重複を除く。

    Args:
        items (Iterable[object]): 要素列。keyを省略する場合はハッシュ可能な要素。
        key (callable | None): 重複判定に使うキーを返す関数。Noneは要素自身。

    Returns:
        list: 最初の出現順を維持した要素。
    """
    ...

def _rethrow_init_error(cls, error: TypeError) -> NoReturn:
    """キーワード引数の解析で起きたTypeErrorを、作っているクラスの名前を先頭にした文言で送り直す。

    maths の ``__init__`` が ``_vector_keywords`` 等の補助関数から受けた
    ``"<helper>() <理由>"`` 形式のメッセージを、``"<Class>() <理由>"`` に書き換える。

    Args:
        cls (type): 構築中のクラス。
        error (TypeError): 補助関数が送出した例外。

    Returns:
        NoReturn: 正常には戻らない。

    Raises:
        TypeError: 書き換えたメッセージの例外。元の例外は連鎖しない。
    """
    ...


class _PointGrid:
    """最も近い点を探すための一様な格子(標準ライブラリだけで計算する)。

    格子の大きさは、点が広がる範囲の対角線と点の数から決める。探すときは、調べたい点が入る格子から
    外側へ広げていく。見つかった点より近い点が、それより外側の格子に無いと分かった時点で終える。

    Args:
        points (Sequence[Sequence[float]]): 3成分の点の並び。空でないこと。
    """
    def __init__(self, points) -> None: ...
    def nearest(self, point: Sequence[float], maxDistance: float | None = ...) -> tuple[int | None, float]:
        """最も近い点の番号と距離を返す。

        Args:
            point (Sequence[float]): 3成分の問い合わせ点。
            maxDistance (float | None): これより遠い点は探さない。Noneは制限なし。

        Returns:
            tuple[int | None, float]: 点の番号と距離。maxDistance内に無ければ ``(None, inf)``。
        """
        ...
    def _cell(self, point):
        """座標を格子の番号にする。"""
        ...
    points: Any
    size: Any
    cells: Any
    lows: Any
    highs: Any
