"""MayaのpaintableShadingDependNodeノードを扱う。"""

from .shadingDependNode import ShadingDependNode


class PaintableShadingDependNode(ShadingDependNode):
    """MayaのpaintableShadingDependNodeノードを扱うクラス。値の設定と接続はPlugで行う。"""
