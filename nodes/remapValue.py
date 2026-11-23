"""ランプで値を再マッピングする。色ランプも操作できる。"""

from .node import Node


class RemapValue(Node):
    """ランプで値を再マッピングする。色ランプも操作できる。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumName()`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
