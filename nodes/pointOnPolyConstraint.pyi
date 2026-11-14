# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の pointOnPolyConstraint を扱う。"""

from .constraint import Constraint



class PointOnPolyConstraint(Constraint):
    """ポリゴンの表面上の点へコンストレイントするpointOnPolyConstraintを扱うクラス。"""
