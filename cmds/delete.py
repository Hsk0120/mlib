"""ノードまたはコンポーネントを削除する(``cmds.delete`` 相当)。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.object import _selection_plug
from ..decorator import _edit_context


def delete(nodes, *, fast=False):
    """指定したノードやコンポーネントを削除する。

    Plug・MPlugは受け付けない。アトリビュートを削除するときは ``plug.delete()`` を、
    マルチアトリビュートの要素を削除するときは ``multi_plug.removeElement(index)`` を使う。

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

    Examples:
        >>> import mlib
        >>> node = mlib.createNode("transform", name="example")
        >>> mlib.delete(node)
    """
    with _edit_context("mlibDelete", fast):
        # 循環参照の回避: core は cmds を参照するため、使う時点で読み込む。
        from ..core.nodeEdit import check_deletion, delete_nodes
        from ..core.object import Object as _InputObject
        from ..nodes.joint import Joint
        from ..nodes.node import Node

        given = [nodes] if isinstance(nodes, Node) else nodes if isinstance(nodes, (list, tuple)) else None
        if given and all(isinstance(node, Node) and node.isValid() for node in given):
            # 有効なNodeだけの入力は、名前へ直して作り直さず、そのまま使う。
            names = []
            direct = list(given)
        else:
            direct = []
            names = _InputObject._input_names(nodes, allow_plugs=False)
            if not names:
                raise ValueError("nodesにはノードを1つ以上指定してください")
        # アトリビュート・コンポーネント文字列は所有ノードへ変換せず、標準の扱いを維持する。
        node_names = [name for name in names if "." not in name]
        components = [name for name in names if "." in name]
        for name in components:
            # "node.tx" のようなアトリビュート名の文字列も、Plugと同じく削除の前に拒否する。
            if _resolves_to_plug(name):
                raise TypeError(f"アトリビュート名は指定できません: {name}(持ち主のノードを削除するにはノード名を指定します)")
        if components and fast:
            raise NotImplementedError("fastはコンポーネントとトポロジーの削除に対応していません")
        nodes = direct
        for name in node_names:
            # Maya標準のワイルドカード指定を実ノードへ展開してから検証する。
            if any(char in name for char in "*?["):
                resolved = list(om2.MGlobal.getSelectionListByName(name).getSelectionStrings()) if fast else cmds.ls(name, long=True)
            else:
                resolved = [name]
            # 名前は Node(value) と同じ解決・型選択を、生成の入口の再判定なしで行う。
            nodes.extend(Node._from_name(value) for value in (resolved or [name]))
        # Joint.deleteの解除はメソッドの呼出しだけの動作で、ここではMaya標準の削除として扱う。
        standard = (Node.delete, Joint.delete)
        batch = all(type(node).delete in standard for node in nodes)
        checked = None
        if nodes and (batch or fast):
            # コンポーネントを削除する前に検査し、拒否する場合は何も削除しない。
            checked = check_deletion(nodes, fast=fast)
        if components:
            cmds.delete(*components)
            # コンポーネントの削除で消えたノードは従来どおり飛ばし、残りを検査し直す。
            nodes = [node for node in nodes if node.isValid()]
            checked = None
        if not nodes:
            return
        if batch:
            delete_nodes(nodes, fast=fast, checked=checked)
            return
        for node in nodes:
            # 親・所有コンテナの削除や重複指定で既に消えた対象は再削除しない。
            if node.isValid():
                (Node.delete if type(node).delete in standard else type(node).delete)(node, fast=fast)


def _resolves_to_plug(name):
    """文字列がアトリビュート(プラグ)を指すか調べる。

    Mayaが見つけられない名前とコンポーネント名は False にし、これまでどおり ``cmds.delete`` の扱いに任せる。

    Args:
        name (str): ``"."`` を含む対象の名前。

    Returns:
        bool: 一致したもののどれかがプラグなら True。
    """
    selection = om2.MSelectionList()
    try:
        selection.add(name)
    except RuntimeError:
        return False
    return any(_selection_plug(selection, index) is not None for index in range(selection.length()))
