"""点の並びに近い3次B-splineの制御点を求める(外部の数値計算ライブラリは使わない)。"""

import math


class CurveFit:
    """3次カーブを点の並びへ当てはめる(フィットする)。

    ノットは等間隔で両端を固定した形(clamped knot)にし、正則化した最小二乗法で求める。
    """

    @staticmethod
    def basis(count, parameter):
        """0〜1のパラメータでの、各CVの基底のウェイトを計算する。

        Args:
            count (int): CVの数。4以上。
            parameter (float): カーブのパラメータ。0〜1に正規化した値。

        Returns:
            list[float]: CVごとのウェイト。

        Raises:
            ValueError: countが4より小さい場合、またはparameterが0〜1の範囲にない場合。
        """
        if count < 4 or not 0 <= parameter <= 1:
            raise ValueError("countは4以上、parameterは0〜1で指定してください")
        if parameter == 1:
            return [0.0] * (count - 1) + [1.0]
        knots = [0.0] * 4 + [i / (count - 3) for i in range(1, count - 3)] + [1.0] * 4
        weights = [float(knots[i] <= parameter < knots[i + 1]) for i in range(len(knots) - 1)]
        for degree in range(1, 4):
            result = []
            for i in range(len(weights) - 1):
                left = knots[i + degree] - knots[i]
                right = knots[i + degree + 1] - knots[i + 1]
                result.append(
                    (weights[i] * (parameter - knots[i]) / left if left else 0) + (weights[i + 1] * (knots[i + degree + 1] - parameter) / right if right else 0)
                )
            weights = result
        return weights

    @classmethod
    def fit(cls, points, count):
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
        if type(count) is not int or not 4 <= count <= 32 or len(points) < 2:
            raise ValueError("点は2個以上、コントロールは4〜32個で指定してください")
        if any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in points):
            raise ValueError("有限な3Dの点を指定してください")
        distances = [0.0]
        for a, b in zip(points, points[1:]):
            distances.append(distances[-1] + math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b))))
        if distances[-1] <= 1e-10:
            raise ValueError("点の並びの長さが0です")
        basis = [cls.basis(count, d / distances[-1]) for d in distances]
        matrix = [[0.0] * (count + 3) for _ in range(count)]
        for row, point in zip(basis, points):
            for i in range(count):
                for j in range(count):
                    matrix[i][j] += row[i] * row[j]
                for axis in range(3):
                    matrix[i][count + axis] += row[i] * point[axis]
        for i in range(count):
            matrix[i][i] += 1e-7
            for axis in range(3):
                matrix[i][count + axis] += 1e-7 * (points[0][axis] + (points[-1][axis] - points[0][axis]) * i / (count - 1))
        for col in range(count):
            pivot = max(range(col, count), key=lambda r: abs(matrix[r][col]))
            matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
            scale = matrix[col][col]
            matrix[col] = [v / scale for v in matrix[col]]
            for row in range(count):
                if row != col:
                    scale = matrix[row][col]
                    matrix[row] = [a - scale * b for a, b in zip(matrix[row], matrix[col])]
        result = [row[count:] for row in matrix]
        result[0], result[-1] = list(points[0]), list(points[-1])
        return result
