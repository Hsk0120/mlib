"""選択(ノードとコンポーネント)を選択順のまま保存・復元する。"""

import re

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from .. import logger
from .componentRef import ComponentRef
from .nodeRef import NodeRef
from .snapshot import Snapshot, ValidationReport

#: 記録するコンポーネントのMFn型と、Mayaの表記。
#: 名前の末尾の、コンポーネントの番号(``[3]``・``[0:7]``)。
_INDEX_PATTERN = re.compile(r"\[([0-9:]+)\]$")
_COMPONENT_TYPES = (
    (om2.MFn.kMeshVertComponent, "vtx"),
    (om2.MFn.kMeshEdgeComponent, "e"),
    (om2.MFn.kMeshPolygonComponent, "f"),
    (om2.MFn.kMeshMapComponent, "map"),
    (om2.MFn.kCurveCVComponent, "cv"),
)


class SelectionSnapshot(Snapshot):
    """選択したノードとコンポーネントを、選択した順に持つ。

    コンポーネントは、頂点・エッジ・フェース・UV・カーブのCVを扱う。
    同じシェイプ・同じ種類のコンポーネントが続いていれば、1つの :class:`ComponentRef` にまとめる。
    NURBSサーフェスのCVのように、番号1つで表せないコンポーネントは保存しない(名前で渡しても、mlibの
    コンポーネントで渡しても、警告して省く)。

    ``apply`` は、保存した項目を選択し直す。

    名前を対応づけたシーンのノード・コンポーネントを選び、今の選択と置き換える。
    選べないものは飛ばして記録し、最後にまとめて警告する。見つからないノードは ``missing`` に、
    範囲の外の番号を含むコンポーネントは ``skipped`` に記録する。
    見つかるものが1つも無ければ、選択を解除する。

    データの形::

        {"items": [{"node": {<NodeRef>}}, {"components": {<ComponentRef>}}, ...]}

    Examples:
        >>> snap = SelectionSnapshot.capture()
        >>> snap.save("selection.json")
        >>> SelectionSnapshot.load("selection.json").apply(namespaceMap={"chrA": "chrB"})
    """

    FORMAT = "mlib.selection"
    VERSION = 1

    @classmethod
    def capture(cls, items=None):
        """今の選択、または指定したノード・コンポーネントを取得する。

        Noneなら、今の選択を選択した順(``ls -orderedSelection``)で取得する。選択の順の記録
        (``selectPref -trackSelectionOrder``)が無効で順番が取れないときは、``ls -selection`` の順にする。

        Args:
            items (Iterable[Node | Component | Components | str] | None): 記録するノード・コンポーネント。
                文字列では ``"pCube1.vtx[0:3]"`` のようなコンポーネントの書き方も使える。Noneなら今の選択。既定はNone。

        Returns:
            SelectionSnapshot: 選択した順の項目を持つ新しいインスタンス。

        Raises:
            TypeError: itemsの型が正しくない場合。
            RuntimeError: 指定したノード・コンポーネントが無い場合。
        """
        groups = []
        for item in _selection_items(items):
            for ref in _capture_item(item):
                _append_ref(groups, ref)
        return cls({"items": [_item_data(ref) for ref in groups]})

    def _require_data(self, data):
        """``items`` のそれぞれの項目が、ノードかコンポーネントの参照か確かめる。

        Args:
            data (dict): 持たせる前のデータ。

        Raises:
            ValueError: データの形が正しくない場合。
        """
        entries = data.get("items")
        if not isinstance(entries, list):
            raise ValueError("選択のデータには'items'のリストが必要です")
        for entry in entries:
            if not isinstance(entry, dict) or len(entry) != 1:
                raise ValueError(f"選択の項目が不正です: {entry!r}")
            if "node" in entry:
                NodeRef._from_data(entry["node"])
            elif "components" in entry:
                ComponentRef._from_data(entry["components"])
            else:
                raise ValueError(f"選択の項目が不正です: {entry!r}")

    def _validate(self, mapping, report, options):  # noqa: ARG002  # 基底(Snapshot)の契約で受ける引数。この種類では使わない。
        """見つからないノードと、範囲の外のコンポーネントを記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 使わない。
        """
        self._plan(mapping, report)

    def _apply(self, mapping, report, options, fast):  # noqa: ARG002  # 基底(Snapshot)の契約で受ける引数。この種類では使わない。
        """見つかった項目で、選択を置き換える。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先(飛ばすものは :meth:`_validate` で記録してある)。
            options (dict): 使わない。
            fast (bool): 使わない。
        """
        names = self._plan(mapping, ValidationReport())
        if names:
            cmds.select(names, replace=True)
        else:
            cmds.select(clear=True)

    def _plan(self, mapping, report):
        """選択する名前を集める。

        見つからないものと、範囲の外のものはreportへ記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。

        Returns:
            list[str]: cmds.selectへ渡す名前(選択した順)。
        """
        names = []
        for entry in self._data["items"]:
            if "node" in entry:
                ref = NodeRef._from_data(entry["node"])
                node = ref.resolve(mapping)
                if node is None:
                    report._add_missing(ref._mapped_name(mapping))
                else:
                    names.append(node._full_name())
                continue
            ref = ComponentRef._from_data(entry["components"])
            if ref.node.resolve(mapping) is None:
                report._add_missing(ref.node._mapped_name(mapping))
                continue
            components = ref.resolve(mapping)
            if components is None:
                report._add_skipped(ref._mapped_name(mapping), "番号が範囲外です")
                continue
            names.extend(str(component) for component in components)
        return names


def _selection_items(items):
    """記録する項目を、順番を保ったlistにする。

    Args:
        items (Iterable | None): 記録する項目。Noneなら今の選択。

    Returns:
        list: 指定した順の項目。

    Raises:
        TypeError: itemsが並びでない場合。
    """
    if items is None:
        return cmds.ls(orderedSelection=True, long=True) or cmds.ls(selection=True, long=True) or []
    # 循環参照の回避: components・nodesはノードのメソッドからmlib.jsonを使うので、使うときに読み込む。
    from ..components import Component, Components
    from ..nodes.node import Node

    if isinstance(items, (str, Node, Component, Components)):
        return [items]
    try:
        return list(items)
    except TypeError:
        raise TypeError("itemsはノードかコンポーネントの並びで指定してください") from None


def _capture_item(item):
    """1つの項目を参照にする。

    Args:
        item (Node | Component | Components | str | om2.MDagPath | om2.MObject): 項目。

    Returns:
        list[NodeRef | ComponentRef]: 参照。保存しない種類のコンポーネントは空list。

    Raises:
        TypeError: 対応しない型の場合。
        RuntimeError: 項目が無い場合。
    """
    # 循環参照の回避: components・nodesはノードのメソッドからmlib.jsonを使うので、使うときに読み込む。
    from ..components import Component, Components
    from ..nodes.node import Node

    if isinstance(item, (Component, Components)):
        try:
            return [ComponentRef.capture(item)]
        except ValueError:
            # 名前で渡したときと同じく、保存しない種類(曲面のCVなど)は警告して省く。
            logger.warning("SelectionSnapshot: 対応していないコンポーネント%sを省きました", item)
            return []
    if isinstance(item, (Node, om2.MObject, om2.MDagPath)):
        return [NodeRef.capture(item)]
    if not isinstance(item, str):
        raise TypeError(f"{type(item).__name__}は選択として記録できません")
    selection = om2.MSelectionList()
    try:
        selection.add(item)
    except RuntimeError:
        raise RuntimeError(f"ノードが見つかりません: {item}") from None
    # Maya は範囲の外の番号を最後の要素へ丸めて受け付けるため、書いた番号の最大を後で確かめる。
    match = _INDEX_PATTERN.search(item)
    requested = max(int(number) for number in match.group(1).split(":") if number) if match else None
    refs = []
    for index in range(selection.length()):
        refs.extend(_capture_selection_entry(selection, index, item, requested))
    return refs


def _capture_selection_entry(selection, index, label, requested=None):
    """MSelectionListの1つの項目を参照にする。

    Args:
        selection (om2.MSelectionList): 選択の一覧。
        index (int): 項目の番号。
        label (str): 警告に使う名前。
        requested (int | None): 名前に書いた番号の最大。範囲の外かを確かめる。Noneなら確かめない。

    Returns:
        list[NodeRef | ComponentRef]: 参照。保存しない種類のコンポーネントは空list。

    Raises:
        RuntimeError: コンポーネントの番号が範囲の外の場合。
    """
    try:
        dag_path, component = selection.getComponent(index)
    except (RuntimeError, TypeError):
        # DGノードはDAGパスを持たない。
        return [NodeRef.capture(selection.getDependNode(index))]
    if component.isNull():
        return [NodeRef.capture(dag_path)]
    kind = next((name for fn_type, name in _COMPONENT_TYPES if component.apiType() == fn_type), None)
    if kind is None:
        logger.warning("SelectionSnapshot: 対応していないコンポーネント%sを省きました", label)
        return []
    shape = om2.MDagPath(dag_path)
    if not shape.node().hasFn(om2.MFn.kShape):
        shape.extendToShape()
    indices = om2.MFnSingleIndexedComponent(component).getElements()
    ref = ComponentRef(NodeRef.capture(shape), kind, list(indices))
    if requested is not None and ComponentRef(ref.node, kind, [requested]).resolve() is None:
        raise RuntimeError(f"コンポーネントの番号が範囲の外です: {label}")
    return [ref]


def _append_ref(groups, ref):
    """参照を並びへ足す。

    直前と同じシェイプ・同じ種類のコンポーネントなら、1つにまとめる。

    Args:
        groups (list[NodeRef | ComponentRef]): これまでの参照。この並びを書き換える。
        ref (NodeRef | ComponentRef): 足す参照。
    """
    if isinstance(ref, ComponentRef) and groups and isinstance(groups[-1], ComponentRef):
        last = groups[-1]
        if last.node == ref.node and last.type == ref.type:
            indices = list(last.indices)
            indices.extend(index for index in ref.indices if index not in last.indices)
            groups[-1] = ComponentRef(last.node, last.type, indices)
            return
    groups.append(ref)


def _item_data(ref):
    """参照を、選択のデータの1項目にする。

    Args:
        ref (NodeRef | ComponentRef): 参照。

    Returns:
        dict: ``{"node": ...}`` か ``{"components": ...}``。
    """
    if isinstance(ref, ComponentRef):
        return {"components": ref._to_data()}
    return {"node": ref._to_data()}
