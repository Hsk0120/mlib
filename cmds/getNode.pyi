# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""既存のMayaノードを指す新しいオブジェクトを、ノードの型に合ったクラスで返す。

ノードを作ったり複製したりはしない。Plugを渡すとその持ち主のノードを、Componentを渡すと
その持ち主のシェイプを返す。複数のノードを探すときは ``mlib.ls()`` を使う。

.. code-block:: python

    import mlib

    node = mlib.getNode("pCube1")  # シーンに存在するノード
"""

from mlib.components.component import Component
from mlib.components.component import Components
from mlib.nodes.node import Node
from mlib.plugs.plug import Plug
import maya.api.OpenMaya as om2


def getNode(value: str | Node | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug) -> Node:
    """既存のMayaノードを指す新しいオブジェクトを取得する。

    Nodeを渡しても、同じMayaノードを指す新しいオブジェクトを作る。シーンのノードは複製しない。
    クラスは次の順に選ぶ。

    - nodeTypeに登録されたクラス。
    - 登録が無ければ、Mayaの継承に沿って作ったクラス(基底は最も近い登録クラス)。
    - Mayaが知らない型名の場合だけNode。

    Args:
        value (str | Node | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug):
            ノード名、mlib のオブジェクト、または Maya API 2.0 のオブジェクト。Plug・MPlug は
            持ち主のノード、Component・Components は持ち主のシェイプとして扱う。

    Returns:
        Node: 実際のノード型に合ったオブジェクト。

    Raises:
        TypeError: 対応していない型を渡した場合、または依存ノード以外(アトリビュートなど)を指す MObject の場合。
        ValueError: 持ち主のノードは有効だが、アトリビュートが ``deleteAttr`` で削除済みの Plug・MPlug の場合
            (``mlib.plugs.plug.DeletedAttributeError``。RuntimeError の派生でもある)。
        RuntimeError: ノードが1つに決まらない場合(存在しない場合や、``"bulk*"`` のようなパターンを
            含めて複数の対象に一致する場合)、または空か削除済みのオブジェクトや om2 のオブジェクトを
            渡した場合。
    """
    ...
