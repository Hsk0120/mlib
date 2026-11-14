"""進行度 0〜1 を、両端でゆるやかに変わる値へ変換するイージング曲線(左右対称)。

公開するのは、曲線名を指定して計算する :func:`ease` と、指定できる曲線名の
一覧 :data:`CURVES` だけ。どの曲線も、次の性質がそろっている。

- 入力は区間 [0, 1] に切り詰めてから計算する。
- 0 と 1 では誤差なく ``0.0`` と ``1.0`` を返す。
- 点 (0.5, 0.5) について点対称で、丸め誤差の範囲で
  ``ease(1 - t) == 1 - ease(t)`` が成り立つ。中央では正確に ``0.5`` を返す。
- 区間全体で単調に増加する。

多くの曲線は、「立ち上がり側の半分」だけを 0→1 の関数として決める。
区間の前半ではそれを縦横 1/2 に縮めて使い、後半ではそれを点対称に移したものを使う。
標準ライブラリの ``math`` 以外は使わない(Maya が無くても動く)。

Examples:
    >>> from mlib.maths import easing
    >>> easing.ease(0.25)
    0.0625
    >>> easing.ease(0.5, "sine")
    0.5
    >>> "exponential" in easing.CURVES
    True
"""

import math

# importlib.reload(mlib.reload() を含む)はモジュールの辞書を引き継ぐので、
# 古い版が公開していた ease_in_out_* 関数を、実行中のセッションからも取り除く。
for _stale_name in [name for name in globals() if name.startswith("ease_in_out_")]:
    del globals()[_stale_name]
globals().pop("_stale_name", None)

__all__ = ["CURVES", "ease"]


# exponential 曲線の立ち上がりの急さ。値が大きいほど両端が平らになり中央が急になる。
_EXPONENTIAL_STEEPNESS = 7.0


def _rising_power(degree):
    """u を degree 乗する、立ち上がり側の半分の曲線を作る。

    Args:
        degree (int): 多項式の次数。

    Returns:
        Callable[[float], float]: [0, 1] を [0, 1] へ変換する、単調に増える関数。
    """

    def rising(u):
        return u**degree

    return rising


def _rising_exponential(u):
    """指数関数を 0→0、1→1 になるよう正規化した、立ち上がり側の半分の曲線。

    ``(e^(k*u) - 1) / (e^k - 1)`` を ``math.expm1`` で求めるので、0 の近くでも
    桁落ちしない。両端は正規化により、ちょうど 0 と 1 になる。

    Args:
        u (float): [0, 1] の値。

    Returns:
        float: [0, 1] の値。
    """
    return math.expm1(_EXPONENTIAL_STEEPNESS * u) / math.expm1(_EXPONENTIAL_STEEPNESS)


def _rising_circular(u):
    """中心 (0, 1)・半径 1 の円のうち、(0, 0) から (1, 1) までの 1/4 の弧。

    u = 0 で接線が水平、u = 1 で接線が垂直(傾きが無限大)になる。

    Args:
        u (float): [0, 1] の値。

    Returns:
        float: [0, 1] の値。
    """
    return 1.0 - math.sqrt(1.0 - u * u)


def _symmetric(rising):
    """立ち上がり側の半分の曲線から、点 (0.5, 0.5) について対称な曲線を組み立てる。

    前半 [0, 0.5] は、半分の曲線を縦横 1/2 に縮めたもの。後半 [0.5, 1] は、前半を
    点 (0.5, 0.5) のまわりに 180 度回したものになる。

    Args:
        rising (Callable[[float], float]): f(0) == 0、f(1) == 1 の、単調に増える関数。

    Returns:
        Callable[[float], float]: [0, 1] で使える対称な曲線。
    """

    def shape(t):
        if t <= 0.5:
            return 0.5 * rising(2.0 * t)
        return 1.0 - 0.5 * rising(2.0 * (1.0 - t))

    return shape


def _linear(t):
    """入力をそのまま返す恒等曲線。比較や、強弱を付けない指定に使う。

    Args:
        t (float): (0, 1) の値。

    Returns:
        float: t と同じ値。
    """
    return t


def _smoothstep(t):
    """両端の傾きが 0 になる 3 次エルミート補間 ``3t^2 - 2t^3``。

    Args:
        t (float): (0, 1) の値。

    Returns:
        float: (0, 1) の値。
    """
    return t * t * (3.0 - 2.0 * t)


def _sine(t):
    """正弦の -90〜90 度を 0〜1 へ変換した曲線 ``(1 + sin(pi * (t - 0.5))) / 2``。

    中央の t = 0.5 では sin(0) を計算するので、中央の値は丸め誤差なく 0.5 になる。

    Args:
        t (float): (0, 1) の値。

    Returns:
        float: (0, 1) の値。
    """
    return 0.5 + 0.5 * math.sin(math.pi * (t - 0.5))


# 曲線名と計算する関数の対応。書いた順がそのまま CURVES の順番になる。
_SHAPES = {
    "linear": _linear,
    "smoothstep": _smoothstep,
    "sine": _sine,
    "circular": _symmetric(_rising_circular),
    "quadratic": _symmetric(_rising_power(2)),
    "cubic": _symmetric(_rising_power(3)),
    "quartic": _symmetric(_rising_power(4)),
    "quintic": _symmetric(_rising_power(5)),
    "exponential": _symmetric(_rising_exponential),
}

CURVES = tuple(_SHAPES)
"""tuple[str, ...]: :func:`ease` の ``curve`` に指定できる曲線名の一覧。

重複のない固定の並びなので、UI の選択肢などにそのまま並べて使える。
"""


def _to_progress(t):
    """進行度として渡された値を float に変換する。

    int・float のほか、``float()`` で数値にできる実数の型(``fractions.Fraction`` など)を受け付ける。
    文字列と組み込みの bool は、数値にできる内容でも受け付けない(間違って渡したものが、
    数値として通ってしまわないようにするため)。float で表せないほど大きな値は、
    符号に合わせて ``inf`` / ``-inf`` として扱う(呼び出し側で切り詰める)。

    Args:
        t (float): 進行度として渡された値。

    Returns:
        float: 変換した値。範囲の切り詰めはしない。

    Raises:
        TypeError: t が文字列・bool の場合、または ``float()`` で数値にできない値の場合。
        ValueError: t が NaN の場合。
    """
    if isinstance(t, (bool, str, bytes, bytearray)):
        raise TypeError(f"イージングの入力は実数で指定してください: {type(t).__name__}")
    try:
        value = float(t)
    except TypeError:
        raise TypeError(f"イージングの入力は実数で指定してください: {type(t).__name__}") from None
    except OverflowError:
        value = math.inf if t > 0 else -math.inf
    if math.isnan(value):
        raise ValueError("イージングの入力にNaNは指定できません")
    return value


def ease(t, curve="cubic"):
    """進行度 t を、指定したイージング曲線で変換した値を返す。

    t は [0, 1] に切り詰めてから計算するので、範囲の外の値を渡しても、
    戻り値はいつも [0, 1] に収まる。どの曲線でも ``ease(0) == 0.0``、
    ``ease(1) == 1.0`` で、点 (0.5, 0.5) について対称で、単調に増える。

    曲線ごとの形:

    - ``"linear"``: 変化なし(t をそのまま返す)。
    - ``"smoothstep"``: 3 次エルミート補間。両端の傾きが 0。
    - ``"sine"``: 正弦の半周期。smoothstep に近いなだらかな形。
    - ``"circular"``: 1/4 円弧を 2 つつないだ形。中央 t = 0.5 で接線が
      垂直になる(傾きが無限大)。
    - ``"quadratic"`` / ``"cubic"`` / ``"quartic"`` / ``"quintic"``:
      2〜5 次のべき乗を対称につないだ形。次数が高いほど両端が平らになる。
    - ``"exponential"``: 正規化した指数関数を対称につないだ形。

    Args:
        t (float): 進行度。int・float などの実数を受け付ける。文字列と組み込みの
            bool は数値として扱わない。
        curve (str): 曲線名。:data:`CURVES` のどれか。既定は ``"cubic"``。

    Returns:
        float: [0, 1] の値。

    Raises:
        TypeError: curve が文字列でない場合。または t が文字列・bool・None
            など、実数として扱えない値の場合。
        ValueError: curve が対応していない名前の場合。または t が NaN の場合。

    Examples:
        >>> ease(0.25, "quadratic")
        0.125
        >>> ease(-3.0, "quintic")
        0.0
        >>> ease(0.5, "circular")
        0.5
    """
    if not isinstance(curve, str):
        raise TypeError(f"イージングのカーブ名はstrで指定してください: {type(curve).__name__}")
    shape = _SHAPES.get(curve)
    if shape is None:
        raise ValueError(f"対応していないイージングのカーブです: {curve!r}({', '.join(CURVES)}のどれかを指定します)")
    value = _to_progress(t)
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return shape(value)
