"""Maya の orientConstraint を扱う。"""

from .interpCacheConstraint import _InterpCacheConstraint


class OrientConstraint(_InterpCacheConstraint):
    """回転をコンストレイントするorientConstraintを扱うクラス。

    補間のキャッシュ(``createCache``・``deleteCache``)を持つ。
    """
