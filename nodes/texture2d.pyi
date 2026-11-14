# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaのtexture2dノードを扱う。"""

from .shadingDependNode import ShadingDependNode
from mlib.nodes.node import Node



class Texture2d(ShadingDependNode):
    """Mayaの継承型に対応するTexture2d。値と接続はPlugで操作する。"""
    def getPlacement(self) -> Node | None:
        """テクスチャの配置を決めるノードを取得する。

        uvCoordアトリビュートへ接続している入力元のノードを返す。通常はPlace2dTextureになる。

        Returns:
            Node | None: uvCoordへの入力元のノード。通常はPlace2dTexture。接続が無ければNone。
        """
        ...
