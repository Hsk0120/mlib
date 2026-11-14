"""Maya の tangentConstraint を扱う。"""

from .constraint import Constraint


class TangentConstraint(Constraint):
    """NURBSカーブの接線の方向へ向けるtangentConstraintを扱うクラス。"""
