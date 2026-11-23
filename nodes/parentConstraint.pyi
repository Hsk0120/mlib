# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の parentConstraint を扱う。"""

from .interpCacheConstraint import _InterpCacheConstraint



class ParentConstraint(_InterpCacheConstraint):
    """位置と回転をコンストレイントするparentConstraintを扱うクラス。

    補間のキャッシュ(``createCache``・``deleteCache``)を持つ。
    """
