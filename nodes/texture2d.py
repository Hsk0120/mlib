"""Mayaのtexture2dノードを扱う。"""

from .shadingDependNode import ShadingDependNode


class Texture2d(ShadingDependNode):
    """Mayaの継承型に対応するTexture2d。値と接続はPlugで操作する。"""

    def getPlacement(self):
        """テクスチャの配置を決めるノードを取得する。

        uvCoordアトリビュートへ接続している入力元のノードを返す。通常はPlace2dTextureになる。

        Returns:
            Node | None: uvCoordへの入力元のノード。通常はPlace2dTexture。接続が無ければNone。
        """
        source = self.getPlug("uvCoord").getSource()
        return None if source is None else source.getNode()
