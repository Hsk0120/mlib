"""Maya の parentConstraint を扱う。"""

from .interpCacheConstraint import _InterpCacheConstraint


class ParentConstraint(_InterpCacheConstraint):
    """位置と回転をコンストレイントするparentConstraintを扱うクラス。

    補間のキャッシュ(``createCache``・``deleteCache``)を持つ。
    """
