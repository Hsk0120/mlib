"""Maya の displayLayer を扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.object import Object
from ..decorator import undoChunk
from .node import Node


class DisplayLayer(Node):
    """MayaのdisplayLayerを扱うクラス。メンバーの管理と、カレントレイヤーの切り替えができる。"""

    def getMembers(self):
        """レイヤーのメンバーを取得する。

        Returns:
            list[Node]: メンバーのオブジェクト。メンバーが無ければ空リスト。

        Note:
            Maya 2024以降はMFnDisplayLayerを使う。2022/2023にはこのAPIが無いので、defaultLayerでは
            標準コマンドを使い、カメラを除くなどのMayaの決まりをそのまま守る。
        """
        if hasattr(om2, "MFnDisplayLayer"):
            members = om2.MFnDisplayLayer(self.mnode()).getMembers()
            # 選択リストから取得したばかりのパスなので、入力の再解決を省いてラッパーにする。
            return [Node._wrap_dag_path(members.getDagPath(index)) for index in range(members.length())]
        if not self.getPlug("identification").get():
            # 2022/2023にはMFnDisplayLayerがない。defaultLayer固有の除外規則を
            # 単なる未接続DAG走査で再現せず、既存コマンドの意味を維持する。
            names = cmds.editDisplayLayerMembers(self.getName(), query=True, fullNames=True) or []
            return [Node(name) for name in names]
        output = self.getPlug("drawInfo").mplug()
        return [Node._wrap_dag_path(om2.MDagPath.getAPathTo(plug.node())) for plug in output.connectedTo(False, True) if plug.node().hasFn(om2.MFn.kDagNode)]

    def addMembers(self, *members):
        """メンバーをこのレイヤーへ移す。

        子の階層もまとめて移す。ノードが入れるレイヤーは1つだけなので、元のレイヤーからは外れる。
        fast引数は無い(OpenMayaで接続を移すほうがcmdsより遅いため)。

        Args:
            members (Node | str): 追加するDAGノード。

        Returns:
            DisplayLayer: 自身。
        """
        with undoChunk("mlibDisplayLayerAddMembers"):
            if members:
                cmds.editDisplayLayerMembers(self.getName(), Object._input_names(members))
            return self

    def removeMembers(self, *members):
        """ノードをdefaultLayerへ移して、レイヤーから外す。

        子の階層もまとめて移す。

        Args:
            members (Node | str): 外すDAGノード。

        Returns:
            DisplayLayer: 自身。
        """
        with undoChunk("mlibDisplayLayerRemoveMembers"):
            if members:
                cmds.editDisplayLayerMembers("defaultLayer", Object._input_names(members))
            return self

    def setCurrent(self):
        """このレイヤーをカレントレイヤーにする。

        以後に新しく作ったノードは、このレイヤーへ入る。

        Returns:
            DisplayLayer: 自身。
        """
        with undoChunk("mlibDisplayLayerSetCurrent"):
            cmds.editDisplayLayerGlobals(currentDisplayLayer=self.getName())
            return self
