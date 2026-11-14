# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ノードまたはコンポーネントを削除する。戻り値はNone。

Plug・MPlugは受け付けない。アトリビュートを削除するときは ``plug.delete()`` を、
マルチアトリビュートの要素を削除するときは ``multi_plug.removeElement(index)`` を使う。
通常はMayaのUndoに対応する。``fast=True`` で削除できるのはノードだけで、
コンポーネントを含む入力では何も削除せずエラーにする。

.. code-block:: python

    import mlib

    node = mlib.createNode("transform", name="example")
    mlib.delete(node)
"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.object import _selection_plug
from ..decorator import _edit_context
from typing import Iterable
from mlib.common.selection import Selection
from mlib.components.component import Component
from mlib.components.component import Components
from mlib.nodes.node import Node


def delete(nodes: Node | Component | Components | Selection | str | om2.MObject | om2.MDagPath | Iterable, *, fast: bool = ...) -> None:
    """指定したノードやコンポーネントを削除する。

    ノードは、対象をすべて1回の削除にまとめる。通常は ``cmds.delete`` を1回呼ぶ(1回のUndoですべて戻る)。
    fastでは、1つの MDagModifier の doIt を1回呼んで削除する。
    削除の順(削除の通知の順)と、一緒に消えるノード(unitConversion・コンストラクションヒストリなど)は、
    Mayaがまとめて削除するときの規則に従う(DGとDAGが混ざると、渡した順にならないことがある)。

    削除の前に、対象のすべてとそのDAGの子孫を調べる。次のノードが1つでも含まれていれば、
    コンポーネントも含めて何も削除せず、RuntimeErrorにする。

    - ロックされたノード
    - リファレンスのノード
    - Mayaが削除を拒否するノード(既定のノード・共有ノードなど。time1・persp・defaultLayer など)

    Args:
        nodes (Node | Component | Components | Selection | str | om2.MObject | om2.MDagPath | Iterable):
            削除する対象、またはその並び(入れ子になったコレクションも展開する)。
            同じノードを何度指定しても、親と子の両方を指定しても、1回だけ削除する(子は親と一緒に消える)。
            ワイルドカードは、一致したノードへ展開する。
        fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: 要素が対応していない型の場合、またはfastがboolでない場合。
            要素に Plug(MultiPlug を含む)・om2.MPlug、またはアトリビュートを指す文字列(``"node.tx"`` など)が
            含まれる場合もTypeErrorにし、何も削除しない(maya.cmds.delete はアトリビュートを削除せず、
            エラーを表示するだけのため)。
        ValueError: nodes が空の場合、または要素が空文字列か削除済みの対象の場合(何も削除しない)。
        RuntimeError: 存在しない名前を含む場合(``getNode`` と同じ文言。何も削除しない)。
            ロックされたノード・リファレンスのノード・削除できないノードを含む場合(何も削除しない)。
            このときの文言は cmds.delete と同じく要素ごとに示す。例えば ``ロックされたノード'x'は削除できません``、
            ``'x'は削除できません。ロックされた子か、読み取り専用の子があります``、
            ``削除できないノードです: 'x'``。fastでロックかリファレンスの場合は
            ``ノードがロックされているか、リファレンスです: x``。
            または Maya が削除を拒否した場合。
        NotImplementedError: fast=Trueで、コンポーネントを含む入力を指定した場合(何も削除しない)。

    Note:
        fastで削除できるのはノードだけ。コンポーネントのトポロジーの削除には対応しない。
        入力にコンポーネントが含まれる場合は、何も削除せずNotImplementedErrorにする。

        deleteを上書きした派生クラスのノードが含まれる場合だけは、これまでどおり各ノードの
        deleteを順に呼ぶ(親の削除ですでに消えた対象は飛ばす)。Jointはこれに含めない。
        :meth:`Joint.delete <mlib.nodes.joint.Joint.delete>` のインフルエンスの解除は行わず、Maya標準で削除する。

        コンポーネントは、ノードを調べたあと、ノードより先に、別の1回の ``cmds.delete`` で削除する。
    """
    ...

def _resolves_to_plug(name: str) -> bool:
    """文字列がアトリビュート(プラグ)を指すか調べる。

    Mayaが見つけられない名前とコンポーネント名は False にし、これまでどおり ``cmds.delete`` の扱いに任せる。

    Args:
        name (str): ``"."`` を含む対象の名前。

    Returns:
        bool: 一致したもののどれかがプラグなら True。
    """
    ...
