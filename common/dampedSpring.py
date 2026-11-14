"""減衰のあるばねの動きを、決まった時間の刻みで計算する。"""

import math


class DampedSpring:
    """ベイク用の数値計算。結果は再生の履歴によらず、毎回同じになる。"""

    @staticmethod
    def solve(samples, secondsPerSample, frequency=3.0, damping=0.5, limit=45.0):
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
        rows = [tuple(float(v) for v in row) for row in samples]
        if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("同じ長さの、空でないサンプルを指定してください")
        if not all(math.isfinite(v) for row in rows for v in row):
            raise ValueError("サンプルは有限な数値で指定してください")
        if not all(math.isfinite(v) for v in (secondsPerSample, frequency, damping, limit)):
            raise ValueError("設定は有限な数値で指定してください")
        if not (secondsPerSample > 0 and 0 < frequency <= 30 and 0 <= damping <= 2 and limit > 0):
            raise ValueError("スプリングの設定が不正です")
        omega = 2 * math.pi * frequency
        count = max(1, int(math.ceil(secondsPerSample * omega * 20)))
        if count > 10000:
            raise ValueError("サンプルの間隔が大きすぎます")
        dt = secondsPerSample / count
        position, velocity = list(rows[0]), [0.0] * len(rows[0])
        result = [tuple(position)]
        for before, after in zip(rows, rows[1:]):
            for step in range(1, count + 1):
                alpha = step / count
                for axis in range(len(position)):
                    goal = before[axis] + (after[axis] - before[axis]) * alpha
                    acceleration = omega * omega * (goal - position[axis]) - 2 * damping * omega * velocity[axis]
                    velocity[axis] += acceleration * dt
                    position[axis] += velocity[axis] * dt
                    bounded = max(goal - limit, min(goal + limit, position[axis]))
                    if bounded != position[axis]:
                        position[axis], velocity[axis] = bounded, 0.0
            result.append(tuple(position))
        return result
