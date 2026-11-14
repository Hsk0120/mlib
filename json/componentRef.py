"""コンポーネントの集まりを、シェイプの参照・種類・番号で記録する。"""

from .nameMapping import NameMapping
from .nodeRef import NodeRef

#: 記録するコンポーネントの種類(Mayaの表記)と、mlibの集まりのクラス名。
_COLLECTIONS = {"vtx": "Vertices", "e": "Edges", "f": "Faces", "map": "UVs", "cv": "CVs"}


class ComponentRef:
    """コンポーネントの参照。

    同じシェイプ・同じ種類のコンポーネントを、シェイプの :class:`NodeRef`・種類・番号で記録する。
    種類はMayaの表記(``"vtx"``・``"e"``・``"f"``・``"map"``・``"cv"``)。番号は記録した順のまま保つ。
    名前の対応づけは、シェイプの部分にだけ当てる。
    """

    __hash__ = None  # type: ignore[assignment]

    def __init__(self, node, type, indices):
        """記録する値を持たせる。

        Args:
            node (NodeRef): シェイプの参照。
            type (str): コンポーネントの種類(``"vtx"`` など)。
            indices (Iterable[int]): 番号。

        Raises:
            TypeError: nodeがNodeRefでない場合、または番号がintでない場合(boolも不可)。
            ValueError: 種類が対応していないものの場合、または番号が負の場合。
        """
        if not isinstance(node, NodeRef):
            raise TypeError("nodeはNodeRefで指定してください")
        if type not in _COLLECTIONS:
            raise ValueError(f"対応していないコンポーネントの種類です: {type!r}({sorted(_COLLECTIONS)}のどれかを指定します)")
        values = []
        for index in indices:
            if isinstance(index, bool) or not isinstance(index, int):
                raise TypeError("コンポーネントの番号はintで指定してください")
            if index < 0:
                raise ValueError("コンポーネントの番号は0以上で指定してください")
            values.append(index)
        self._node = node
        self._type = type
        self._indices = tuple(values)

    def __repr__(self):
        """シェイプ名・種類・番号の数を含む表記を返す。

        Returns:
            str: ``ComponentRef('chrA:bodyShape', 'vtx', 12 indices)`` の形式。
        """
        return f"ComponentRef({self._node.name!r}, {self._type!r}, {len(self._indices)} indices)"

    def __eq__(self, other):
        """シェイプの参照・種類・番号が同じかを返す。

        Args:
            other (object): 比較する値。

        Returns:
            bool: 同じ記録ならTrue。ComponentRef以外はNotImplemented。
        """
        if not isinstance(other, ComponentRef):
            return NotImplemented
        return (self._node, self._type, self._indices) == (other._node, other._type, other._indices)

    @classmethod
    def capture(cls, components):
        """mlibのコンポーネントか、その集まりから参照を作る。

        Args:
            components (Component | Components): 記録するコンポーネント。

        Returns:
            ComponentRef: シェイプ・種類・番号を記録した参照。

        Raises:
            TypeError: componentsがmlibのコンポーネントでない場合。
            ValueError: 種類が記録できないものの場合。
        """
        # 循環参照の回避: componentsはnodesを通してmlib.jsonを使うので、使うときに読み込む。
        from ..components import Component, Components

        if isinstance(components, Component):
            shape, kind, indices = components.shape, components.component_type, [components.index]
        elif isinstance(components, Components):
            shape = components.shape
            kind = components.component_class.component_type
            indices = list(components.indices)
        else:
            raise TypeError("componentsはmlibのComponentかComponentsで指定してください")
        return cls(NodeRef.capture(shape), kind, indices)

    @classmethod
    def fromData(cls, data):
        """:meth:`toData` の辞書から作る。

        Args:
            data (dict): ``node``・``type``・``indices`` を持つ辞書。

        Returns:
            ComponentRef: 新しい参照。

        Raises:
            ValueError: 辞書の形が正しくない場合。
        """
        if not isinstance(data, dict) or "node" not in data or not isinstance(data.get("indices"), list):
            raise ValueError(f"JSONのコンポーネントの参照が不正です: {data!r}")
        try:
            return cls(NodeRef.fromData(data["node"]), data.get("type"), data["indices"])
        except TypeError as error:
            raise ValueError(f"JSONのコンポーネントの参照が不正です: {data!r}") from error

    @property
    def node(self):
        """シェイプの参照を返す。

        Returns:
            NodeRef: 持っている参照。
        """
        return self._node

    @property
    def type(self):
        """コンポーネントの種類を返す。

        Returns:
            str: ``"vtx"``・``"e"``・``"f"``・``"map"``・``"cv"``。
        """
        return self._type

    @property
    def indices(self):
        """記録した番号を返す。

        Returns:
            tuple[int, ...]: 記録した順の番号。
        """
        return self._indices

    def toData(self):
        """JSONに書く辞書を返す。

        Returns:
            dict: ``{"node": {...}, "type": ..., "indices": [...]}``。
        """
        return {"node": self._node.toData(), "type": self._type, "indices": list(self._indices)}

    def mappedName(self, mapping=None):
        """名前の対応づけを当てたシェイプ名と、種類を返す。

        Args:
            mapping (NameMapping | None): 名前の対応づけ。

        Returns:
            str: ``<シェイプ名>.<種類>[...]``。警告や報告の表示に使う。
        """
        return f"{self._node.mappedName(mapping)}.{self._type}[...]"

    def resolve(self, mapping=None):
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
        if mapping is not None and not isinstance(mapping, NameMapping):
            raise TypeError("mappingはNameMappingかNoneで指定してください")
        shape = self._node.resolve(mapping)
        if shape is None:
            return None
        # 循環参照の回避: componentsはnodesを通してmlib.jsonを使うので、使うときに読み込む。
        from .. import components

        try:
            return getattr(components, _COLLECTIONS[self._type])(shape, self._indices)
        except (IndexError, TypeError, RuntimeError):
            return None
