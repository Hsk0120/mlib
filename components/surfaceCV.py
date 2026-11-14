"""NURBS曲面のCVと、CVの集まり。"""

import maya.api.OpenMaya as om2

from .component import _MultiIndexComponent, _MultiIndexComponents
from .pointComponent import PointComponent, PointComponents


def _surface_layout(shape):
    """曲面のCVの並び方を取得する。

    Args:
        shape (NurbsSurface): 型を確かめてある曲面。

    Returns:
        tuple[int, int, int, int]: (U方向のCV数, V方向のCV数, U方向の独立CV数, V方向の独立CV数)。
            独立CV数は、重なっているCVを数えない数。周期方向では ``CV数 - 次数`` になり、
            cmdsの ``cv[u][v]`` で使える番号の範囲と同じ。

    Raises:
        RuntimeError: 形状データを持たない空のシェイプの場合。
    """
    fn = shape._geometry_fn()
    count_u, count_v = fn.numCVsInU, fn.numCVsInV
    periodic = om2.MFnNurbsSurface.kPeriodic
    independent_u = count_u - fn.degreeInU if fn.formInU == periodic else count_u
    independent_v = count_v - fn.degreeInV if fn.formInV == periodic else count_v
    return count_u, count_v, independent_u, independent_v


class SurfaceCV(_MultiIndexComponent, PointComponent):
    """NURBS曲面のCV1つを表すクラス。

    NurbsSurfaceのShapeとCVの番号(``cv[u][v]``)を持ち、今のXYZ座標を取得・編集する。

    - 持っている :attr:`index` は、``u * V方向のCV数 + v`` の通し番号。
      :meth:`NurbsSurface.getCvPositions <mlib.nodes.nurbsSurface.NurbsSurface.getCvPositions>` の並びと同じになる。
      ``(u, v)`` は :meth:`getMultiIndex` で取得する。
    - 周期曲面でも、OpenMayaの番号(重なっているCVを含む)で持つ。
      cmdsへ渡す名前では、末尾で重なっているCVを、先頭側の同じCVの番号に直す。
      座標を書き込むと、重なっているCVも同じ位置になる。
    - 座標の取得・書き込み・反転は :class:`~mlib.components.pointComponent.PointComponent` と同じ。
    """

    shape_type = "nurbsSurface"
    component_type = "cv"
    index_size = 2

    @classmethod
    def _element_count(cls, shape):
        """曲面のCVの数(``U方向のCV数 * V方向のCV数``)を返す。

        Args:
            shape (NurbsSurface): 型を確かめてある曲面。

        Returns:
            int: CVの数。周期曲面で重なっているCVも数える。
        """
        count_u, count_v, _, _ = _surface_layout(shape)
        return count_u * count_v

    @classmethod
    def _multi_indices(cls, shape, indices, command=False):
        """通し番号を ``(u, v)`` へ変換する。

        Args:
            shape (NurbsSurface): 型を確かめてある曲面。
            indices (Iterable[int]): 範囲を確かめてある通し番号。
            command (bool): Trueならcmdsで使う番号にする(周期方向で重なっているCVを、先頭側の番号に直す)。
                既定はFalse。

        Returns:
            list[tuple[int, int]]: ``(u, v)``。指定した順に並ぶ。
        """
        _, count_v, independent_u, independent_v = _surface_layout(shape)
        result = []
        for index in indices:
            u, v = divmod(index, count_v)
            if command:
                u %= independent_u
                v %= independent_v
            result.append((u, v))
        return result

    @classmethod
    def _flat_indices(cls, shape, numbers):
        """``(u, v)`` を通し番号へ変換する。

        Args:
            shape (NurbsSurface): 型を確かめてある曲面。
            numbers (Iterable[tuple[int, int]]): 0以上の ``(u, v)``。

        Returns:
            list[int]: 通し番号。指定した順に並ぶ。

        Raises:
            IndexError: 番号がU・V方向のCV数の範囲の外にある場合。
        """
        count_u, count_v, _, _ = _surface_layout(shape)
        result = []
        for u, v in numbers:
            if u >= count_u or v >= count_v:
                raise IndexError(f"コンポーネントの番号が範囲外です: {(u, v)}")
            result.append(u * count_v + v)
        return result


class SurfaceCVs(_MultiIndexComponents, PointComponents):
    """同じNURBS曲面にあるCVの集まりを表すクラス。

    CVを1つずつ取り出したり、座標をまとめて扱ったりする。
    番号の指定には、通し番号と ``(u, v)`` を混ぜて使える。名前は範囲にまとめない。
    """

    component_class = SurfaceCV
