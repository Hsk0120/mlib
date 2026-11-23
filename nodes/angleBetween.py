"""2つのベクトルのなす角を計算する。"""

from .node import Node


class AngleBetween(Node):
    """2つのベクトルのなす角・回転軸・オイラー角を計算する。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumNames(current=True)`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
