"""NURBS カーブの CV と CV コレクション。"""

from ..core.geometryEdit import command_indices
from .pointComponent import PointComponent, PointComponents


class CV(PointComponent):
    """NURBSカーブのCV1つを表すクラス。

    NurbsCurveのShapeと、OpenMayaでのCVの番号を持つ。
    NurbsSurfaceのCV(番号が2つあるもの)は扱わない(SurfaceCVを使う)。

    周期カーブでも、番号はnumCVsの範囲のAPIの番号で持つ。
    cmdsへ渡す名前では、末尾で重なっているCVを、先頭側の同じCVの番号に直す。
    """

    shape_type = "nurbsCurve"
    component_type = "cv"
    count_attribute = "getNumCVs"

    def getFullName(self):
        """cmdsへ渡すCVの名前を返す。

        周期カーブの末尾で重なっているCVは、先頭側の同じCVの番号に直す。

        Returns:
            str: 同じ位置を編集できるMayaのコンポーネント名。indexはAPIの番号のまま変わらない。
        """
        self._require_valid()
        index = command_indices(self.shape, [self.index])[0]
        return f"{self.shape.getFullName()}.cv[{index}]"


class CVs(PointComponents):
    """同じNURBSカーブにあるCVの集まりを表すクラス。

    CVを1つずつ取り出したり、座標をまとめて扱ったりする。
    番号はOpenMayaの番号で、持っている順を保つ。

    周期カーブの末尾と先頭のCVは、APIでは別の番号として持てる。
    ただしcmdsへ渡す名前では、同じCVの番号になることがある。そのため、名前は範囲にまとめない。
    """

    component_class = CV

    def getFullNames(self):
        """cmdsへ渡すCVの名前を、持っている順に返す。

        周期カーブの末尾で重なっているCVは、先頭側の同じCVの名前になる。

        Returns:
            list[str]: 持っている順のMayaのコンポーネント名。indicesはAPIの番号のまま変わらない。

        Raises:
            TypeError: シェイプの種類がNurbsCurveでない場合。
            IndexError: 持っている番号が、今のCVの範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        self._require_valid()
        name = self.shape.getFullName()
        return [f"{name}.cv[{index}]" for index in command_indices(self.shape, self.indices)]

    def getCompactNames(self):
        """cmdsへ渡すCVの名前を返す。

        周期カーブのCVの対応を保つため、範囲にはまとめない。

        Returns:
            list[str]: getFullNamesと同じ、持っている順のMayaのコンポーネント名。

        Raises:
            TypeError: シェイプの種類がNurbsCurveでない場合。
            IndexError: 持っている番号が、今のCVの範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        return self.getFullNames()

    def _repr_indices(self):
        """reprに表示する番号を、cmdsで使うCVの番号に直して返す。

        周期カーブの末尾で重なっているCVは、先頭側のCVと同じ名前になるので、表示では重なりを除く。

        Returns:
            list[int]: 表示用の番号。持っている順に並び、重なりは除く。
        """
        return list(dict.fromkeys(command_indices(self.shape, self.indices)))
