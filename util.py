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

__all__ = ["legalizeName", "measure", "mirrorArguments"]

# 長短のどちらを省略したかを区別する。値として渡すための定数ではない。
_UNSET = ...

#: Mayaの色の番号の上限(0〜31)。
_MAX_COLOR_INDEX = 31

#: 名前空間の区切り文字。区切りとして残し、区間ごとに検査する。
_SEPARATOR = ":"

#: 使えない文字の代わりに入れる文字。
_FILLER = "_"

#: 区間内で使ってよい文字。``str.isalnum`` は非ASCII文字も真になるため使わない。
_PERMITTED = frozenset(string.ascii_letters + string.digits + _FILLER)

#: 区間の先頭に置けない文字。``str.isdigit`` は上付き数字なども真になるため使わない。
_NOT_AT_HEAD = frozenset(string.digits)

# 型を動的に作る利用側でも保持し続けないよう、判定キャッシュに上限を設ける。
_TYPE_CACHE_LIMIT = 256
_OM2_TYPES = {}
_STATEFUL_TYPES = {}

#: 角度の単位名と正規化した名前。シーン操作の数値の角度は既定で度(``"deg"``)。
_ANGLE_UNITS = {"deg": "deg", "degree": "deg", "degrees": "deg", "rad": "rad", "radian": "rad", "radians": "rad"}

#: 反転する軸の番号(0=x, 1=y, 2=z)の順に並べたミラー面の名前。x を反転するミラーは YZ 面のミラー。
_MIRROR_PLANES = ("YZ", "XZ", "XY")

#: ミラーの axis に指定できる書き方の案内(例外の文言用)。
_MIRROR_AXIS_CHOICES = "反転する軸'x'・'y'・'z'(または0・1・2)か、ミラー平面'YZ'・'XZ'・'XY'"

#: 時間の単位名と正規化した名前。シーン操作の数値の時間は既定で現在のUI時間単位のフレーム(``"frame"``)。
_TIME_UNITS = {"frame": "frame", "frames": "frame", "sec": "sec", "second": "sec", "seconds": "sec"}


class _ArgumentError(TypeError):
    """長い名前と短縮名の引数の重複や、必須の値の不足を伝える例外。複数形でもTypeErrorとして伝える。"""


def legalizeName(name):
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
    if not isinstance(name, str):
        raise TypeError(f"nameはstrで指定してください: {type(name).__name__}")
    text = name.strip()
    segments = []
    for part in text.split(_SEPARATOR):
        cleaned = _clean_segment(part)
        if cleaned:
            segments.append(cleaned)
    if not segments:
        return _FILLER
    joined = _SEPARATOR.join(segments)
    if text.startswith(_SEPARATOR):
        return _SEPARATOR + joined
    return joined


def measure(operation, samples=30, warmup=3):
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
    if not callable(operation):
        raise TypeError("operationは呼び出せるオブジェクトにしてください")
    if type(samples) is not int or samples <= 0 or type(warmup) is not int or warmup < 0:
        raise ValueError("サンプル数が不正です")
    # statisticsはfractions・decimalも読むため、import mlibの時間を増やさないよう計測前に読む。
    import statistics

    for _ in range(warmup):
        operation()
    values = []
    for _ in range(samples):
        start = time.perf_counter()
        operation()
        values.append(time.perf_counter() - start)
    return {"samples": samples, "median_seconds": statistics.median(values), "min_seconds": min(values), "max_seconds": max(values)}


def _mirror_axis(axis):
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
    if type(axis) is int:
        if axis in (0, 1, 2):
            return axis
        raise ValueError(f"axisは{_MIRROR_AXIS_CHOICES}で指定してください: {axis!r}")
    if not isinstance(axis, str):
        raise TypeError(f"axisはstrかintで指定してください: {type(axis).__name__}")
    letters = axis.lower()
    if letters in ("x", "y", "z"):
        return "xyz".index(letters)
    if len(letters) == 2 and letters[0] != letters[1] and all(letter in "xyz" for letter in letters):
        # ミラー面に含まれない残りの1軸が、反転する軸になる。
        return next(index for index, letter in enumerate("xyz") if letter not in letters)
    raise ValueError(f"axisは{_MIRROR_AXIS_CHOICES}で指定してください: {axis!r}")


def mirrorArguments(axis, pivot):
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
    flip = _mirror_axis(axis)
    try:
        center = tuple(float(value) for value in pivot)
    except (TypeError, ValueError):
        raise ValueError("pivotは3つの有限な数値で指定してください") from None
    if len(center) != 3 or not all(math.isfinite(value) for value in center):
        raise ValueError("pivotは3つの有限な数値で指定してください")
    return (flip,), center


def _clean_segment(segment):
    """コロンで区切った1つの部分を、それだけで使える名前に整える。

    前後の空白を除き、使えない文字が続く部分は1文字の ``_`` にまとめる。
    もともと入っていた ``_`` はそのまま残す。整えた結果が数字で始まるなら、先頭に ``_`` を足す。

    Args:
        segment (str): コロンを含まない1つの部分。

    Returns:
        str: 整えた部分。空白だけの部分や空の部分なら空文字列。
    """
    out = []
    in_bad_run = False
    for char in segment.strip():
        if char in _PERMITTED:
            out.append(char)
            in_bad_run = False
            continue
        if not in_bad_run:
            out.append(_FILLER)
            in_bad_run = True
    cleaned = "".join(out)
    if cleaned[:1] in _NOT_AT_HEAD:
        cleaned = _FILLER + cleaned
    return cleaned


def _checked_index(index, size, name):
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
    try:
        position = _as_index(index)
    except TypeError:
        raise TypeError(f"{name}の番号は整数かスライスで指定してください: {type(index).__name__}") from None
    if position < 0:
        position += size
    if not 0 <= position < size:
        raise IndexError(f"{name}の番号が範囲外です")
    return position


def _is_om2_type(cls):
    """cls が OpenMaya の型(API 1.0 / 2.0。派生クラスを含む)か判定する。

    Args:
        cls (type): 判定する型。

    Returns:
        bool: MRO に OpenMaya のモジュールで定義された型を含めば True。
    """
    found = _OM2_TYPES.get(cls)
    if found is None:
        found = False
        for base in cls.__mro__:
            module = getattr(base, "__module__", None) or ""
            if module.startswith(("OpenMaya", "maya.OpenMaya", "maya.api.")):
                found = True
                break
        if len(_OM2_TYPES) >= _TYPE_CACHE_LIMIT:
            _OM2_TYPES.clear()
        _OM2_TYPES[cls] = found
    return found


def _foreign_comparison(other, result):
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
    if other is None or _is_om2_type(type(other)):
        return result
    return NotImplemented


def _instance_state(value):
    """利用者の派生クラスのインスタンスが持つ追加のアトリビュートを取り出す。

    mlib 自身の型のように ``__dict__`` も ``__slots__`` のアトリビュートも持たない型は、
    型ごとの判定をキャッシュしてすぐに返す。

    Args:
        value (object): mlib の値。

    Returns:
        tuple: (``__dict__`` の浅いコピー、または None, ``__slots__`` の値の辞書、または None)。
    """
    cls = type(value)
    stateful = _STATEFUL_TYPES.get(cls)
    if stateful is None:
        stateful = bool(cls.__dictoffset__) or bool(copyreg._slotnames(cls))
        if len(_STATEFUL_TYPES) >= _TYPE_CACHE_LIMIT:
            _STATEFUL_TYPES.clear()
        _STATEFUL_TYPES[cls] = stateful
    if not stateful:
        return None, None
    state = getattr(value, "__dict__", None)
    state = dict(state) if state else None
    slots = None
    for name in copyreg._slotnames(type(value)):
        try:
            item = getattr(value, name)
        except AttributeError:
            continue
        if slots is None:
            slots = {}
        slots[name] = item
    return state, slots


def _restore_state(target, state, slots):
    """_instance_state で取り出したアトリビュートを target へ設定する。

    Args:
        target (object): 設定先。
        state (dict | None): ``__dict__`` へ追加するアトリビュート。
        slots (dict | None): ``__slots__`` へ設定するアトリビュート。

    Returns:
        object: target。
    """
    if state:
        target.__dict__.update(state)
    if slots:
        for name, item in slots.items():
            setattr(target, name, item)
    return target


def _copy_state(source, target, memo=None):
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
    if memo is not None:
        memo[id(source)] = target
    state, slots = _instance_state(source)
    if state is None and slots is None:
        return target
    if memo is not None:
        if state:
            state = copy.deepcopy(state, memo)
        if slots:
            slots = copy.deepcopy(slots, memo)
    return _restore_state(target, state, slots)


def _angle_unit(unit, default="deg"):
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
    if unit is None:
        return default
    if not isinstance(unit, str):
        raise TypeError(f"角度の単位は文字列で指定してください: {unit!r}")
    try:
        return _ANGLE_UNITS[unit]
    except KeyError:
        if unit in _TIME_UNITS:
            # 時間の単位を角度の引数へ渡した誤りを、正しい引数名で伝える。
            raise ValueError(f"対応していない角度の単位です: {unit!r}(時間の値にはtimeUnitを使います)") from None
        raise ValueError(f"対応していない角度の単位です: {unit!r}('deg'か'rad'を使います)") from None


def _time_unit(unit, default="frame"):
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
    if unit is None:
        return default
    if not isinstance(unit, str):
        raise TypeError(f"時間の単位は文字列で指定してください: {unit!r}")
    try:
        return _TIME_UNITS[unit]
    except KeyError:
        if unit in _ANGLE_UNITS:
            raise ValueError(f"対応していない時間の単位です: {unit!r}(角度の値にはunitを使います)") from None
        raise ValueError(f"対応していない時間の単位です: {unit!r}('frame'か'sec'を使います)") from None


def _to_radians(value, unit):
    """正規化済みの単位の数値をラジアンへ変換する。

    Args:
        value (float): 角度。
        unit (str): ``"deg"`` または ``"rad"``。

    Returns:
        float: ラジアンの値。radはそのまま返す。
    """
    return math.radians(value) if unit == "deg" else value


def _from_radians(value, unit):
    """ラジアンの数値を正規化済みの単位へ変換する。

    Args:
        value (float): ラジアンの角度。
        unit (str): ``"deg"`` または ``"rad"``。

    Returns:
        float: 指定単位の値。radはそのまま返す。
    """
    return math.degrees(value) if unit == "deg" else value


def _world_space(value):
    """boolの空間指定を検証する。

    Args:
        value (bool): Trueはワールド空間、Falseはローカル空間。

    Returns:
        bool: 検証済みの指定。

    Raises:
        TypeError: bool以外を指定した場合。
    """
    if type(value) is not bool:
        raise TypeError("worldSpace(ws)はboolで指定してください")
    return value


def _finite(value, name):
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
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name}は数値で指定してください")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name}は有限な数値で指定してください")
    return result


def _finite_vector(value, size, name):
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
    try:
        items = tuple(value)
    except TypeError:
        raise TypeError(f"{name}は{size}個の数値の並びで指定してください") from None
    if len(items) != size:
        raise ValueError(f"{name}は{size}個の成分で指定してください")
    return tuple(_finite(item, name) for item in items)


def _color_value(color):
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
    if color is None:
        return None, None
    if isinstance(color, bool):
        raise TypeError("colorはintの番号か(r, g, b)の並びかNoneで指定してください(boolは指定できません)")
    if isinstance(color, int):
        if not 0 <= color <= _MAX_COLOR_INDEX:
            raise ValueError(f"colorの番号は0〜{_MAX_COLOR_INDEX}で指定してください: {color}")
        return color, None
    if isinstance(color, (str, bytes)) or not hasattr(color, "__iter__"):
        raise TypeError("colorはintの番号か(r, g, b)の並びかNoneで指定してください")
    rgb = _finite_vector(color, 3, "color")
    if not all(0.0 <= value <= 1.0 for value in rgb):
        raise ValueError("colorのRGBの各成分は0〜1で指定してください")
    return None, rgb


def _checked_tolerance(value, *, positive=False):
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
    result = _finite(value, "tolerance")
    if positive and result <= 0:
        raise ValueError("toleranceは正の値で指定してください")
    if result < 0:
        raise ValueError("toleranceは0以上で指定してください")
    return result


def _checked_digits(ndigits):
    """丸めの桁数を検証する。

    Args:
        ndigits (int | None): 小数点以下の桁数。負の値は整数部を丸める。Noneは整数へ丸める。

    Returns:
        int | None: 検証済みの桁数。

    Raises:
        TypeError: int・None以外(boolを含む)の場合。
    """
    if ndigits is None:
        return None
    if isinstance(ndigits, bool) or not isinstance(ndigits, numbers.Integral):
        raise TypeError(f"ndigitsはintかNoneで指定してください: {ndigits!r}")
    return int(ndigits)


def _round_float(value, ndigits):
    """組み込みの ``round`` で丸め、-0.0 を 0.0 にそろえたfloatを返す。

    Args:
        value (float): 丸める値。
        ndigits (int | None): :func:`_checked_digits` で検証済みの桁数。

    Returns:
        float: 丸めた値。
    """
    result = float(round(value, ndigits))
    return 0.0 if result == 0.0 else result


def _unique_ordered(items, key=None):
    """最初の出現順を保ったまま重複を除く。

    Args:
        items (Iterable[object]): 要素列。keyを省略する場合はハッシュ可能な要素。
        key (callable | None): 重複判定に使うキーを返す関数。Noneは要素自身。

    Returns:
        list: 最初の出現順を維持した要素。
    """
    seen = set()
    result = []
    for item in items:
        marker = item if key is None else key(item)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def _rethrow_init_error(cls, error):
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
    raise TypeError(f"{cls.__name__}() {str(error).split('() ', 1)[-1]}") from None


class _PointGrid:
    """最も近い点を探すための一様な格子(標準ライブラリだけで計算する)。

    格子の大きさは、点が広がる範囲の対角線と点の数から決める。探すときは、調べたい点が入る格子から
    外側へ広げていく。見つかった点より近い点が、それより外側の格子に無いと分かった時点で終える。

    Args:
        points (Sequence[Sequence[float]]): 3成分の点の並び。空でないこと。
    """

    def __init__(self, points):
        self.points = [tuple(float(value) for value in point) for point in points]
        if not self.points:
            raise ValueError("pointsは空にできません")
        lows = [min(point[axis] for point in self.points) for axis in range(3)]
        highs = [max(point[axis] for point in self.points) for axis in range(3)]
        diagonal = math.sqrt(sum((high - low) ** 2 for low, high in zip(lows, highs))) or 1.0
        # 1つの格子に数点が入る大きさにする。
        self.size = max(diagonal / max(1.0, len(self.points) ** (1.0 / 3.0)), 1e-6)
        self.cells = {}
        for index, point in enumerate(self.points):
            self.cells.setdefault(self._cell(point), []).append(index)
        self.lows = [math.floor(low / self.size) for low in lows]
        self.highs = [math.floor(high / self.size) for high in highs]

    def nearest(self, point, maxDistance=None):
        """最も近い点の番号と距離を返す。

        Args:
            point (Sequence[float]): 3成分の問い合わせ点。
            maxDistance (float | None): これより遠い点は探さない。Noneは制限なし。

        Returns:
            tuple[int | None, float]: 点の番号と距離。maxDistance内に無ければ ``(None, inf)``。
        """
        point = tuple(float(value) for value in point)
        base = self._cell(point)
        # 問い合わせ点から、全ての点を含む範囲の格子まで届く輪の数。
        reach = max(max(abs(base[axis] - self.lows[axis]), abs(base[axis] - self.highs[axis])) for axis in range(3))
        if maxDistance is not None:
            reach = min(reach, int(math.ceil(maxDistance / self.size)))
        best, best_distance = None, math.inf
        limit = math.inf if maxDistance is None else maxDistance * maxDistance
        for radius in range(reach + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    for dz in range(-radius, radius + 1):
                        if max(abs(dx), abs(dy), abs(dz)) != radius:
                            continue
                        for index in self.cells.get((base[0] + dx, base[1] + dy, base[2] + dz), ()):
                            distance = sum((a - b) ** 2 for a, b in zip(self.points[index], point))
                            if distance < best_distance and distance <= limit:
                                best, best_distance = index, distance
            # 見つかった点より近い点は、次の輪より外には無い。
            if best is not None and math.sqrt(best_distance) <= radius * self.size:
                break
        return best, math.sqrt(best_distance)

    def _cell(self, point):
        """座標を格子の番号にする。"""
        return tuple(int(math.floor(value / self.size)) for value in point)
