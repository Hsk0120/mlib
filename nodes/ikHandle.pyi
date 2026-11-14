# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の IK ハンドルを Transform として扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.mel as mel
from ..decorator import undoChunk
from .node import Node
from .transform import Transform
from mlib.nodes.joint import Joint

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
    def getCurve(self) -> Transform | None:
        """ikSplineSolverが使うカーブを取得する。

        ``inCurve`` の接続元の形状をたどり、その親のTransformを返す。

        Returns:
            Transform | None: カーブのTransform。inCurveが接続されていなければNone
                (スプライン以外のソルバーなど)。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def getEndJoint(self) -> Joint | None:
        """IKチェーンの末端のジョイントを取得する。

        ikEffectorノードのtranslateの接続元をたどって、末端のジョイントを見つける。
        ``cmds.ikHandle(query=True, jointList=True)`` は末端のジョイントを含まないので、この方法で求める。

        Returns:
            Joint | None: 末端のジョイント。接続が見つからない場合は ``None``。
        """
        ...
    def getJoints(self, includeTip: bool = ...) -> list[Joint]:
        """IKチェーンのジョイントを、開始ジョイントから順に取得する。

        ``cmds.ikHandle(query=True, jointList=True)`` と同じジョイントを、OpenMayaで求める。
        ``endEffector`` の接続元(ikEffector)から、DAGの親を ``startJoint`` の接続元までたどる。
        ikEffectorは、末端のジョイントの1つ上のジョイントの子に置かれている。

        既定(``includeTip=False``)では、末端のジョイントを含まない。
        末端まで含めたチェーン全体は ``getJoints(includeTip=True)`` で取得する。

        Args:
            includeTip (bool): Trueなら、末端のジョイント(``getEndJoint()``)も最後に加える。
                既定はFalseで、``cmds.ikHandle(query=True, jointList=True)`` と同じく末端のジョイントを含まない。

        Returns:
            list[Joint]: 開始ジョイントから順に並んだジョイント。次の場合は空リスト。

                - startJointかendEffectorが接続されていない。
                - ikEffectorが開始ジョイントの子孫でない。

        Raises:
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
    def setSolver(self, solver: str) -> IkHandle:
        """ハンドルのIKソルバーを切り替える。

        ``cmds.ikHandle(edit=True, solver=...)`` と同じ処理をする。

        - ``ikSpringSolver`` のソルバーノードが無ければ、Maya標準の手続きで用意する
          (:func:`~mlib.cmds.createIkHandle` と同じ)。
        - ikSplineSolverへの切り替えと、ikSplineSolverからの切り替えはできない。カーブの扱いが変わるため。

        Undoが有効なら、1回のUndoで戻せる。ただし、Mayaが新しく作ったソルバーノードはUndoしても残る。

        Args:
            solver (str): ``"ikRPsolver"``・``"ikSCsolver"``・``"ikSpringSolver"`` のいずれか。

        Returns:
            IkHandle: 自身。

        Raises:
            TypeError: solverが文字列でない場合。
            ValueError: solverに使えない名前を指定した場合、またはハンドルがikSplineSolverを使っている場合。
            RuntimeError: ノードが無効な場合、またはMayaが切り替えを拒否した場合。
        """
        ...
    def snapToEffector(self) -> IkHandle:
        """ハンドルをエフェクターの位置へ移す。

        IKハンドルのSnap Handle to Effectorと同じ操作。
        ハンドルの回転ピボットが、エフェクターの回転ピボットのワールド位置に重なるように、translateを書き換える
        (:meth:`~mlib.nodes.transform.Transform.setTranslation` の ``worldSpace=True`` を使う)。
        IKとFKを切り替えるとき、FKで動かしたチェーンの先端へハンドルを合わせるのに使う。

        ``cmds.ikHandle(edit=True, snapHandleToEffector=True)`` は使わない。
        ``snapEnable`` がオフのハンドルを動かさないため。
        Undoが有効なら、1回のUndoで戻せる。fast引数は無い。

        Returns:
            IkHandle: 自身。

        Raises:
            RuntimeError: ノードが無効な場合、エフェクターが接続されていない場合、
                またはtranslateがロックされているか入力が接続されていて書き込めない場合。
        """
        ...
