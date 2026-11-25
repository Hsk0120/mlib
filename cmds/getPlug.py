"""アトリビュート名やMPlugから、型に合ったPlugを取得する。"""

import maya.api.OpenMaya as om2


def getPlug(value):
    """アトリビュート名やAPIのオブジェクトからプラグを取得する。

    値は ``plug.get()`` で取得する。シーンは変更しない。まだ作られていないマルチアトリビュートの要素も取得でき、
    取得しただけではその要素は作られない。
    クラスはアトリビュートの定義から選ぶ。クラスを選ぶために値を評価することはない。

    Args:
        value (str | Plug | om2.MPlug): アトリビュート名、mlibのプラグ、またはMaya API 2.0のオブジェクト。

    Returns:
        Plug: アトリビュートの型に合ったオブジェクト。既存のPlugを渡すと、有効かどうかを調べ直さずに
            同じインスタンスを返す。文字列・MPlugからは新しいオブジェクトを作る。
            値やアトリビュートを複製するわけではない。

    Raises:
        TypeError: 対応していない型を渡した場合。
        ValueError: 空の名前、または空のMPlugを渡した場合。
        MissingAttributeError: アトリビュート(またはノード)が存在しない場合(文言は ``アトリビュートが見つかりません: <名前>``)。
            ``mlib.plugs.plug.MissingAttributeError`` は ``AttributeError`` の派生で、
            ``node.getPlug(name)`` と同じ例外。
        DeletedAttributeError: ``deleteAttr`` で削除したアトリビュートのMPlugを渡した場合
            (``mlib.getNode`` と同じ例外)。``mlib.plugs.plug.DeletedAttributeError`` は ``ValueError`` の派生。
        RuntimeError: 名前が複数の対象に一致する場合。

    Examples:
        >>> import mlib
        >>> translate_x = mlib.getPlug("pCube1.translateX")
        >>> value = translate_x.get()
    """
    # 循環参照の回避: plugs は cmds を参照するため、使う時点で読み込む。
    from ..plugs.plug import DeletedAttributeError, Plug

    # ノードが残っていてアトリビュートだけが削除されたMPlugは、mlib.getNodeと同じ例外にする。
    if isinstance(value, om2.MPlug) and not value.isNull:
        owner = value.node()
        if om2.MObjectHandle(owner).isValid() and not Plug._mplug_attribute_exists(value, owner):
            raise DeletedAttributeError("削除されたアトリビュートのMPlugからはPlugを作成できません")
    return Plug._resolve_input(value)
