"""Mayaのplace2dTextureノードを扱う。"""

from ..decorator import _edit_context, _require_bool
from .node import Node
from .shadingDependNode import ShadingDependNode
from .texture2d import Texture2d


class Place2dTexture(ShadingDependNode):
    """Mayaのplace2dTextureノードを扱うクラス。値の設定と接続はPlugで行う。"""

    def connectTexture(self, texture, *, force=False, fast=False):
        """2Dテクスチャの配置に使う標準のアトリビュートを、テクスチャへ接続する。

        テクスチャ側に無いアトリビュートは飛ばす。すでに同じ接続があるものはそのままにする。

        Args:
            texture (Texture2d | str): 接続先の2Dテクスチャ。
            force (bool): Trueなら、テクスチャ側にすでにある入力の接続を置き換える。:meth:`Plug.connectTo <mlib.plugs.plug.Plug.connectTo>` の決まりに従う。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: force・fastがbool以外、または対象がTexture2dでない場合。
            RuntimeError: 接続できない場合。途中までにできた接続は自動では戻さない。
        """
        _require_bool(force, "force")
        with _edit_context("mlibPlace2dTextureConnectTexture", fast):
            texture = Node._resolve_input(texture)
            if not isinstance(texture, Texture2d):
                raise TypeError("textureはTexture2dで指定してください")
            names = (
                "coverage",
                "translateFrame",
                "rotateFrame",
                "mirrorU",
                "mirrorV",
                "stagger",
                "wrapU",
                "wrapV",
                "repeatUV",
                "offset",
                "rotateUV",
                "noiseUV",
                "vertexUvOne",
                "vertexUvTwo",
                "vertexUvThree",
                "vertexCameraOne",
            )
            pairs = [(name, name) for name in names] + [("outUV", "uvCoord"), ("outUvFilterSize", "uvFilterSize")]
            for origin, target in pairs:
                if texture.hasAttr(target):
                    source = self.getPlug(origin)
                    destination = texture.getPlug(target)
                    if destination.getConnections(input=True) != source:
                        source.connectTo(destination, force=force, fast=fast)
