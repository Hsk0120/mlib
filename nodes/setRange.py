"""XYZ各成分を旧範囲から新範囲へ線形変換する。"""

from .node import Node


class SetRange(Node):
    """XYZ各成分を旧範囲から新範囲へ線形変換する。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumName()`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
