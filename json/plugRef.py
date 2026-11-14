"""Plugを、持ち主のノードの参照とアトリビュートのパスで記録する。"""

from .nameMapping import NameMapping
from .nodeRef import NodeRef


class PlugRef:
    """Plugの参照。

    持ち主のノードの :class:`NodeRef` と、アトリビュートのパスで記録する。
    アトリビュートのパスはロング名で書く。マルチアトリビュートの要素は ``weight[3]``、
    コンパウンドアトリビュートの子は ``translate.translateX`` のように書く。エイリアスは使わない。
    名前の対応づけは、ノードの部分にだけ当てる。
    """

    __hash__ = None  # type: ignore[assignment]

    def __init__(self, node, attribute):
        """記録する値を持たせる。

        Args:
            node (NodeRef): 持ち主のノードの参照。
            attribute (str): アトリビュートのパス(ノード名は含めない)。

        Raises:
            TypeError: nodeがNodeRefでない場合、またはattributeが文字列でない場合。
            ValueError: attributeが空の場合。
        """
        if not isinstance(node, NodeRef):
            raise TypeError("nodeはNodeRefで指定してください")
        if not isinstance(attribute, str):
            raise TypeError("attributeは文字列で指定してください")
        if not attribute:
            raise ValueError("attributeは空にできません")
        self._node = node
        self._attribute = attribute

    def __repr__(self):
        """ノード名とアトリビュートを含む表記を返す。

        Returns:
            str: ``PlugRef('chrA:arm_L_jnt.translateX')`` の形式。
        """
        return f"PlugRef({self._node.name + '.' + self._attribute!r})"

    def __eq__(self, other):
        """ノードの参照とアトリビュートのパスが同じかを返す。

        Args:
            other (object): 比較する値。

        Returns:
            bool: 同じ記録ならTrue。PlugRef以外はNotImplemented。
        """
        if not isinstance(other, PlugRef):
            return NotImplemented
        return self._node == other._node and self._attribute == other._attribute

    @classmethod
    def capture(cls, plug):
        """シーンのPlugから参照を作る。

        Args:
            plug (Plug | str | om2.MPlug): 記録するPlug。

        Returns:
            PlugRef: 持ち主のノードとアトリビュートのパスを記録した参照。

        Raises:
            TypeError: plugが対応しない型の場合。
            ValueError: Plugが無い場合。
            RuntimeError: Plugが無効な場合。
        """
        # 循環参照の回避: plugs・cmdsはノードのメソッドからmlib.jsonを使うので、使うときに読み込む。
        from ..cmds import getPlug
        from ..plugs.plug import Plug

        plug = plug if isinstance(plug, Plug) else getPlug(plug)
        if not plug.isValid():
            raise RuntimeError("削除されたPlugは記録できません")
        attribute = plug.mplug().partialName(includeNodeName=False, includeNonMandatoryIndices=True, includeInstancedIndices=True, useLongNames=True)
        return cls(NodeRef.capture(plug.getNode()), attribute)

    @classmethod
    def fromData(cls, data):
        """:meth:`toData` の辞書から作る。

        Args:
            data (dict): ``node``・``attr`` を持つ辞書。

        Returns:
            PlugRef: 新しい参照。

        Raises:
            ValueError: 辞書の形が正しくない場合。
        """
        if not isinstance(data, dict) or "node" not in data or not isinstance(data.get("attr"), str):
            raise ValueError(f"JSONのPlugの参照が不正です: {data!r}")
        return cls(NodeRef.fromData(data["node"]), data["attr"])

    @property
    def node(self):
        """持ち主のノードの参照を返す。

        Returns:
            NodeRef: 持っている参照。
        """
        return self._node

    @property
    def attribute(self):
        """アトリビュートのパスを返す。

        Returns:
            str: ``"translateX"``・``"weight[3]"`` など。
        """
        return self._attribute

    def toData(self):
        """JSONに書く辞書を返す。

        Returns:
            dict: ``{"node": {...}, "attr": ...}``。
        """
        return {"node": self._node.toData(), "attr": self._attribute}

    def mappedName(self, mapping=None):
        """名前の対応づけを当てたPlug名を返す。

        Args:
            mapping (NameMapping | None): 名前の対応づけ。

        Returns:
            str: ``<ノード名>.<アトリビュート>``。警告や報告の表示に使う。
        """
        return self._node.mappedName(mapping) + "." + self._attribute

    def resolve(self, mapping=None):
        """シーンのPlugを返す。

        名前の対応づけを当てたノードから、記録したアトリビュートのPlugを取得する。

        Args:
            mapping (NameMapping | None): 名前の対応づけ。

        Returns:
            Plug | None: 見つかったPlug。ノードかアトリビュートが無ければNone。

        Raises:
            TypeError: mappingがNameMappingでもNoneでもない場合。
        """
        if mapping is not None and not isinstance(mapping, NameMapping):
            raise TypeError("mappingはNameMappingかNoneで指定してください")
        node = self._node.resolve(mapping)
        if node is None:
            return None
        try:
            return node.getPlug(self._attribute)
        except (AttributeError, RuntimeError, ValueError):
            return None
