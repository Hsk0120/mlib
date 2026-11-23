"""Mayaのtexture2dノードを扱う。"""

from .shadingDependNode import ShadingDependNode


class Texture2d(ShadingDependNode):
    """Mayaの継承型に対応するTexture2d。値と接続はPlugで操作する。"""
