"""単位変換のノード(unitConversion)を扱う。"""

from .node import Node


class UnitConversion(Node):
    """単位変換のノード(unitConversion)を扱うクラス。入力に係数を掛けて出力する。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumName()`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
