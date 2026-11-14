# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ノードを名前・DAGパス・型で記録し、読み込み先のシーンのノードへ対応づける。"""

import maya.cmds as cmds
from .nameMapping import NameMapping
from mlib.nodes.node import Node
import maya.api.OpenMaya as om2



class NodeRef:
    """ノードを名前・DAGパス・ノード型で記録した参照。

    読み込むときは、:meth:`resolve` が :class:`NameMapping` で変換した名前でシーンを探す。
    同じ名前が複数あれば、変換したDAGパスで絞る。ノード型が違うものは対応させない。
    """
    __hash__: None
    def __init__(self, name: str, path: str | None = ..., type: str | None = ...) -> None:
        """記録する値を持たせる。

        Args:
            name (str): 名前空間付きの短い名前(``"chrA:arm_L_jnt"``)。
            path (str | None): DAGノードの完全パス。DGノードやパスが分からないときはNone。
            type (str | None): ノード型(``"joint"`` など)。Noneなら型を確かめない。

        Raises:
            TypeError: nameが文字列でない場合、またはpath・typeが文字列でもNoneでもない場合。
            ValueError: nameが空の場合、または ``"|"`` を含む場合。
        """
        ...
    def __repr__(self) -> str:
        """名前と型を含む表記を返す。

        Returns:
            str: ``NodeRef('chrA:arm_L_jnt', type='joint')`` の形式。
        """
        ...
    def __eq__(self, other: object) -> bool:
        """名前・パス・型がすべて同じかを返す。

        Args:
            other (object): 比較する値。

        Returns:
            bool: 同じ記録ならTrue。NodeRef以外はNotImplemented。
        """
        ...
    @classmethod
    def capture(cls, node: Node | str | om2.MObject | om2.MDagPath) -> NodeRef:
        """シーンのノードから参照を作る。

        Args:
            node (Node | str | om2.MObject | om2.MDagPath): 記録するノード。

        Returns:
            NodeRef: 名前・パス・型を記録した参照。

        Raises:
            TypeError: nodeが対応しない型の場合。
            ValueError: ノードが無い場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    @classmethod
    def fromData(cls, data: dict) -> NodeRef:
        """:meth:`toData` の辞書から作る。

        Args:
            data (dict): ``name``・``path``・``type`` を持つ辞書。

        Returns:
            NodeRef: 新しい参照。

        Raises:
            ValueError: 辞書の形が正しくない場合。
        """
        ...
    @property
    def name(self) -> str:
        """記録した名前空間付きの短い名前を返す。

        Returns:
            str: ノード名。
        """
        ...
    @property
    def path(self) -> str | None:
        """記録した完全なDAGパスを返す。

        Returns:
            str | None: DGノードやパスが分からないときはNone。
        """
        ...
    @property
    def type(self) -> str | None:
        """記録したノード型を返す。

        Returns:
            str | None: 型を記録していなければNone。
        """
        ...
    def toData(self) -> dict:
        """JSONに書く辞書を返す。

        Returns:
            dict: ``{"name": ..., "path": ..., "type": ...}``。
        """
        ...
    def mappedName(self, mapping: NameMapping | None = ...) -> str:
        """名前の対応づけを当てた名前を返す。

        Args:
            mapping (NameMapping | None): 名前の対応づけ。Noneなら変換しない。

        Returns:
            str: 変換後の名前。警告や報告の表示に使う。
        """
        ...
    def resolve(self, mapping: NameMapping | None = ...) -> Node | None:
        """名前の対応づけを当てた名前で、シーンのノードを探す。

        候補が1つならそれを返す。複数あれば、変換したDAGパスと一致するものを返す。
        記録した型と違うノードは候補にしない。

        Args:
            mapping (NameMapping | None): 名前の対応づけ。Noneなら保存したときの名前で探す。

        Returns:
            Node | None: 見つかったノード。見つからない場合と、1つに絞れない場合はNone。

        Raises:
            TypeError: mappingがNameMappingでもNoneでもない場合。
        """
        ...
