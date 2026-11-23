"""サーフェス上の点の位置・法線・接線を取得する。"""

from .node import Node


class PointOnSurfaceInfo(Node):
    """サーフェス上の点の情報を出力するpointOnSurfaceInfoを扱うクラス。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumName()`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
