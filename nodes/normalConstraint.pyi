# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の normalConstraint を扱う。"""

from .constraint import Constraint



class NormalConstraint(Constraint):
    """ターゲットの表面の法線の方向へ向けるnormalConstraintを扱うクラス。"""
