"""Maya の poleVectorConstraint を扱う。"""

from .pointConstraint import PointConstraint


class PoleVectorConstraint(PointConstraint):
    """RP IKハンドルのポールベクトルをコンストレイントするクラス。

    Mayaのノード型ではpoleVectorConstraintはpointConstraintの派生型になっている。
    そのため、このクラスもPointConstraintを基底にする。
    """
