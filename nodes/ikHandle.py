"""Maya の IK ハンドルを Transform として扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.mel as mel

from ..core.fastWrite import require_unlocked
from ..core.nodeEdit import require_editable
from ..decorator import undoChunk
from .node import Node
from .transform import Transform

#: :meth:`IkHandle.setSolver` で切り替えられるソルバー(ikSplineSolver はカーブが要るため対象外)。
_SWITCHABLE_SOLVERS = ("ikRPsolver", "ikSCsolver", "ikSpringSolver")


class IkHandle(Transform):
    """IKハンドルを扱うクラス。Transformとしての操作もできる。

    たとえばポールベクトルコンストレイントは、Transformから受け継いだ
    :meth:`~mlib.nodes.transform.Transform.addConstraint` で ``addConstraint(target, type="poleVector")`` のように作る。
    """

    def getEffector(self):
        """IKハンドルのエフェクターを取得する。

        ``endEffector`` の接続元のノードを返す。

        Returns:
            Node | None: ikEffectorノード。接続されていなければNone。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("エフェクターの取得")
        source = self._dependency_fn().findPlug("endEffector", False).source()
        return None if source.isNull else Node(source.node())

    def setChain(self, startJoint, endJoint):
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
        start = Node._resolve_input(startJoint)
        end = Node._resolve_input(endJoint)
        if not start.mnode().hasFn(om2.MFn.kJoint) or not end.mnode().hasFn(om2.MFn.kJoint):
            raise TypeError("startJointとendJointはJointで指定してください")
        parent = end.getParent()
        ancestors = []
        while parent is not None:
            ancestors.append(parent)
            if parent == start:
                break
            parent = parent.getParent()
        if start not in ancestors:
            raise ValueError("endJointはstartJointの子孫で指定してください")
        if self.getSolver() != "ikSCsolver":
            raise NotImplementedError("チェーン変更はSCソルバーだけに対応しています")
        for node in [self, end, *ancestors]:
            if node.isFromReferencedFile() or node.isInstanced():
                raise NotImplementedError("参照またはインスタンスのIKチェーン変更には対応していません")
            if node.isLocked():
                raise RuntimeError("IKチェーンのノードがロックされています")
        for name in ("startJoint", "endEffector"):
            if self.getPlug(name).isLocked():
                raise RuntimeError(f"{name}がロックされています")
        cmds.ikHandle(self.getFullName(), edit=True, startJoint=start.getFullName(), endEffector=end.getFullName())

    def getEndJoint(self):
        """IKチェーンの末端のジョイントを取得する。

        ikEffectorノードのtranslateの接続元をたどって、末端のジョイントを見つける。
        ``cmds.ikHandle(query=True, jointList=True)`` は末端のジョイントを含まないので、この方法で求める。

        Returns:
            Joint | None: 末端のジョイント。接続が見つからない場合は ``None``。
        """
        # nodes の初期化順に依存しないよう、使う時点で読み込む。
        from .joint import Joint

        effector_plug = self.getPlug("endEffector").getConnections(input=True)
        if effector_plug is None:
            return None
        source = effector_plug.getNode().getPlug("translateX").getConnections(input=True)
        if source is None:
            return None
        return Joint(source.getNode().getFullName())

    def getJoints(self, includeTip=False):
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
            Joints: 開始ジョイントから順に並んだジョイント。次の場合は空の集まり。

                - startJointかendEffectorが接続されていない。
                - ikEffectorが開始ジョイントの子孫でない。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("ジョイントの一覧の取得")
        fn = self._dependency_fn()
        start = fn.findPlug("startJoint", False).source()
        effector = fn.findPlug("endEffector", False).source()
        joints = []
        if not start.isNull and not effector.isNull:
            start_node = start.node()
            path = om2.MDagPath.getAPathTo(effector.node())
            paths = []
            while path.length() > 1:
                path.pop()
                paths.append(om2.MDagPath(path))
                if path.node() == start_node:
                    joints = [Node(item) for item in reversed(paths)]
                    break
        if includeTip:
            tip = self.getEndJoint()
            if tip is not None:
                joints.append(tip)
        # 循環参照の回避: jointがikHandleを参照するため、使う時点で読み込む。
        from .joint import Joints

        return Joints._wrap(joints)

    def getSolver(self):
        """ハンドルが使うIKソルバーの種類を取得する。

        ``ikSolver`` の接続元のノードの型名を返す。

        Returns:
            str | None: ``"ikRPsolver"``・``"ikSCsolver"``・``"ikSplineSolver"``・``"ikSpringSolver"`` など。
                ソルバーが接続されていなければNone。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("ソルバーの取得")
        source = self._dependency_fn().findPlug("ikSolver", False).source()
        return None if source.isNull else om2.MFnDependencyNode(source.node()).typeName

    def setSolver(self, solver):
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
        if not isinstance(solver, str):
            raise TypeError(f"solverは文字列で指定してください: {solver!r}")
        if solver not in _SWITCHABLE_SOLVERS:
            raise ValueError(f"solverは{', '.join(_SWITCHABLE_SOLVERS)}のどれかで指定してください: {solver!r}")
        if self.getSolver() == "ikSplineSolver":
            raise ValueError(f"スプラインIKハンドルのソルバーは切り替えられません: {self.getFullName()}")
        require_editable(self.mnode())
        require_unlocked(self._dependency_fn().findPlug("ikSolver", False))
        with undoChunk("mlibIkHandleSetSolver"):
            if solver == "ikSpringSolver" and not cmds.ls(type="ikSpringSolver"):
                # ikSpringSolverはソルバーノードの登録が要るため、Maya標準の手続きで用意する。
                mel.eval("ikSpringSolver")
            cmds.ikHandle(self.getFullName(), edit=True, solver=solver)

    def snapToEffector(self):
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
        self._require_valid("スナップ")
        effector = self.getEffector()
        if effector is None:
            raise RuntimeError(f"IKハンドルにエンドエフェクターがありません: {self.getFullName()}")
        with undoChunk("mlibIkHandleSnapToEffector"):
            self.setTranslation(effector.getTranslation(worldSpace=True), worldSpace=True)
