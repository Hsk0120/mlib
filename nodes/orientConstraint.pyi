# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の orientConstraint を扱う。"""

from .interpCacheConstraint import _InterpCacheConstraint



class OrientConstraint(_InterpCacheConstraint):
    """回転をコンストレイントするorientConstraintを扱うクラス。

    補間のキャッシュ(``createCache``・``deleteCache``)を持つ。
    """
