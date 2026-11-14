"""ノードのローカルなアトリビュートの値(ポーズ)を保存・復元する。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from .nodeRef import NodeRef
from .snapshot import Snapshot, ValidationReport


class PoseSnapshot(Snapshot):
    """キーを打てるアトリビュートと、チャンネルボックスに表示されるアトリビュートの値を持つ。

    値はスカラー(数値・bool・enumの番号)だけを扱う。mlibの既定の単位(角度は度、距離はcm)で保存するので、
    保存したとき・適用するときのUIの単位には左右されない。

    ロックされたアトリビュートや、接続されているアトリビュートも保存する。適用するときに書けないものは、
    飛ばして報告する。適用してもキーは打たない。ワールド空間は扱わない。

    データの形::

        {"nodes": [{"node": {<NodeRef>}, "attrs": {"translateX": 1.0, "rotateY": 45.0, ...}}, ...]}

    Examples:
        >>> pose = PoseSnapshot.capture(mlib.ls(type="joint"))
        >>> pose.save("pose.json")
        >>> PoseSnapshot.load("pose.json").apply(namespaceMap={"chrA": "chrB"})
    """

    FORMAT = "mlib.pose"
    VERSION = 1

    @classmethod
    def capture(cls, nodes):
        """ノードのアトリビュートの今の値を取得する。

        対象は、キーを打てるアトリビュートと、チャンネルボックスに表示されるアトリビュート。
        ユーザー定義アトリビュートも含む。値がスカラーでないものは保存しない。
        同じノードを何回か指定した場合は、最初の1回だけ記録する。

        Args:
            nodes (Iterable[Node | str]): 対象のノード。Nodeや名前を1つだけ渡してもよい。

        Returns:
            PoseSnapshot: 取得した値を持つ新しいインスタンス。

        Raises:
            TypeError: nodesがノードでもその並びでもない場合。
            RuntimeError: ノードが無い場合。
        """
        entries = []
        seen = set()
        for node in _require_nodes(nodes):
            full = node.getFullName()
            if full in seen:
                continue
            seen.add(full)
            entries.append({"node": NodeRef.capture(node).toData(), "attrs": _capture_pose_attributes(node)})
        return cls({"nodes": entries})

    def apply(self, *, nameMap=None, replace=None, namespaceMap=None):
        """保存した値を、対応づけたノードのアトリビュートへ書き戻す。

        1回のUndoにまとめる。キーは打たない。書き戻せないものは飛ばして記録し、最後にまとめて警告する。
        見つからないノードは ``missing`` に、ロック・入力接続(アニメカーブを含む)のあるアトリビュートと
        対象に無いアトリビュートは ``skipped`` に記録する。

        Args:
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。
            replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え。
            namespaceMap (dict[str, str] | None): 名前空間の対応。

        Returns:
            ValidationReport: 適用の結果。
        """
        return self._run_apply({"nameMap": nameMap, "replace": replace, "namespaceMap": namespaceMap}, {})

    def _require_data(self, data):
        """``nodes`` のそれぞれの項目が、ノードの参照とスカラー値の辞書を持つか確かめる。

        Args:
            data (dict): 持たせる前のデータ。

        Raises:
            ValueError: データの形が正しくない場合。
        """
        entries = data.get("nodes")
        if not isinstance(entries, list):
            raise ValueError("ポーズのデータには'nodes'のリストが必要です")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("attrs"), dict):
                raise ValueError(f"ポーズの項目が不正です: {entry!r}")
            NodeRef.fromData(entry.get("node"))
            for name, value in entry["attrs"].items():
                if not isinstance(name, str) or not name:
                    raise ValueError(f"ポーズのデータのアトリビュート名が不正です: {name!r}")
                if not isinstance(value, (bool, int, float)):
                    raise ValueError(f"ポーズの値は数値かboolで指定してください: {name!r}={value!r}")

    def _validate(self, mapping, report, options):  # noqa: ARG002  # 基底(Snapshot)の契約で受ける引数。この種類では使わない。
        """見つからないノードと、書けないアトリビュートを記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 使わない。
        """
        self._plan(mapping, report)

    def _apply(self, mapping, report, options, fast):  # noqa: ARG002  # 基底(Snapshot)の契約で受ける引数。この種類では使わない。
        """書けるアトリビュートへ値を書き込む。

        飛ばすものは :meth:`_validate` で記録してあるので、ここでは書き込みに失敗したものだけを記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 使わない。
            fast (bool): 使わない(常にcmdsで書く)。
        """
        for plug, value in self._plan(mapping, ValidationReport()):
            _write_plug(plug, value, report)

    def _plan(self, mapping, report):
        """書き込む (Plug, 値) を集める。

        見つからないものと書けないものは、reportへ記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。

        Returns:
            list[tuple[Plug, object]]: 書き込める組。
        """
        writes = []
        for entry in self._data["nodes"]:
            ref = NodeRef.fromData(entry["node"])
            node = ref.resolve(mapping)
            if node is None:
                report.addMissing(ref.mappedName(mapping))
                continue
            for name, value in entry["attrs"].items():
                plug = _find_plug(node, name)
                label = node.getName() + "." + name
                if plug is None:
                    report.addSkipped(label, "アトリビュートがありません")
                    continue
                reason = _block_reason(plug.mplug())
                if reason:
                    report.addSkipped(label, reason)
                    continue
                writes.append((plug, value))
        return writes


def _require_nodes(nodes):
    """指定したノードを、mlibのNodeのlistにする。

    Args:
        nodes (Iterable[Node | str] | Node | str): 指定したノード。

    Returns:
        list[Node]: 指定した順のNode。

    Raises:
        TypeError: nodesがノードでもその並びでもない場合。
        RuntimeError: ノードが無い場合。
    """
    # 循環参照の回避: nodesはノードのメソッドからmlib.jsonを使うので、使うときに読み込む。
    from ..nodes.node import Node

    if isinstance(nodes, (str, Node)):
        nodes = [nodes]
    try:
        items = list(nodes)
    except TypeError:
        raise TypeError("nodesはノードかノードの並びで指定してください") from None
    return [item if isinstance(item, Node) else Node(item) for item in items]


def _capture_pose_attributes(node):
    """キーを打てるアトリビュートと、チャンネルボックスに表示されるアトリビュートのスカラー値を集める。

    Args:
        node (Node): 対象のノード。

    Returns:
        dict[str, bool | int | float]: ロング名のアトリビュートのパスと値。listAttrの順に並ぶ。
    """
    name = node.getFullName()
    names = (cmds.listAttr(name, keyable=True) or []) + (cmds.listAttr(name, channelBox=True) or [])
    values = {}
    for attribute in names:
        plug = _find_plug(node, attribute)
        if plug is None or plug.mplug().isCompound or plug.mplug().isArray:
            continue
        path = _attribute_path(plug.mplug())
        if path in values:
            continue
        try:
            value = plug.get()
        except (RuntimeError, TypeError, ValueError):
            continue
        if isinstance(value, (bool, int, float)):
            values[path] = value
    return values


def _find_plug(node, attribute):
    """ノードのアトリビュートを探す。

    Args:
        node (Node): 対象のノード。
        attribute (str): アトリビュートのパス。

    Returns:
        Plug | None: 見つかったPlug。無ければNone。
    """
    try:
        return node.getPlug(attribute)
    except (AttributeError, RuntimeError, ValueError):
        return None


def _attribute_path(mplug):
    """ロング名のアトリビュートのパスを返す。ノード名は含めない。

    Args:
        mplug (om2.MPlug): 対象のPlug。

    Returns:
        str: ``"translateX"``・``"weight[3]"`` など。
    """
    return mplug.partialName(includeNodeName=False, includeNonMandatoryIndices=True, includeInstancedIndices=True, useLongNames=True)


def _block_reason(mplug):
    """アトリビュートへ値を書けない理由を返す。

    自身と、コンパウンドアトリビュートの親と子について、ロックと入力接続(アニメカーブを含む)を調べる。

    Args:
        mplug (om2.MPlug): 対象のPlug。

    Returns:
        str | None: ``"locked"``・``"connected"``・``"not settable"``。書けるならNone。
    """
    related = [mplug]
    parent = mplug
    while parent.isChild:
        parent = parent.parent()
        related.append(parent)
    pending = [mplug]
    while pending:
        current = pending.pop()
        if current.isCompound:
            children = [current.child(index) for index in range(current.numChildren())]
            related.extend(children)
            pending.extend(children)
    if any(item.isLocked for item in related):
        return "locked"
    if any(item.isDestination for item in related):
        return "connected"
    if mplug.isFreeToChange() != om2.MPlug.kFreeToChange:
        return "not settable"
    return None


def _write_plug(plug, value, report):
    """値を書き込み、失敗したものをreportへ記録する。

    Args:
        plug (Plug): 書き込み先。
        value (object): mlibの既定の単位の値。
        report (ValidationReport): 記録先。
    """
    try:
        plug.set(value)
    except (RuntimeError, TypeError, ValueError) as error:
        report.addSkipped(plug.getName(), f"failed ({error})")
