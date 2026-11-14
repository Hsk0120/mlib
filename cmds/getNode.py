"""既存のMayaノードを指す新しいオブジェクトを、ノードの型に合ったクラスで返す。"""


def getNode(value):
    """既存のMayaノードを指す新しいオブジェクトを取得する。

    Nodeを渡しても、同じMayaノードを指す新しいオブジェクトを作る。シーンのノードを作ったり複製したりはしない。
    複数のノードを探すときは ``mlib.ls()`` を使う。
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

    Examples:
        >>> import mlib
        >>> node = mlib.getNode("pCube1")  # シーンに存在するノード
    """
    # 循環参照の回避: nodes は cmds を参照するため、使う時点で読み込む。
    from ..nodes.node import Node

    if isinstance(value, str):
        # Node(value) と同じ解決・型選択を、生成の入口の再判定なしで行う。
        return Node._from_name(value)
    return Node(value)
