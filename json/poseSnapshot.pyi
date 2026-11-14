# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ノードのローカルなアトリビュートの値(ポーズ)を保存・復元する。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from .nodeRef import NodeRef
from .snapshot import Snapshot, ValidationReport
from typing import Iterable
from mlib.json.nameMapping import NameMapping
from mlib.nodes.node import Node
from mlib.plugs.plug import Plug



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
    FORMAT: str
    VERSION: int
    @classmethod
    def capture(cls, nodes: Iterable[Node | str]) -> PoseSnapshot:
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
        ...
    def apply(self, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ...) -> ValidationReport:
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
        ...
    def _require_data(self, data: dict):
        """``nodes`` のそれぞれの項目が、ノードの参照とスカラー値の辞書を持つか確かめる。

        Args:
            data (dict): 持たせる前のデータ。

        Raises:
            ValueError: データの形が正しくない場合。
        """
        ...
    def _validate(self, mapping: NameMapping, report: ValidationReport, options: dict):
        """見つからないノードと、書けないアトリビュートを記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 使わない。
        """
        ...
    def _apply(self, mapping: NameMapping, report: ValidationReport, options: dict, fast: bool):
        """書けるアトリビュートへ値を書き込む。

        飛ばすものは :meth:`_validate` で記録してあるので、ここでは書き込みに失敗したものだけを記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 使わない。
            fast (bool): 使わない(常にcmdsで書く)。
        """
        ...
    def _plan(self, mapping: NameMapping, report: ValidationReport) -> list[tuple[Plug, object]]:
        """書き込む (Plug, 値) を集める。

        見つからないものと書けないものは、reportへ記録する。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。

        Returns:
            list[tuple[Plug, object]]: 書き込める組。
        """
        ...

def _require_nodes(nodes: Iterable[Node | str] | Node | str) -> list[Node]:
    """指定したノードを、mlibのNodeのlistにする。

    Args:
        nodes (Iterable[Node | str] | Node | str): 指定したノード。

    Returns:
        list[Node]: 指定した順のNode。

    Raises:
        TypeError: nodesがノードでもその並びでもない場合。
        RuntimeError: ノードが無い場合。
    """
    ...

def _capture_pose_attributes(node: Node) -> dict[str, bool | int | float]:
    """キーを打てるアトリビュートと、チャンネルボックスに表示されるアトリビュートのスカラー値を集める。

    Args:
        node (Node): 対象のノード。

    Returns:
        dict[str, bool | int | float]: ロング名のアトリビュートのパスと値。listAttrの順に並ぶ。
    """
    ...

def _find_plug(node: Node, attribute: str) -> Plug | None:
    """ノードのアトリビュートを探す。

    Args:
        node (Node): 対象のノード。
        attribute (str): アトリビュートのパス。

    Returns:
        Plug | None: 見つかったPlug。無ければNone。
    """
    ...

def _attribute_path(mplug: om2.MPlug) -> str:
    """ロング名のアトリビュートのパスを返す。ノード名は含めない。

    Args:
        mplug (om2.MPlug): 対象のPlug。

    Returns:
        str: ``"translateX"``・``"weight[3]"`` など。
    """
    ...

def _block_reason(mplug: om2.MPlug) -> str | None:
    """アトリビュートへ値を書けない理由を返す。

    自身と、コンパウンドアトリビュートの親と子について、ロックと入力接続(アニメカーブを含む)を調べる。

    Args:
        mplug (om2.MPlug): 対象のPlug。

    Returns:
        str | None: ``"locked"``・``"connected"``・``"not settable"``。書けるならNone。
    """
    ...

def _write_plug(plug: Plug, value: object, report: ValidationReport):
    """値を書き込み、失敗したものをreportへ記録する。

    Args:
        plug (Plug): 書き込み先。
        value (object): mlibの既定の単位の値。
        report (ValidationReport): 記録先。
    """
    ...
