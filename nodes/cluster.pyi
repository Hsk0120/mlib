# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の cluster デフォーマを扱う。"""

from .geometryFilter import GeometryFilter
from mlib.nodes.node import Node



class Cluster(GeometryFilter):
    """Mayaのclusterデフォーマを扱うクラス。"""
    def getWeightedNode(self) -> Node | None:
        """このクラスターのハンドル(Transform)を取得する。

        ``matrix`` アトリビュートの接続元のノードを返す。

        Returns:
            Node | None: クラスターハンドルのTransform。見つからない場合は ``None``。
        """
        ...
