# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の IK ハンドルを Transform として扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.mel as mel
from ..core.fastWrite import require_unlocked
from ..core.nodeEdit import require_editable
from ..decorator import _require_bool, undoChunk
from .node import Node
from .transform import Transform
from typing import Literal
from mlib.nodes.joint import Joint
from mlib.nodes.joint import Joints
from typing import overload

_SWITCHABLE_SOLVERS: tuple


class IkHandle(Transform):
    """IKハンドルを扱うクラス。Transformとしての操作もできる。

    たとえばポールベクトルコンストレイントは、Transformから受け継いだ
    :meth:`~mlib.nodes.transform.Transform.addConstraint` で ``addConstraint(target, type="poleVector")`` のように作る。
    """
    def getEffector(self) -> Node | None:
        """IKハンドルのエフェクターを取得する。

        ``endEffector`` の接続元のノードを返す。

        Returns:
            Node | None: ikEffectorノード。接続されていなければNone。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def setChain(self, startJoint: Joint | str, endJoint: Joint | str) -> None:
        """IKハンドルの開始・末端ジョイントを変更する。

        SCソルバーのローカルなチェーンを対象にする。Mayaが末端にエフェクターを作成する場合がある。
        姿勢の維持は保証しない。fast引数は持たない(1回のcmdsでチェーンを変更するため)。

        Args:
            startJoint (Joint | str): 開始ジョイント。
            endJoint (Joint | str): 開始ジョイントの子孫にある末端ジョイント。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: ジョイント以外を指定した場合。
            ValueError: 末端が開始ジョイントの子孫でない場合。
            RuntimeError: ノードや接続先が無効またはロックされている場合。
            NotImplementedError: SC以外のソルバー、参照、インスタンスを含む場合。
        """
        ...
    @overload
    def getJoints(self, *, includeTip: bool = ..., tipOnly: Literal[True]) -> Joint | None: ...
    @overload
    def getJoints(self, *, includeTip: bool = ..., tipOnly: Literal[False] = ...) -> Joints: ...
    @overload
    def getJoints(self, *, includeTip: bool = ..., tipOnly: bool = ...) -> Joints | Joint | None:
        """IKチェーンのジョイントを、開始ジョイントから順に取得する。``tipOnly=True`` なら、末端のジョイントを1つ取得する。

        ``cmds.ikHandle(query=True, jointList=True)`` と同じジョイントを、OpenMayaで求める。
        ``endEffector`` の接続元(ikEffector)から、DAGの親を ``startJoint`` の接続元までたどる。
        ikEffectorは、末端のジョイントの1つ上のジョイントの子に置かれている。

        既定(``includeTip=False``)では、末端のジョイントを含まない。
        末端まで含めたチェーン全体は ``getJoints(includeTip=True)`` で取得する。

        ``tipOnly=True`` は、ikEffectorノードのtranslateの接続元をたどって、末端のジョイントを見つける
        (``jointList`` は末端のジョイントを含まないので、この方法で求める)。
        ``getJoints(includeTip=True)[-1]`` とは違い、末端が見つからないときはNoneになる(途中のジョイントは返さない)。

        Args:
            includeTip (bool): Trueなら、末端のジョイントも最後に加える。
                既定はFalseで、``cmds.ikHandle(query=True, jointList=True)`` と同じく末端のジョイントを含まない。
            tipOnly (bool): Trueなら、末端のジョイントだけを返す。既定はFalse。includeTip=Trueとは同時に指定できない。

        Returns:
            Joints | Joint | None: 開始ジョイントから順に並んだジョイント。次の場合は空の集まり。

                - startJointかendEffectorが接続されていない。
                - ikEffectorが開始ジョイントの子孫でない。

                tipOnly=Trueなら、末端のジョイント。接続が見つからない場合は ``None``。

        Raises:
            TypeError: includeTip・tipOnlyがboolでない場合、またはtipOnly=TrueとincludeTip=Trueを同時に指定した場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def getSolver(self) -> str | None:
        """ハンドルが使うIKソルバーの種類を取得する。

        ``ikSolver`` の接続元のノードの型名を返す。

        Returns:
            str | None: ``"ikRPsolver"``・``"ikSCsolver"``・``"ikSplineSolver"``・``"ikSpringSolver"`` など。
                ソルバーが接続されていなければNone。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def setSolver(self, solver: str) -> None:
        """ハンドルのIKソルバーを切り替える。

        ``cmds.ikHandle(edit=True, solver=...)`` と同じ処理をする。

        - ``ikSpringSolver`` のソルバーノードが無ければ、Maya標準の手続きで用意する
          (:func:`~mlib.cmds.createIkHandle` と同じ)。
        - ikSplineSolverへの切り替えと、ikSplineSolverからの切り替えはできない。カーブの扱いが変わるため。

        Undoが有効なら、1回のUndoで戻せる。ただし、Mayaが新しく作ったソルバーノードはUndoしても残る。

        Args:
            solver (str): ``"ikRPsolver"``・``"ikSCsolver"``・``"ikSpringSolver"`` のいずれか。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: solverが文字列でない場合。
            ValueError: solverに使えない名前を指定した場合、またはハンドルがikSplineSolverを使っている場合。
            RuntimeError: ノードが無効な場合、ハンドルがロックされているかリファレンスの場合、
                ``ikSolver`` がロックされている場合(Mayaはロックを見ずに切り替えるため、切り替える前に確かめる)、
                またはMayaが切り替えを拒否した場合。
        """
        ...
    def snapToEffector(self) -> None:
        """ハンドルをエフェクターの位置へ移す。

        IKハンドルのSnap Handle to Effectorと同じ操作。
        ハンドルの回転ピボットが、エフェクターの回転ピボットのワールド位置に重なるように、translateを書き換える
        (:meth:`~mlib.nodes.transform.Transform.setTranslation` の ``worldSpace=True`` を使う)。
        IKとFKを切り替えるとき、FKで動かしたチェーンの先端へハンドルを合わせるのに使う。

        ``cmds.ikHandle(edit=True, snapHandleToEffector=True)`` は使わない。
        ``snapEnable`` がオフのハンドルを動かさないため。
        Undoが有効なら、1回のUndoで戻せる。fast引数は無い。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが無効な場合、エフェクターが接続されていない場合、
                またはtranslateがロックされているか入力が接続されていて書き込めない場合。
        """
        ...
    def _end_joint(self) -> Joint | None:
        """IKチェーンの末端のジョイントを返す(``getJoints(tipOnly=True)`` の本体)。

        Returns:
            Joint | None: 末端のジョイント。接続が見つからない場合は ``None``。
        """
        ...
