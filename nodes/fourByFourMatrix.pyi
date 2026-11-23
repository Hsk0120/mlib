# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""16個の値からマトリクスを作る。"""

from .node import Node



class FourByFourMatrix(Node):
    """``in00``〜``in33`` の16個の値(行優先)からマトリクスを作り、``output`` へ出力する。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumNames(current=True)`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
