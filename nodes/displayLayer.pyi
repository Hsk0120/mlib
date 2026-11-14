# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の displayLayer を扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.object import Object
from ..decorator import undoChunk
from .node import Node



class DisplayLayer(Node):
    """MayaのdisplayLayerを扱うクラス。メンバーの管理と、カレントレイヤーの切り替えができる。"""
    def getMembers(self) -> list[Node]:
        """レイヤーのメンバーを取得する。

        Returns:
            list[Node]: メンバーのオブジェクト。メンバーが無ければ空リスト。

        Note:
            Maya 2024以降はMFnDisplayLayerを使う。2022/2023にはこのAPIが無いので、defaultLayerでは
            標準コマンドを使い、カメラを除くなどのMayaの決まりをそのまま守る。
        """
        ...
    def addMembers(self, *members: Node | str) -> DisplayLayer:
        """メンバーをこのレイヤーへ移す。

        子の階層もまとめて移す。ノードが入れるレイヤーは1つだけなので、元のレイヤーからは外れる。
        fast引数は無い(OpenMayaで接続を移すほうがcmdsより遅いため)。

        Args:
            members (Node | str): 追加するDAGノード。

        Returns:
            DisplayLayer: 自身。
        """
        ...
    def removeMembers(self, *members: Node | str) -> DisplayLayer:
        """ノードをdefaultLayerへ移して、レイヤーから外す。

        子の階層もまとめて移す。

        Args:
            members (Node | str): 外すDAGノード。

        Returns:
            DisplayLayer: 自身。
        """
        ...
    def setCurrent(self) -> DisplayLayer:
        """このレイヤーをカレントレイヤーにする。

        以後に新しく作ったノードは、このレイヤーへ入る。

        Returns:
            DisplayLayer: 自身。
        """
        ...
