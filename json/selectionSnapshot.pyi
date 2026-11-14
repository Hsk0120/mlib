# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""選択(ノードとコンポーネント)を選択順のまま保存・復元する。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from .. import logger
from .componentRef import ComponentRef
from .nodeRef import NodeRef
from .snapshot import Snapshot, ValidationReport
from typing import Iterable
from mlib.components.component import Component
from mlib.components.component import Components
from mlib.json.nameMapping import NameMapping
from mlib.nodes.node import Node

_COMPONENT_TYPES: tuple


class SelectionSnapshot(Snapshot):
    """選択したノードとコンポーネントを、選択した順に持つ。

    コンポーネントは、頂点・エッジ・フェース・UV・カーブのCVを扱う。
    同じシェイプ・同じ種類のコンポーネントが続いていれば、1つの :class:`ComponentRef` にまとめる。
    NURBSサーフェスのCVのように、番号1つで表せないコンポーネントは保存しない。

    データの形::

        {"items": [{"node": {<NodeRef>}}, {"components": {<ComponentRef>}}, ...]}

    Examples:
        >>> snap = SelectionSnapshot.capture()
        >>> snap.save("selection.json")
        >>> SelectionSnapshot.load("selection.json").apply(namespaceMap={"chrA": "chrB"})
    """
    FORMAT: str
    VERSION: int
    @classmethod
    def capture(cls, items: Iterable[Node | Component | Components | str] | None = ...) -> SelectionSnapshot:
        """今の選択、または指定したノード・コンポーネントを取得する。

        Noneなら、今の選択を選択した順(``ls -orderedSelection``)で取得する。選択の順の記録
        (``selectPref -trackSelectionOrder``)が無効で順番が取れないときは、``ls -selection`` の順にする。

        Args:
            items (Iterable[Node | Component | Components | str] | None): 記録するノード・コンポーネント。
                文字列では ``"pCube1.vtx[0:3]"`` のようなコンポーネントの書き方も使える。Noneなら今の選択。

        Returns:
            SelectionSnapshot: 選択した順の項目を持つ新しいインスタンス。

        Raises:
            TypeError: itemsの型が正しくない場合。
            RuntimeError: 指定したノード・コンポーネントが無い場合。
        """
        ...
    def apply(self, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ...) -> ValidationReport:
        """保存した項目を選択し直す。

        名前を対応づけたシーンのノード・コンポーネントを選び、今の選択と置き換える。
        選べないものは飛ばして記録し、最後にまとめて警告する。見つからないノードは ``missing`` に、
        範囲の外の番号を含むコンポーネントは ``skipped`` に記録する。
        見つかるものが1つも無ければ、選択を解除する。

        Args:
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。
            replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え。
            namespaceMap (dict[str, str] | None): 名前空間の対応。

        Returns:
            ValidationReport: 適用の結果。
        """
        ...
    def _require_data(self, data: dict):
        """``items`` のそれぞれの項目が、ノードかコンポーネントの参照か確かめる。

        Args:
            data (dict): 持たせる前のデータ。

        Raises:
            ValueError: データの形が正しくない場合。
        """
        ...
    def _validate(self, mapping: NameMapping, report: ValidationReport, options: dict):
        """見つからないノードと、範囲の外のコンポーネントを記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 使わない。
        """
        ...
    def _apply(self, mapping: NameMapping, report: ValidationReport, options: dict, fast: bool):
        """見つかった項目で、選択を置き換える。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先(飛ばすものは :meth:`_validate` で記録してある)。
            options (dict): 使わない。
            fast (bool): 使わない。
        """
        ...
    def _plan(self, mapping: NameMapping, report: ValidationReport) -> list[str]:
        """選択する名前を集める。

        見つからないものと、範囲の外のものはreportへ記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。

        Returns:
            list[str]: cmds.selectへ渡す名前(選択した順)。
        """
        ...

def _selection_items(items: Iterable | None) -> list:
    """記録する項目を、順番を保ったlistにする。

    Args:
        items (Iterable | None): 記録する項目。Noneなら今の選択。

    Returns:
        list: 指定した順の項目。

    Raises:
        TypeError: itemsが並びでない場合。
    """
    ...

def _capture_item(item: Node | Component | Components | str | om2.MDagPath | om2.MObject) -> list[NodeRef | ComponentRef]:
    """1つの項目を参照にする。

    Args:
        item (Node | Component | Components | str | om2.MDagPath | om2.MObject): 項目。

    Returns:
        list[NodeRef | ComponentRef]: 参照。保存しない種類のコンポーネントは空list。

    Raises:
        TypeError: 対応しない型の場合。
        RuntimeError: 項目が無い場合。
    """
    ...

def _capture_selection_entry(selection: om2.MSelectionList, index: int, label: str) -> list[NodeRef | ComponentRef]:
    """MSelectionListの1つの項目を参照にする。

    Args:
        selection (om2.MSelectionList): 選択の一覧。
        index (int): 項目の番号。
        label (str): 警告に使う名前。

    Returns:
        list[NodeRef | ComponentRef]: 参照。保存しない種類のコンポーネントは空list。
    """
    ...

def _append_ref(groups: list[NodeRef | ComponentRef], ref: NodeRef | ComponentRef):
    """参照を並びへ足す。

    直前と同じシェイプ・同じ種類のコンポーネントなら、1つにまとめる。

    Args:
        groups (list[NodeRef | ComponentRef]): これまでの参照。この並びを書き換える。
        ref (NodeRef | ComponentRef): 足す参照。
    """
    ...

def _item_data(ref: NodeRef | ComponentRef) -> dict:
    """参照を、選択のデータの1項目にする。

    Args:
        ref (NodeRef | ComponentRef): 参照。

    Returns:
        dict: ``{"node": ...}`` か ``{"components": ...}``。
    """
    ...
