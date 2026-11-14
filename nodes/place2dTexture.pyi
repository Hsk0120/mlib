# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaのplace2dTextureノードを扱う。"""

from ..decorator import _edit_context
from .node import Node
from .shadingDependNode import ShadingDependNode
from .texture2d import Texture2d



class Place2dTexture(ShadingDependNode):
    """Mayaのplace2dTextureノードを扱うクラス。値の設定と接続はPlugで行う。"""
    def connectTexture(self, texture: Texture2d | str, force: bool = ..., *, fast: bool = ...) -> Place2dTexture:
        """2Dテクスチャの配置に使う標準のアトリビュートを、テクスチャへ接続する。

        テクスチャ側に無いアトリビュートは飛ばす。すでに同じ接続があるものはそのままにする。

        Args:
            texture (Texture2d | str): 接続先の2Dテクスチャ。
            force (bool): Trueなら、テクスチャ側にすでにある入力の接続を置き換える。:meth:`Plug.connectTo <mlib.plugs.plug.Plug.connectTo>` の決まりに従う。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Place2dTexture: 自身。

        Raises:
            TypeError: fastがbool以外、または対象がTexture2dでない場合。
            RuntimeError: 接続できない場合。途中までにできた接続は自動では戻さない。
        """
        ...
