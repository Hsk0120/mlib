# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""開始のjointから末端のjointまでのIKハンドルとエフェクターを作る(``cmds.ikHandle`` 相当)。"""

import maya.cmds as cmds
import maya.mel as mel
from ..decorator import _pick_alias, undoChunk
from ..util import _UNSET
from mlib.nodes.ikHandle import IkHandle
from mlib.nodes.node import Node

_SOLVERS: tuple
_REJECTED_FLAGS: frozenset

def _record_chain_angles(start: str, end: str) -> None:
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
    ...

def createIkHandle(startJoint: str | Node = ..., endJoint: str | Node = ..., solver: str = ..., name: str | None = ..., curve: str | Node | None = ..., *, sj: str | Node = ..., ee: str | Node = ..., sol: str = ..., n: str | None = ..., c: str | Node | None = ..., **kwargs: object) -> IkHandle:
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

    Examples:
        >>> import mlib
        >>> handle = mlib.createIkHandle(shoulder, wrist, solver="ikRPsolver", name="arm_ikh")
        >>> effector = handle.getEffector()
        >>> # cmds.ikHandle と同じ短縮名でも指定できる。
        >>> handle = mlib.createIkHandle(sj=shoulder, ee=wrist, sol="ikSCsolver", n="arm_sc_ikh")
    """
    ...
