"""距離型の2入力を乗算する(Maya 2026以降の型名は ``multDL``)。"""

from .node import Node


class MultDoubleLinear(Node):
    """距離型の2入力を乗算する。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumNames(current=True)`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """


MultDL = MultDoubleLinear  #: Maya 2026以降の型名に合わせた別名(同じクラス)。
