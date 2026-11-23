"""2つのRGBの入力を、blenderの割合で補間する。"""

from .node import Node


class BlendColors(Node):
    """color1 * blender + color2 * (1 - blender)を評価するノード。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumNames(current=True)`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
