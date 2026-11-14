"""Jointの親を直接付け替える処理。回転のチャンネルとSSC(セグメントスケール補正)を保つ。"""

import maya.api.OpenMaya as om2

from .fastWrite import require_writable
from .nodeEdit import require_editable


def reparent_plan(joint, parent):
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
    # 循環参照の回避: maths は core を参照するため、使う時点で読み込む。
    from ..maths import Matrix
    from ..nodes.transform import Transform

    require_editable(joint.mnode())
    if om2.MFnDagNode(joint.mnode()).isInstanced():
        raise NotImplementedError("fastのジョイントの親子付けはインスタンスに対応していません")
    if parent is not None:
        require_editable(parent.mnode())
        parent_matrix = parent.getMatrix(worldSpace=True)
        if abs(parent_matrix.det4x4()) < 1e-12:
            raise ValueError("特異なトランスフォームの下へは親子付けできません")
    else:
        parent_matrix = Matrix()
    for name in ("translate", "jointOrient"):
        plug = joint.getPlug(name).mplug()
        require_writable(plug)
        for i in range(plug.numChildren()):
            require_writable(plug.child(i))
    inverse = joint.getPlug("inverseScale").mplug()
    old_source = inverse.connectedTo(True, False)
    old_parent = joint.getParent()
    if old_source and (old_parent is None or old_source[0] != old_parent.getPlug("scale").mplug()):
        raise NotImplementedError("fastのジョイントの親子付けは、独自のinverseScaleの入力を置き換えられません")
    if inverse.isLocked or any(inverse.child(i).isLocked or inverse.child(i).isDestination for i in range(inverse.numChildren())):
        raise RuntimeError("inverseScaleがロックされているか、軸ごとの入力があります")
    new_source = parent.getPlug("scale") if parent is not None and parent.isType("joint") else None
    inverse_value = tuple(new_source.get()) if new_source is not None else (1.0, 1.0, 1.0)
    if joint.getSegmentScaleCompensate() and any(abs(v) < 1e-12 for v in inverse_value):
        raise ValueError("親のスケールが0のため、補正できません")
    local = joint.getMatrix(worldSpace=True) * parent_matrix.inverse()
    corrected = local * Matrix(scale=inverse_value) if joint.getSegmentScaleCompensate() else Matrix(local)
    corrected.translate = local.translate
    _, quaternion, scale, shear, _ = Transform._decompose_like_channels(joint, corrected)
    if any(abs(a - b) > 1e-7 for a, b in zip(scale, joint.getScale())) or any(abs(v) > 1e-7 for v in shear):
        raise NotImplementedError("fastのジョイントの親子付けは、Mayaが必要とする補正用のTransformを挿入できません")
    orientation = joint._component_quaternion("rotate").inverse() * joint._component_quaternion("rotateAxis").inverse() * quaternion
    return joint, parent, tuple(local.translate), orientation.asEulerRotation(), new_source


def reparent(plan):
    """計画に従ってJointの親を付け替える。

    付け替えた後、inverseScaleの接続と姿勢を元どおりにする。

    Args:
        plan (tuple): reparent_planが返した計画。

    Returns:
        None: 値を返さない。
    """
    joint, parent, translate, orientation, new_source = plan
    inverse = joint.getPlug("inverseScale").mplug()
    modifier = om2.MDGModifier()
    for origin in inverse.connectedTo(True, False):
        modifier.disconnect(origin, inverse)
    modifier.doIt()
    modifier = om2.MDagModifier()
    modifier.reparentNode(joint.mnode(), parent.mnode() if parent is not None else om2.MObject.kNullObj)
    modifier.doIt()
    # 古いパスを黙って別のインスタンスへ切り替えず、この操作で移したノードの新しいパスを持たせる。
    joint._resolve(om2.MDagPath.getAPathTo(joint.mnode()))
    inverse = joint.getPlug("inverseScale")
    if new_source is not None:
        new_source.connectTo(inverse, fast=True)
    else:
        inverse.set((1.0, 1.0, 1.0), fast=True)
    joint.getPlug("jointOrient").set(orientation, fast=True)
    joint.getPlug("translate").set(translate, fast=True)
