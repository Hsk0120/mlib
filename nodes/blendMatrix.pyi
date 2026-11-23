# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""入力マトリクスへ、ターゲットのマトリクスをウェイトで順に混ぜる。"""

from .node import Node



class BlendMatrix(Node):
    """``inputMatrix`` へ ``target[i].targetMatrix`` を ``weight`` で順に混ぜたマトリクスを出力する。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumNames(current=True)`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
