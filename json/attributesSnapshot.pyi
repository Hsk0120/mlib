# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""名前で指定したアトリビュートの値を、型を問わず保存・復元する。"""

from .. import logger
from .codec import encode
from .plugRef import PlugRef
from .poseSnapshot import _block_reason, _require_nodes, _write_plug
from .snapshot import Snapshot, ValidationReport
from typing import Any, Iterable
from mlib.json.nameMapping import NameMapping
from mlib.nodes.node import Node
from mlib.plugs.plug import Plug

_UNSUPPORTED: Any


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
    FORMAT: str
    VERSION: int
    @classmethod
    def capture(cls, nodes: Iterable[Node | Plug | str], attributes: Iterable[str] | None = ...) -> AttributesSnapshot:
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
        ...
    def apply(self, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ...) -> ValidationReport:
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
        ...
    def _require_data(self, data: dict):
        """``plugs`` のそれぞれの項目が、Plugの参照と値を持つか確かめる。

        Args:
            data (dict): 持たせる前のデータ。

        Raises:
            ValueError: データの形が正しくない場合、または値をJSONで書けない場合。
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

def _require_attribute_names(attributes: Iterable[str] | str | None) -> list[str]:
    """アトリビュート名の指定を確かめてlistにする。

    Args:
        attributes (Iterable[str] | str | None): アトリビュート名。

    Returns:
        list[str]: 名前。Noneなら空のlist。

    Raises:
        TypeError: 文字列以外を含む場合。
        ValueError: 空の名前を含む場合。
    """
    ...

def _collect_plugs(nodes: Iterable[Node | Plug | str] | Node | Plug | str, names: list[str]) -> list[Plug]:
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
    ...

def _capture_value(plug: Plug) -> Any:
    """Plugの値を、保存できる形で取得する。

    Args:
        plug (Plug): 対象のPlug。

    Returns:
        object: 値(角度は度、距離はcm)。保存できないものは ``_UNSUPPORTED``。
    """
    ...
