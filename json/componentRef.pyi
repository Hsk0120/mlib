# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""コンポーネントの集まりを、シェイプの参照・種類・番号で記録する。"""

from .nameMapping import NameMapping
from .nodeRef import NodeRef
from typing import Iterable
from mlib.components.component import Component
from mlib.components.component import Components

_COLLECTIONS: dict


class ComponentRef:
    """コンポーネントの参照。

    同じシェイプ・同じ種類のコンポーネントを、シェイプの :class:`NodeRef`・種類・番号で記録する。
    種類はMayaの表記(``"vtx"``・``"e"``・``"f"``・``"map"``・``"cv"``)。番号は記録した順のまま保つ。
    名前の対応づけは、シェイプの部分にだけ当てる。
    """
    __hash__: None
    def __init__(self, node: NodeRef, type: str, indices: Iterable[int]) -> None:
        """記録する値を持たせる。

        Args:
            node (NodeRef): シェイプの参照。
            type (str): コンポーネントの種類(``"vtx"`` など)。
            indices (Iterable[int]): 番号。

        Raises:
            TypeError: nodeがNodeRefでない場合、または番号がintでない場合(boolも不可)。
            ValueError: 種類が対応していないものの場合、または番号が負の場合。
        """
        ...
    def __repr__(self) -> str:
        """シェイプ名・種類・番号の数を含む表記を返す。

        Returns:
            str: ``ComponentRef('chrA:bodyShape', 'vtx', 12 indices)`` の形式。
        """
        ...
    def __eq__(self, other: object) -> bool:
        """シェイプの参照・種類・番号が同じかを返す。

        Args:
            other (object): 比較する値。

        Returns:
            bool: 同じ記録ならTrue。ComponentRef以外はNotImplemented。
        """
        ...
    @classmethod
    def capture(cls, components: Component | Components) -> ComponentRef:
        """mlibのコンポーネントか、その集まりから参照を作る。

        Args:
            components (Component | Components): 記録するコンポーネント。

        Returns:
            ComponentRef: シェイプ・種類・番号を記録した参照。

        Raises:
            TypeError: componentsがmlibのコンポーネントでない場合。
            ValueError: 種類が記録できないものの場合。
        """
        ...
    @classmethod
    def fromData(cls, data: dict) -> ComponentRef:
        """:meth:`toData` の辞書から作る。

        Args:
            data (dict): ``node``・``type``・``indices`` を持つ辞書。

        Returns:
            ComponentRef: 新しい参照。

        Raises:
            ValueError: 辞書の形が正しくない場合。
        """
        ...
    @property
    def node(self) -> NodeRef:
        """シェイプの参照を返す。

        Returns:
            NodeRef: 持っている参照。
        """
        ...
    @property
    def type(self) -> str:
        """コンポーネントの種類を返す。

        Returns:
            str: ``"vtx"``・``"e"``・``"f"``・``"map"``・``"cv"``。
        """
        ...
    @property
    def indices(self) -> tuple[int, ...]:
        """記録した番号を返す。

        Returns:
            tuple[int, ...]: 記録した順の番号。
        """
        ...
    def toData(self) -> dict:
        """JSONに書く辞書を返す。

        Returns:
            dict: ``{"node": {...}, "type": ..., "indices": [...]}``。
        """
        ...
    def mappedName(self, mapping: NameMapping | None = ...) -> str:
        """名前の対応づけを当てたシェイプ名と、種類を返す。

        Args:
            mapping (NameMapping | None): 名前の対応づけ。

        Returns:
            str: ``<シェイプ名>.<種類>[...]``。警告や報告の表示に使う。
        """
        ...
    def resolve(self, mapping: NameMapping | None = ...) -> Components | None:
        """シーンのコンポーネントの集まりを返す。

        名前の対応づけを当てたシェイプから、記録した番号のコンポーネントを取得する。

        Args:
            mapping (NameMapping | None): 名前の対応づけ。

        Returns:
            Components | None: ``Vertices`` などの集まり。シェイプが無い場合、型が合わない場合、
                番号が範囲の外の場合はNone。

        Raises:
            TypeError: mappingがNameMappingでもNoneでもない場合。
        """
        ...
