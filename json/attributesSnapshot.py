"""名前で指定したアトリビュートの値を、型を問わず保存・復元する。"""

from .. import logger
from .codec import encode
from .plugRef import PlugRef
from .poseSnapshot import _block_reason, _require_nodes, _write_plug
from .snapshot import Snapshot, ValidationReport

#: 保存しない値の目印。
_UNSUPPORTED = object()


class AttributesSnapshot(Snapshot):
    """指定したアトリビュートの値を持つ。

    キーを打てるかどうかや、型は問わない。扱える値は、数値・bool・enumの番号・文字列・マトリクス・
    double3などのコンパウンドアトリビュート・型付きのデータ(doubleArrayなど)。
    角度は度、距離はcmで保存する(:meth:`Plug.get` の既定)。

    ユーザー定義アトリビュートの定義(addAttr)は保存しない。そのため、適用先に無いアトリビュートは飛ばす。
    マルチアトリビュート全体・message・値の無いものは保存しない。

    データの形::

        {"plugs": [{"plug": {<PlugRef>}, "value": <値>}, ...]}

    Examples:
        >>> snap = AttributesSnapshot.capture(mlib.ls(type="joint"), ["radius", "visibility"])
        >>> snap.save("attrs.json")
        >>> AttributesSnapshot.load("attrs.json").apply()
    """

    FORMAT = "mlib.attributes"
    VERSION = 1

    @classmethod
    def capture(cls, nodes, attributes=None):
        """指定したアトリビュートの今の値を取得する。

        ``nodes`` のそれぞれのノードで、``attributes`` のそれぞれの名前を探す。ノードに無い名前は飛ばす。
        ``nodes`` にPlug(または ``"node.attr"`` の文字列)を入れると、そのPlugだけを記録する。
        同じPlugは、最初の1回だけ記録する。

        Args:
            nodes (Iterable[Node | Plug | str]): 対象のノードかPlug。1つだけ渡してもよい。
            attributes (Iterable[str] | None): それぞれのノードで記録するアトリビュートの名前かパス。
                NoneならPlugだけを記録する。

        Returns:
            AttributesSnapshot: 取得した値を持つ新しいインスタンス。

        Raises:
            TypeError: nodes・attributesの型が正しくない場合。
            ValueError: attributesを指定せずにノードを渡した場合。
            RuntimeError: ノードが無い場合。
            MissingAttributeError: 指定したPlugが無い場合。
        """
        names = _require_attribute_names(attributes)
        entries = []
        seen = set()
        for plug in _collect_plugs(nodes, names):
            key = PlugRef.capture(plug)
            identity = (plug.getNode().getFullName(), key.attribute)
            if identity in seen:
                continue
            seen.add(identity)
            value = _capture_value(plug)
            if value is not _UNSUPPORTED:
                entries.append({"plug": key.toData(), "value": value})
        return cls({"plugs": entries})

    def apply(self, *, nameMap=None, replace=None, namespaceMap=None):
        """保存した値を、対応づけたノードのアトリビュートへ書き戻す。

        1回のUndoにまとめる。書き戻せないものは飛ばして記録し、最後にまとめて警告する。
        見つからないノードは ``missing`` に、ロック・入力接続のあるアトリビュートと対象に無いアトリビュートは
        ``skipped`` に記録する。

        Args:
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。
            replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え。
            namespaceMap (dict[str, str] | None): 名前空間の対応。

        Returns:
            ValidationReport: 適用の結果。
        """
        return self._run_apply({"nameMap": nameMap, "replace": replace, "namespaceMap": namespaceMap}, {})

    def _require_data(self, data):
        """``plugs`` のそれぞれの項目が、Plugの参照と値を持つか確かめる。

        Args:
            data (dict): 持たせる前のデータ。

        Raises:
            ValueError: データの形が正しくない場合、または値をJSONで書けない場合。
        """
        entries = data.get("plugs")
        if not isinstance(entries, list):
            raise ValueError("アトリビュートのデータには'plugs'のリストが必要です")
        for entry in entries:
            if not isinstance(entry, dict) or "value" not in entry:
                raise ValueError(f"アトリビュートの項目が不正です: {entry!r}")
            PlugRef.fromData(entry.get("plug"))
            try:
                encode(entry["value"])
            except TypeError as error:
                raise ValueError(f"JSONのアトリビュートの値が不正です: {entry['value']!r}") from error

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
        for entry in self._data["plugs"]:
            ref = PlugRef.fromData(entry["plug"])
            node = ref.node.resolve(mapping)
            if node is None:
                report.addMissing(ref.node.mappedName(mapping))
                continue
            label = node.getName() + "." + ref.attribute
            plug = ref.resolve(mapping)
            if plug is None:
                report.addSkipped(label, "アトリビュートがありません")
                continue
            reason = _block_reason(plug.mplug())
            if reason:
                report.addSkipped(label, reason)
                continue
            if entry["value"] is None:
                report.addSkipped(label, "値がありません")
                continue
            writes.append((plug, entry["value"]))
        return writes


def _require_attribute_names(attributes):
    """アトリビュート名の指定を確かめてlistにする。

    Args:
        attributes (Iterable[str] | str | None): アトリビュート名。

    Returns:
        list[str]: 名前。Noneなら空のlist。

    Raises:
        TypeError: 文字列以外を含む場合。
        ValueError: 空の名前を含む場合。
    """
    if attributes is None:
        return []
    if isinstance(attributes, str):
        attributes = [attributes]
    try:
        names = list(attributes)
    except TypeError:
        raise TypeError("attributesはアトリビュート名の並びで指定してください") from None
    for name in names:
        if not isinstance(name, str):
            raise TypeError("アトリビュート名は文字列で指定してください")
        if not name:
            raise ValueError("アトリビュート名は空にできません")
    return names


def _collect_plugs(nodes, names):
    """指定したノード・Plugから、記録するPlugを集める。

    指定した順に並べる。

    Args:
        nodes (Iterable[Node | Plug | str] | Node | Plug | str): 対象。
        names (list[str]): 各ノードで探すアトリビュート名。

    Returns:
        list[Plug]: 記録するPlug。ノードに無い名前は含めない。

    Raises:
        TypeError: nodesの型が正しくない場合。
        ValueError: namesが空なのにノードを渡した場合。
        RuntimeError: ノード・Plugが無い場合。
    """
    # 循環参照の回避: plugs・cmdsはノードのメソッドからmlib.jsonを使うので、使うときに読み込む。
    from ..cmds import getPlug
    from ..nodes.node import Node
    from ..plugs.plug import Plug

    if isinstance(nodes, (str, Node, Plug)):
        nodes = [nodes]
    try:
        nodes = list(nodes)
    except TypeError:
        raise TypeError("nodesはノードか、Plugか、それらの並びで指定してください") from None
    result = []
    for item in nodes:
        if isinstance(item, Plug):
            result.append(item)
            continue
        if isinstance(item, str) and "." in item:
            result.append(getPlug(item))
            continue
        if not names:
            raise ValueError("nodesを指定する場合はattributesが必要です")
        node = _require_nodes(item)[0]
        for name in names:
            try:
                result.append(node.getPlug(name))
            except (AttributeError, RuntimeError, ValueError):
                continue
    return result


def _capture_value(plug):
    """Plugの値を、保存できる形で取得する。

    Args:
        plug (Plug): 対象のPlug。

    Returns:
        object: 値(角度は度、距離はcm)。保存できないものは ``_UNSUPPORTED``。
    """
    name = plug.getName()
    if plug.mplug().isArray:
        logger.warning("AttributesSnapshot: マルチアトリビュート%sを省きました(要素を個別に指定してください)", name)
        return _UNSUPPORTED
    if plug.getType() == "message":
        logger.warning("AttributesSnapshot: messageアトリビュート%sを省きました", name)
        return _UNSUPPORTED
    try:
        value = plug.get()
        encode(value)
    except (RuntimeError, TypeError, ValueError) as error:
        logger.warning("AttributesSnapshot: %sを省きました(%s)", name, error)
        return _UNSUPPORTED
    if value is None:
        logger.warning("AttributesSnapshot: %sを省きました(値がありません)", name)
        return _UNSUPPORTED
    return value
