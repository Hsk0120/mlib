"""マトリクスから移動・回転・スケール・せん断の一部だけを取り出す。"""

from .node import Node


class PickMatrix(Node):
    """マトリクスの成分の一部だけを取り出すpickMatrixを扱うクラス。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumNames(current=True)`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
