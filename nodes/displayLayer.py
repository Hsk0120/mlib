"""Maya の displayLayer を扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.object import Object
from ..decorator import _require_bool, undoChunk
from .node import Node, Nodes


class DisplayLayer(Node):
    """MayaのdisplayLayerを扱うクラス。メンバーの管理と、カレントレイヤーの切り替えができる。"""

    def getMembers(self):
        """レイヤーのメンバーを取得する。

        Returns:
            Nodes: メンバーのオブジェクト。メンバーが無ければ空の集まり。

        Note:
            Maya 2024以降はMFnDisplayLayerを使う。2022/2023にはこのAPIが無いので、defaultLayerでは
            標準コマンドを使い、カメラを除くなどのMayaの決まりをそのまま守る。
        """
        if hasattr(om2, "MFnDisplayLayer"):
            members = om2.MFnDisplayLayer(self.mnode()).getMembers()
            # 選択リストから取得したばかりのパスなので、入力の再解決を省いてラッパーにする。
            return Nodes._wrap([Node._wrap_dag_path(members.getDagPath(index)) for index in range(members.length())])
        if not self.getPlug("identification").get():
            # 2022/2023にはMFnDisplayLayerがない。defaultLayer固有の除外規則を
            # 単なる未接続DAG走査で再現せず、既存コマンドの意味を維持する。
            names = cmds.editDisplayLayerMembers(self.getName(), query=True, fullNames=True) or []
            return Nodes._wrap([Node(name) for name in names])
        output = self.getPlug("drawInfo").mplug()
        return Nodes._wrap(
            [Node._wrap_dag_path(om2.MDagPath.getAPathTo(plug.node())) for plug in output.connectedTo(False, True) if plug.node().hasFn(om2.MFn.kDagNode)]
        )

    def addMembers(self, *members):
        """メンバーをこのレイヤーへ移す。

        子の階層もまとめて移す。ノードが入れるレイヤーは1つだけなので、元のレイヤーからは外れる。
        fast引数は無い(OpenMayaで接続を移すほうがcmdsより遅いため)。

        Args:
            members (Node | str): 追加するDAGノード。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 対応していない型を渡した場合、または名前とNodeなどのオブジェクトを混ぜて渡した場合。
            ValueError: 名前に一致するものが無い場合、または渡したものが無効な(削除された)場合。
        """
        with undoChunk("mlibDisplayLayerAddMembers"):
            if members:
                cmds.editDisplayLayerMembers(self.getName(), Object._input_names(members))

    def removeMembers(self, *members, all=False):
        """ノードをdefaultLayerへ移して、レイヤーから外す。``all=True`` なら、すべてのメンバーを外す。

        子の階層もまとめて移す。

        Args:
            all (bool): Trueなら、すべてのメンバーを外す。既定はFalse。
            members (Node | str): 外すDAGノード。all=Trueとは同時に指定できない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: allがboolでない場合、membersとall=Trueを同時に指定した場合、対応していない型を渡した場合、
                または名前とNodeなどのオブジェクトを混ぜて渡した場合。
            ValueError: 名前に一致するものが無い場合、または渡したものが無効な(削除された)場合。
        """
        _require_bool(all, "all")
        if all and members:
            raise TypeError("membersとall=Trueは同時に指定できません")
        with undoChunk("mlibDisplayLayerRemoveMembers"):
            if all:
                members = tuple(self.getMembers())
            if members:
                cmds.editDisplayLayerMembers("defaultLayer", Object._input_names(members))

    def setCurrent(self):
        """このレイヤーをカレントレイヤーにする。

        以後に新しく作ったノードは、このレイヤーへ入る。

        Returns:
            None: 値を返さない。
        """
        with undoChunk("mlibDisplayLayerSetCurrent"):
            cmds.editDisplayLayerGlobals(currentDisplayLayer=self.getName())
