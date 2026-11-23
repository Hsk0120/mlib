"""指定した軸をターゲットへ向けるマトリクスを作る。"""

from .node import Node


class AimMatrix(Node):
    """入力マトリクスの主軸・副軸を、ターゲットのマトリクスまたはベクトルへ向けたマトリクスを出力する。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumNames(current=True)`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
