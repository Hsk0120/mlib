# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""点を順につないだjointのチェーンを作り、jointのlistを返す。

各jointは次の点へ向ける。aimAxis を次の点へ、upAxis を up の向きへ向ける(最後のjointは1つ前と同じ向き)。
向きは jointOrient に入れ、rotate は0にする。
``cmds.joint`` で1つずつ作って ``orientJoint`` で向きを揃える手順を、1回で行う。

.. code-block:: python

    import mlib
    from mlib.cmds.createJointChain import createJointChain

    joints = createJointChain([(0, 10, 0), (5, 10, -1), (10, 10, 0)], aimAxis="x", upAxis="y",
                              up=(0, 0, -1), names=["arm_JNT", "elbow_JNT", "wrist_JNT"])
"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.object import Object
from ..decorator import undoChunk
from ..maths.matrix import Matrix
from ..util import _finite_vector
from typing import Iterable, Sequence
from mlib.nodes.joint import Joint
from mlib.nodes.node import Node

_AXES: dict

def _axis(value: str, label: str) -> tuple[int, float]:
    """軸の名前を確かめ、(軸の番号, 符号) を返す。

    Args:
        value (str): ``"x"``・``"y"``・``"z"``・``"-x"``・``"-y"``・``"-z"``。
        label (str): 例外メッセージに使う引数名。

    Returns:
        tuple[int, float]: 軸の番号(0〜2)と符号。

    Raises:
        TypeError: 文字列でない場合。
        ValueError: 対応しない名前の場合。
    """
    ...

def createJointChain(points: Iterable[Sequence[float]], *, aimAxis: str = ..., upAxis: str = ..., up: Sequence[float] = ..., names: Sequence[str] | None = ..., parent: str | Node | None = ...) -> list[Joint]:
    """点を順につないだjointのチェーンを作る。

    1つ目のjointは parent の子に、2つ目からは1つ前のjointの子に作る。

    - 各jointの aimAxis を、次の点へ向ける。
    - upAxis は、up を aim に垂直にした向きへ向ける。
    - 最後のjointは、1つ前のjointと同じ向きにする。

    向きは jointOrient に入れ、rotate・rotateAxis は0のままにする。
    親がjointなら、inverseScale を親の scale へ接続する。
    選択は変えない。fast引数は無い。Undoが有効なら1回で戻せる。

    Args:
        points (Iterable[Sequence[float]]): ワールド空間の位置(cm)の並び。2点以上で、隣り合う点は別の位置にする。
        aimAxis (str): 次の点へ向ける軸。``"x"`` (既定)・``"y"``・``"z"``・``"-x"``・``"-y"``・``"-z"``。
        upAxis (str): up の向きへ向ける軸。aimAxis と別の軸にする。既定は ``"y"``。
        up (Sequence[float]): ワールド空間で、上の向きの目安。既定は ``(0, 1, 0)``。
        names (Sequence[str] | None): jointの名前。points と同じ数だけ指定する。
            Noneなら ``joint#`` (Mayaの連番)。
        parent (str | Node | None): 1つ目のjointの親のtransform。Noneならワールド。

    Returns:
        list[Joint]: 作ったjoint。points の順に並ぶ。

    Raises:
        TypeError: points・up の成分が数値でない場合、aimAxis・upAxis が文字列でない場合、
            names が文字列の並びでもNoneでもない場合、または parent がtransformでない場合。
        ValueError: 点が2つ未満の場合、隣り合う点が同じ位置の場合、軸の名前が正しくないか同じ軸の場合、
            names の数が points と違うか空の名前を含む場合、up が0の場合、
            または up が向ける方向とほぼ平行な場合。
        RuntimeError: parent の名前のノードが無い場合、またはMayaが作成を拒否した場合。

    Note:
        parent のスケールが1でない場合も、位置と向きは parent のワールドのマトリクスで換算する。
        ただし、segmentScaleCompensate による補正は考えに入れない。
    """
    ...
