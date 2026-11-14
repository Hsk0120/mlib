# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""減衰のあるばねの動きを、決まった時間の刻みで計算する。"""

import math
from typing import Sequence



class DampedSpring:
    """ベイク用の数値計算。結果は再生の履歴によらず、毎回同じになる。"""
    @staticmethod
    def solve(samples: Sequence[Sequence[float]], secondsPerSample: float, frequency: float = ..., damping: float = ..., limit: float = ...) -> list[tuple[float]]:
        """目標の値の並びを追いかけるばねの動きを、先頭から計算する。

        Args:
            samples (Sequence[Sequence[float]]): 同じ時間の間隔で並んだ目標の値。成分ごとに別々に計算する。
            secondsPerSample (float): サンプルの間隔(秒)。
            frequency (float): 固有振動数(Hz)。0より大きく30以下。
            damping (float): 減衰比。0〜2。1で臨界減衰になる。
            limit (float): 目標から離れてよい最大の差。正の値。

        Returns:
            list[tuple[float]]: 各目標へ遅れて追いかけた結果。

        Raises:
            ValueError: samplesが空か、成分の数がそろわないか、有限でない場合。
                設定の値が有限でないか範囲外の場合。
                またはsecondsPerSampleが大きすぎて、内部の刻みの数が10000を超える場合。

        Note:
            最初の位置は先頭の目標、最初の速度は0。サンプルの間を細かく刻み、
            半陰的Euler法で計算する。回転に使う場合、角度の折り返し(360度で戻すなど)は呼び出す側で行う。
        """
        ...
