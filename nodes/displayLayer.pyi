# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の displayLayer を扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.object import Object
from ..decorator import undoChunk
from .node import Node, Nodes



class DisplayLayer(Node):
    """MayaのdisplayLayerを扱うクラス。メンバーの管理と、カレントレイヤーの切り替えができる。"""
    def getMembers(self) -> Nodes:
        """レイヤーのメンバーを取得する。

        Returns:
            Nodes: メンバーのオブジェクト。メンバーが無ければ空の集まり。

        Note:
            Maya 2024以降はMFnDisplayLayerを使う。2022/2023にはこのAPIが無いので、defaultLayerでは
            標準コマンドを使い、カメラを除くなどのMayaの決まりをそのまま守る。
        """
        ...
    def addMembers(self, *members: Node | str) -> None:
        """メンバーをこのレイヤーへ移す。

        子の階層もまとめて移す。ノードが入れるレイヤーは1つだけなので、元のレイヤーからは外れる。
        fast引数は無い(OpenMayaで接続を移すほうがcmdsより遅いため)。

        Args:
            members (Node | str): 追加するDAGノード。

        Returns:
            None: 値を返さない。
        """
        ...
    def removeMembers(self, *members: Node | str) -> None:
        """ノードをdefaultLayerへ移して、レイヤーから外す。

        子の階層もまとめて移す。

        Args:
            members (Node | str): 外すDAGノード。

        Returns:
            None: 値を返さない。
        """
        ...
    def setCurrent(self) -> None:
        """このレイヤーをカレントレイヤーにする。

        以後に新しく作ったノードは、このレイヤーへ入る。

        Returns:
            None: 値を返さない。
        """
        ...
