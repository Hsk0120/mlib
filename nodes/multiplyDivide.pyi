# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""XYZ成分ごとの乗算・除算・累乗。"""

from .shadingDependNode import ShadingDependNode



class MultiplyDivide(ShadingDependNode):
    """XYZの成分ごとに、乗算・除算・累乗を計算するmultiplyDivideを扱うクラス。

    専用のメソッドは持たない。入力・出力・演算の種類などは、アトリビュート(Plug)で読み書きする
    (``node.getPlug("input1").set(...)``・``plug.connect(...)``・``node.getPlug("output").get()``。
    enumは ``Plug.getEnumNames(current=True)`` と、Mayaのフィールド名を渡す ``Plug.set("Divide")`` で名前でも扱える)。
    """
