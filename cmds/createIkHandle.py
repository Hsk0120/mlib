"""開始のjointから末端のjointまでのIKハンドルとエフェクターを作る(``cmds.ikHandle`` 相当)。

.. code-block:: python

    import mlib

    handle = mlib.createIkHandle(shoulder, wrist, solver="ikRPsolver", name="arm_ikh")
    effector = handle.getEffector()

    # cmds.ikHandle と同じ短縮名でも指定できる。
    handle = mlib.createIkHandle(sj=shoulder, ee=wrist, sol="ikSCsolver", n="arm_sc_ikh")
"""

import maya.cmds as cmds
import maya.mel as mel

from ..decorator import _pick_alias, undoChunk
from ..util import _UNSET

#: ``createIkHandle`` が受け付けるMaya標準のIKソルバー名。
_SOLVERS = ("ikRPsolver", "ikSCsolver", "ikSplineSolver", "ikSpringSolver")

#: ``**kwargs`` では受け付けないフラグ。``endEffector`` は ``endJoint``(短縮名 ``ee``)、
#: ``createCurve`` は ``curve`` の有無で決め、query・editは作成専用のため受け付けない。
_REJECTED_FLAGS = frozenset(("endEffector", "createCurve", "ccv", "query", "q", "edit", "e"))


def _record_chain_angles(start, end):
    """IKチェーンのjointの角度アトリビュートを、Undoで戻せるようにする。

    ``cmds.ikHandle`` はpreferredAngleなどを、Undoに記録せずに書き換える。そのため作成の前に、
    今と同じ値をcmds.setAttrで書き込み、元の値をUndoへ記録しておく。
    ロックされたアトリビュートと、入力の接続があるアトリビュートは対象にしない。

    Args:
        start (str): 開始jointの完全パス。
        end (str): 末端jointの完全パス。

    Returns:
        None: 値を返さない。
    """
    joint = end
    while joint:
        for attribute in ("preferredAngle", "fkRotate", "ikRotate"):
            plug = joint + "." + attribute
            if cmds.getAttr(plug, settable=True):
                cmds.setAttr(plug, *cmds.getAttr(plug)[0])
        if joint == start:
            break
        parents = cmds.listRelatives(joint, parent=True, fullPath=True)
        joint = parents[0] if parents else None


def createIkHandle(
    startJoint=_UNSET, endJoint=_UNSET, solver=_UNSET, name=_UNSET, curve=_UNSET, *, sj=_UNSET, ee=_UNSET, sol=_UNSET, n=_UNSET, c=_UNSET, **kwargs
):
    """開始のjointから末端のjointまでのIKハンドルとエフェクターを作る。

    - エフェクター(ikEffector)は、Mayaの規則どおり、末端のjointの1つ上のjointの子に作られる。
      :meth:`~mlib.nodes.IkHandle.getEffector` で取得できる。
    - ``ikSplineSolver`` で ``curve`` を省略すると、Mayaがカーブを自動で作る。
      :meth:`~mlib.nodes.IkHandle.getCurve` で取得できる。
    - ``ikSpringSolver`` は、ソルバーノードが無ければMaya標準の ``ikSpringSolver`` で用意する。
    - Mayaの規則どおり、作ったハンドルが選択される。

    Mayaがチェーンのjointへ自動で設定するpreferredAngleも、Undoで作成前の値に戻す
    (``cmds.ikHandle`` だけをUndoしても戻らない)。
    fast引数は無い(OpenMayaにIKハンドルを作る同じ機能が無いため)。Undoが有効なら1回で戻せる。
    ``mlib.createNode("ikHandle")`` は、これまでどおり何も接続していないノードだけを作る。
    専用の引数は ``cmds.ikHandle`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        startJoint (str | Node): チェーンの開始のjoint。必須。
        endJoint (str | Node): チェーンの末端のjoint(``cmds.ikHandle`` の ``endEffector``)。
            startJointの子孫であること。必須。
        solver (str): ``"ikRPsolver"``・``"ikSCsolver"``・``"ikSplineSolver"``・``"ikSpringSolver"`` のどれか。
            既定は ``"ikRPsolver"``。
        name (str | None): ハンドルに付ける名前。NoneならMayaが自動で名前を付ける。既定はNone。
        curve (str | Node | None): ikSplineSolverで使う既存のカーブ(transformまたはnurbsCurve)。
            Noneなら自動で作る。ikSplineSolver以外では指定できない。既定はNone。
        sj (str | Node): startJointの短縮名。startJointと同時には指定できない。
        ee (str | Node): endJointの短縮名(Mayaの ``endEffector``)。endJointと同時には指定できない。
        sol (str): solverの短縮名。solverと同時には指定できない。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        c (str | Node | None): curveの短縮名。curveと同時には指定できない。
        **kwargs (object): ``cmds.ikHandle`` のそのほかのフラグ(``priority``・``numSpans``・
            ``parentCurve`` など)。そのままMayaへ渡す。
            ``endEffector`` は ``endJoint`` で指定し、``createCurve`` は ``curve`` の有無で決まるため受け付けない。
            query・editも受け付けない。

    Returns:
        IkHandle: 作ったIKハンドル。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、startJointかendJointを省略した場合、
            ``**kwargs`` で受け付けないフラグを渡した場合、nameが文字列でもNoneでもない場合、
            または対象が対応していない型の場合。
        ValueError: solverが対応していない場合、ikSplineSolver以外でcurveを指定した場合、
            開始や末端がjointでない場合、endJointがstartJointの子孫でない場合、またはnameが空文字列の場合。
        RuntimeError: 名前からノードが見つからない場合、またはMayaが作成を拒否した場合。

    Note:
        シーンで最初にIKハンドルを作るとき、Mayaはソルバーノード(ikRPsolverなど)を作る。
        このノードは、``cmds.ikHandle`` と同じくUndoしても残る。
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.joint import Joint
    from ..nodes.node import Node

    startJoint = _pick_alias(startJoint, sj, "startJoint", "sj")
    endJoint = _pick_alias(endJoint, ee, "endJoint", "ee")
    solver = _pick_alias(solver, sol, "solver", "sol", default="ikRPsolver")
    name = _pick_alias(name, n, "name", "n", default=None)
    curve = _pick_alias(curve, c, "curve", "c", default=None)
    rejected = sorted(_REJECTED_FLAGS.intersection(kwargs))
    if rejected:
        raise TypeError(f"createIkHandleは次の引数を受け付けません: {', '.join(rejected)}")
    if solver not in _SOLVERS:
        raise ValueError(f"solverは{', '.join(_SOLVERS)}のどれかで指定してください: {solver!r}")
    if name is not None and not isinstance(name, str):
        raise TypeError("nameは文字列かNoneで指定してください")
    if name == "":
        raise ValueError("nameは空でない文字列かNoneで指定してください")
    if curve is not None and solver != "ikSplineSolver":
        raise ValueError("curveはikSplineSolverの場合だけ指定できます")
    start = Node._resolve_input(startJoint)
    end = Node._resolve_input(endJoint)
    for role, joint in (("startJoint", start), ("endJoint", end)):
        if not joint.isValid() or not isinstance(joint, Joint):
            raise ValueError(f"{role}は有効なジョイントで指定してください")
    if not start.isAncestorOf(end):
        raise ValueError("endJointはstartJointの子孫で指定してください")
    flags = dict(kwargs)
    flags.update(startJoint=start.getFullName(), endEffector=end.getFullName(), solver=solver)
    if name is not None:
        flags["name"] = name
    if curve is not None:
        flags["curve"] = Node._input_name(curve)
        flags["createCurve"] = False
    with undoChunk("mlibCreateIkHandle"):
        if solver == "ikSpringSolver" and not cmds.ls(type="ikSpringSolver"):
            # ikSpringSolverはソルバーノードの登録が要るため、Maya標準の手続きで用意する。
            mel.eval("ikSpringSolver")
        _record_chain_angles(start.getFullName(), end.getFullName())
        result = cmds.ikHandle(**flags)
        return Node(result[0])
