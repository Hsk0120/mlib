"""ベクトルの内積・外積・マトリクスとの積を計算する。"""

from .node import Node


class VectorProduct(Node):
    """ベクトルの内積・外積・マトリクスとの積を計算するノード(vectorProduct)を扱うクラス。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumName()`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
