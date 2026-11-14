# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の tangentConstraint を扱う。"""

from .constraint import Constraint



class TangentConstraint(Constraint):
    """NURBSカーブの接線の方向へ向けるtangentConstraintを扱うクラス。"""
