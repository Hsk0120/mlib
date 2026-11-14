# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Jointの親を直接付け替える処理。回転のチャンネルとSSC(セグメントスケール補正)を保つ。"""

import maya.api.OpenMaya as om2
from .fastWrite import require_writable
from .nodeEdit import require_editable
from mlib.nodes.joint import Joint
from mlib.nodes.transform import Transform


def reparent_plan(joint: Joint, parent: Transform | None) -> tuple:
    """Jointの親を付け替えるための計画を作る。

    cmds.parentが補正用の中間Transformを入れずに済む場合だけを扱う。
    書き込む前に必要な値をすべて求め、書き込めるかどうかも確かめておく。

    Args:
        joint (Joint): 移動するJoint。
        parent (Transform | None): 新しい親。Noneならワールド直下。

    Returns:
        tuple: (対象, 親, translate, jointOrient, 新しいinverseScaleの入力)。

    Raises:
        ValueError: 新しい親のマトリクスが特異な(逆マトリクスを持たない)場合、
            またはSSCで補正する親のスケールが0の場合。
        RuntimeError: Jointや新しい親を編集できない場合、translate・jointOrientへ書き込めない場合、
            またはinverseScaleがロックされているか成分ごとに接続されている場合。
        NotImplementedError: インスタンスの場合、inverseScaleに独自の入力がある場合、
            または補正用のTransformが必要な場合。
    """
    ...

def reparent(plan: tuple) -> None:
    """計画に従ってJointの親を付け替える。

    付け替えた後、inverseScaleの接続と姿勢を元どおりにする。

    Args:
        plan (tuple): reparent_planが返した計画。

    Returns:
        None: 値を返さない。
    """
    ...
