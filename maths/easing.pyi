# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
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
from typing import Callable

__all__ = ['CURVES', 'ease']
_EXPONENTIAL_STEEPNESS: float

def _rising_power(degree: int) -> Callable[[float], float]:
    """u を degree 乗する、立ち上がり側の半分の曲線を作る。

    Args:
        degree (int): 多項式の次数。

    Returns:
        Callable[[float], float]: [0, 1] を [0, 1] へ変換する、単調に増える関数。
    """
    ...

def _rising_exponential(u: float) -> float:
    """指数関数を 0→0、1→1 になるよう正規化した、立ち上がり側の半分の曲線。

    ``(e^(k*u) - 1) / (e^k - 1)`` を ``math.expm1`` で求めるので、0 の近くでも
    桁落ちしない。両端は正規化により、ちょうど 0 と 1 になる。

    Args:
        u (float): [0, 1] の値。

    Returns:
        float: [0, 1] の値。
    """
    ...

def _rising_circular(u: float) -> float:
    """中心 (0, 1)・半径 1 の円のうち、(0, 0) から (1, 1) までの 1/4 の弧。

    u = 0 で接線が水平、u = 1 で接線が垂直(傾きが無限大)になる。

    Args:
        u (float): [0, 1] の値。

    Returns:
        float: [0, 1] の値。
    """
    ...

def _symmetric(rising: Callable[[float], float]) -> Callable[[float], float]:
    """立ち上がり側の半分の曲線から、点 (0.5, 0.5) について対称な曲線を組み立てる。

    前半 [0, 0.5] は、半分の曲線を縦横 1/2 に縮めたもの。後半 [0.5, 1] は、前半を
    点 (0.5, 0.5) のまわりに 180 度回したものになる。

    Args:
        rising (Callable[[float], float]): f(0) == 0、f(1) == 1 の、単調に増える関数。

    Returns:
        Callable[[float], float]: [0, 1] で使える対称な曲線。
    """
    ...

def _linear(t: float) -> float:
    """入力をそのまま返す恒等曲線。比較や、強弱を付けない指定に使う。

    Args:
        t (float): (0, 1) の値。

    Returns:
        float: t と同じ値。
    """
    ...

def _smoothstep(t: float) -> float:
    """両端の傾きが 0 になる 3 次エルミート補間 ``3t^2 - 2t^3``。

    Args:
        t (float): (0, 1) の値。

    Returns:
        float: (0, 1) の値。
    """
    ...

def _sine(t: float) -> float:
    """正弦の -90〜90 度を 0〜1 へ変換した曲線 ``(1 + sin(pi * (t - 0.5))) / 2``。

    中央の t = 0.5 では sin(0) を計算するので、中央の値は丸め誤差なく 0.5 になる。

    Args:
        t (float): (0, 1) の値。

    Returns:
        float: (0, 1) の値。
    """
    ...
_SHAPES: dict
CURVES: tuple

def _to_progress(t: float) -> float:
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
    ...

def ease(t: float, curve: str = ...) -> float:
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
    ...
