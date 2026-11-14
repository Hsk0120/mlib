"""Maya の cluster デフォーマを扱う。"""

from .geometryFilter import GeometryFilter


class Cluster(GeometryFilter):
    """Mayaのclusterデフォーマを扱うクラス。"""

    def getWeightedNode(self):
        """このクラスターのハンドル(Transform)を取得する。

        ``matrix`` アトリビュートの接続元のノードを返す。

        Returns:
            Node | None: クラスターハンドルのTransform。見つからない場合は ``None``。
        """
        source = self.getPlug("matrix").getSource()
        return None if source is None else source.getNode()
