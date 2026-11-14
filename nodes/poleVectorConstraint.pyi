# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の poleVectorConstraint を扱う。"""

from .pointConstraint import PointConstraint



class PoleVectorConstraint(PointConstraint):
    """RP IKハンドルのポールベクトルをコンストレイントするクラス。

    Mayaのノード型ではpoleVectorConstraintはpointConstraintの派生型になっている。
    そのため、このクラスもPointConstraintを基底にする。
    """
