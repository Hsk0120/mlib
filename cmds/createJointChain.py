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

#: aimAxis・upAxis に指定できる軸の名前と、(軸の番号, 符号)。
_AXES = {"x": (0, 1.0), "y": (1, 1.0), "z": (2, 1.0), "-x": (0, -1.0), "-y": (1, -1.0), "-z": (2, -1.0)}


def _axis(value, label):
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
    if not isinstance(value, str):
        raise TypeError(f"{label}は文字列で指定してください")
    if value.lower() not in _AXES:
        raise ValueError(f"{label}は{', '.join(_AXES)}のどれかで指定してください: {value!r}")
    return _AXES[value.lower()]


def createJointChain(points, *, aimAxis="x", upAxis="y", up=(0, 1, 0), names=None, parent=None):
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
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.joint import Joint
    from ..nodes.node import Node
    from ..nodes.transform import Transform

    if isinstance(points, (str, bytes)):
        raise TypeError("pointsは3Dの位置の並びで指定してください")
    try:
        items = list(points)
    except TypeError:
        raise TypeError("pointsは3Dの位置の並びで指定してください") from None
    positions = [om2.MVector(*_finite_vector(item, 3, "points")) for item in items]
    if len(positions) < 2:
        raise ValueError(f"pointsには位置を2つ以上指定してください: {len(positions)}個")
    aim_axis = _axis(aimAxis, "aimAxis")
    up_axis = _axis(upAxis, "upAxis")
    if aim_axis[0] == up_axis[0]:
        raise ValueError(f"aimAxisとupAxisは別の軸で指定してください: {aimAxis!r}, {upAxis!r}")
    up_vector = om2.MVector(*_finite_vector(up, 3, "up"))
    if up_vector.length() <= 1e-12:
        raise ValueError("upに0のベクトルは指定できません")
    up_vector.normalize()
    if names is not None:
        if isinstance(names, str):
            raise TypeError("namesは文字列の並びかNoneで指定してください")
        names = list(names)
        if not all(isinstance(name, str) for name in names):
            raise TypeError("namesは文字列の並びかNoneで指定してください")
        if len(names) != len(positions):
            raise ValueError(f"namesは{len(positions)}個で指定してください: {len(names)}個")
        if not all(names):
            raise ValueError("namesに空の文字列は指定できません")
    parent_node = None
    if parent is not None:
        parent_node = Node(Object._input_name(parent))
        if not isinstance(parent_node, Transform):
            raise TypeError(f"parentはtransformで指定してください: {parent_node.getFullName()}")
    rotations = []
    for index, position in enumerate(positions[:-1]):
        aim = positions[index + 1] - position
        if aim.length() <= 1e-9:
            raise ValueError(f"点{index}と点{index + 1}が同じ位置にあります")
        try:
            rotation = Matrix.fromAim(aim, up_vector, aimAxis=aimAxis.lower(), upAxis=upAxis.lower())
        except ValueError:
            raise ValueError(f"upが、点{index}から点{index + 1}への方向と平行です") from None
        rotations.append(rotation)
    rotations.append(rotations[-1])
    unit = om2.MDistance.uiUnit()
    angle = om2.MAngle.uiUnit()
    with undoChunk("mlibCreateJointChain"):
        parent_name = parent_node.getFullName() if parent_node is not None else None
        parent_matrix = parent_node.getMatrix(worldSpace=True) if parent_node is not None else om2.MMatrix()
        created = []
        for index, (position, rotation) in enumerate(zip(positions, rotations)):
            flags = {"skipSelect": True}
            if names is not None:
                flags["name"] = names[index]
            if parent_name is not None:
                flags["parent"] = parent_name
            joint = cmds.ls(cmds.createNode("joint", **flags), long=True)[0]
            if parent_name is not None and cmds.nodeType(parent_name) == "joint":
                cmds.connectAttr(parent_name + ".scale", joint + ".inverseScale")
            world = om2.MMatrix(rotation)
            world.setElement(3, 0, position.x)
            world.setElement(3, 1, position.y)
            world.setElement(3, 2, position.z)
            local = om2.MTransformationMatrix(world * om2.MMatrix(parent_matrix).inverse())
            translation = local.translation(om2.MSpace.kTransform)
            orient = local.rotation()
            orient.reorderIt(om2.MEulerRotation.kXYZ)
            cmds.setAttr(joint + ".translate", *(om2.MDistance(value).asUnits(unit) for value in translation))
            cmds.setAttr(joint + ".jointOrient", *(om2.MAngle(value).asUnits(angle) for value in orient))
            created.append(joint)
            parent_name = joint
            parent_matrix = world
        return [Joint(joint) for joint in created]
