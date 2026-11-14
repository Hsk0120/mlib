"""Maya の normalConstraint を扱う。"""

from .constraint import Constraint


class NormalConstraint(Constraint):
    """ターゲットの表面の法線の方向へ向けるnormalConstraintを扱うクラス。"""
