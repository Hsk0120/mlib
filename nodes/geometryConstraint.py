"""Maya の geometryConstraint を扱う。"""

from .constraint import Constraint


class GeometryConstraint(Constraint):
    """ターゲットの表面上の位置へコンストレイントするクラス。"""
