# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""点の並びに近い3次B-splineの制御点を求める(外部の数値計算ライブラリは使わない)。"""

import math
from typing import Sequence



class CurveFit:
    """3次カーブを点の並びへ当てはめる(フィットする)。

    ノットは等間隔で両端を固定した形(clamped knot)にし、正則化した最小二乗法で求める。
    """
    @staticmethod
    def basis(count: int, parameter: float) -> list[float]:
        """0〜1のパラメータでの、各CVの基底のウェイトを計算する。

        Args:
            count (int): CVの数。4以上。
            parameter (float): カーブのパラメータ。0〜1に正規化した値。

        Returns:
            list[float]: CVごとのウェイト。

        Raises:
            ValueError: countが4より小さい場合、またはparameterが0〜1の範囲にない場合。
        """
        ...
    @classmethod
    def fit(cls, points: Sequence[Sequence[float]], count: int) -> list[list[float]]:
        """点の並びに近いカーブのCVを求める。

        カーブのパラメータには、点を結んだ折れ線の長さ(弦長)を使う。

        Args:
            points (Sequence[Sequence[float]]): 3次元の点。2点以上。すべて同じ空間・同じ単位にする。
            count (int): CVの数。4〜32。

        Returns:
            list[list[float]]: CVの座標。pointsと同じ空間・同じ単位。

        Raises:
            ValueError: countが4〜32のintでない場合(intでないものも含む)、点が2つより少ないか
                有限な3次元の点でない場合、または折れ線の長さが0の場合。

        Note:
            点が少ないときは、CVを直線上に並べる方向へ弱く寄せる(正則化する)。
            折れた角や弧の長さが、元の点の並びと完全に一致することは保証しない。
        """
        ...
