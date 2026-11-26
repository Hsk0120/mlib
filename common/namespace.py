"""Maya の名前空間を取得・作成・移動・削除する。"""

import re
from contextlib import contextmanager

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.nodeEdit import check_deletion
from ..decorator import _require_bool, undoChunk

#: 名前空間の1つの階層に使える名前(ASCIIの英字か_で始まり、英数字と_が続く)。
_LEGAL_SEGMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class Namespace:
    """Mayaの名前空間(namespace)を表すオブジェクト。"""

    def __init__(self, name=":"):
        """名前空間の名前を決まった形に揃えて、オブジェクトを作る。

        名前を持つだけで、シーンに名前空間を作ったり、存在するかを確かめたりはしない。

        Args:
            name (str | Namespace): 名前空間の名前、または既存のオブジェクト。既定の : はルート。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 文字列でもNamespaceでもない場合。
            ValueError: 空文字列の場合。
        """
        if isinstance(name, Namespace):
            name = name.name
        if not isinstance(name, str):
            raise TypeError("nameはstrで指定してください")
        if not name:
            raise ValueError("nameは空でない文字列で指定してください")
        self._name = self._normalize(name)

    def __repr__(self):
        """デバッグ用の表示を返す。

        Returns:
            str: Namespace と、持っている名前を含む文字列。
        """
        return f"Namespace({self._name!r})"

    def __str__(self):
        """名前空間の絶対名を返す。

        Returns:
            str: 揃えた形の、持っている名前。存在するかは確かめない。
        """
        return self._name

    def __eq__(self, other):
        """名前空間の名前で、同じものか判定する。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | types.NotImplementedType: Namespace どうしなら、持っている名前を比べる。型が違えば NotImplemented。
        """
        if not isinstance(other, Namespace):
            return NotImplemented
        return self._name == other._name

    def __hash__(self):
        """名前空間の名前からハッシュ値を返す。

        Returns:
            int: 今持っている名前のハッシュ。rename/setParent で変わるため、集合や辞書のキーに入れている間は
                名前を変えないこと。
        """
        return hash(self._name)

    @classmethod
    def getCurrent(cls):
        """カレントの名前空間を取得する。

        Returns:
            Namespace: 今のカレントの名前空間。
        """
        return cls(om2.MNamespace.currentNamespace())

    @classmethod
    def create(cls, name, parent=":"):
        """指定した名前空間を作る。すでにあれば作らず、そのオブジェクトを返す。

        カレントの名前空間は変えない。/ は : と同じ区切りとして扱う。
        cmds.namespaceを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Args:
            name (str | Namespace): 作る名前空間。相対名ならparentの下に作る。
                絶対名とNamespaceのオブジェクトでは、parentを無視する。何階層もある名前も指定できる。
            parent (str | Namespace): 作る場所の親。相対名の文字列は、カレントから数える。
                既定はルート(:)。存在しない親も、上から順に作る。

        Returns:
            Namespace: 作った(またはすでにあった)名前空間の完全名を持つオブジェクト。

        Raises:
            TypeError: name・parentが文字列でもNamespaceでもない場合。
            ValueError: name・parentが空、使えない文字(英数字と_以外・先頭の数字)を含む、または空の階層(``a::b``)を含む場合。
            RuntimeError: Mayaが作成を拒否した場合。
        """
        _require_name(name, "name")
        _require_name(parent, "parent")
        with undoChunk("mlibNamespaceCreate"):
            return cls._create(name, parent)

    @property
    def name(self):
        """揃えた形の、名前空間の絶対名を返す。

        Returns:
            str: 先頭が : の、持っている名前。
        """
        return self._name

    def exists(self):
        """名前空間がシーンに存在するか調べる。

        Returns:
            bool: 持っている名前の名前空間が、今のシーンにあれば True。
        """
        return bool(om2.MNamespace.namespaceExists(self._name))

    def getParent(self, *, all=False):
        """親の名前空間を返す。ルートの親は ``None``。

        ``all=True`` なら、祖先(親・親の親…ルートまで)を近い順にすべて返す
        (:meth:`DagNode.getParent(all=True) <mlib.nodes.dagNode.DagNode.getParent>` と同じ考え方)。

        Args:
            all (bool): Trueなら、祖先を近い順にすべて返す。ルート(``:``)も含む。既定はFalse。

        Returns:
            Namespace | list[Namespace] | None: 名前から求めた親。ルートでは None。親が存在するかは確かめない。
                all=Trueなら祖先を近い順に並べた新しいリスト(ルートでは空リスト)。

        Raises:
            TypeError: allがboolでない場合。
        """
        _require_bool(all, "all")
        if all:
            ancestors = []
            parent = self.getParent()
            while parent is not None:
                ancestors.append(parent)
                parent = parent.getParent()
            return ancestors
        if self._name == ":":
            return None
        parent_name = self._name.rsplit(":", 1)[0] or ":"
        return Namespace(parent_name)

    def setParent(self, parent=":"):
        """この名前空間を、指定した親の名前空間の下へ移す(親を変える)。

        :meth:`getParent` と対になる。

        cmdsを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Args:
            parent (str | Namespace): 移動先の、既存の親の名前空間。自身の最後の階層の名前はそのままにする。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: parentが文字列でもNamespaceでもない場合。
            ValueError: ルートを移動しようとした場合、または parent が正しくない場合。
            RuntimeError: 親が存在しない場合、移動先がすでにある場合、または Maya の操作が失敗した場合。
        """
        _require_name(parent, "parent")
        with undoChunk("mlibNamespaceSetParent"):
            if self._name == ":":
                raise ValueError("ルートの名前空間は移動できません")
            parent_namespace = Namespace(parent)
            if not parent_namespace.exists():
                raise RuntimeError(f"名前空間が存在しません: {parent_namespace.name}")
            leaf_name = self._name.rsplit(":", 1)[-1]
            target = Namespace(f"{parent_namespace.name}:{leaf_name}")
            self._move_contents(target)
            self._name = target.name

    def getShortName(self):
        """末端の名前(``:a:b`` なら ``b``)を返す。

        Returns:
            str: 区切りの ``:`` を含まない最後の階層名。ルートでは ``":"``。
        """
        if self._name == ":":
            return ":"
        return self._name.rsplit(":", 1)[-1]

    def split(self):
        """階層ごとの名前のリスト(``:a:b`` なら ``["a", "b"]``)を返す。

        Returns:
            list[str]: 上の階層から順に並べた名前。ルートでは空リスト。
        """
        if self._name == ":":
            return []
        return self._name[1:].split(":")

    def getChildren(self, *, allDescendents=False):
        """子の名前空間を取得する。

        Args:
            allDescendents (bool): Trueなら、孫より下の子孫も含める(親が子より先に並ぶ)。既定は直下だけ。
                :meth:`DagNode.getChildren <mlib.nodes.dagNode.DagNode.getChildren>` の同じ名前の引数と同じ意味。

        Returns:
            list[Namespace]: 子(allDescendents=Trueなら子孫)。自身が存在しない場合は空リスト。

        Raises:
            TypeError: allDescendents が bool でない場合。
        """
        _require_bool(allDescendents, "allDescendents")
        if not self.exists():
            return []
        names = om2.MNamespace.getNamespaces(self._name, allDescendents) or []
        children = []
        prefix = self._name if self._name.endswith(":") else self._name + ":"
        for name in names:
            absolute_name = name if name.startswith(":") else prefix + name
            child = Namespace(absolute_name)
            if allDescendents or child.getParent() == self:
                children.append(child)
        return children

    def getNodes(self, *, allDescendents=False, type=None):
        """名前空間の中のノードを、mlibのオブジェクトとして返す。

        Args:
            allDescendents (bool): Trueなら、子孫の名前空間の中のノードも含める。既定はFalse。
            type (str | None): 絞り込むノード型。その型から派生した型も含む。Noneならすべての型
                (:meth:`Selection.getNodes <mlib.common.selection.Selection.getNodes>` と同じ)。

        Returns:
            Nodes: 名前空間の中のノードのオブジェクト。自身が存在しない場合は空の集まり。

        Raises:
            TypeError: allDescendentsがboolでない場合、またはtypeが文字列でもNoneでもない場合。
        """
        _require_bool(allDescendents, "allDescendents")
        if type is not None and not isinstance(type, str):
            raise TypeError("typeはstrかNoneで指定してください")
        # nodes.nodeもcommon.namespaceを参照するため、
        # 循環回避のためここで遅延 import する(mlib で意図的な相互依存の一つ)。
        from ..nodes.node import Node, Nodes

        if not self.exists():
            return Nodes._wrap([])

        mobjects = om2.MNamespace.getNamespaceObjects(self._name, allDescendents) or []
        # Node(mobject)と同じ解決(DAGは最初のパス)・型選択を、生成の入口の再判定なしで行う。
        nodes = [Node._from_name(mobject) for mobject in mobjects]
        if type is not None:
            nodes = [node for node in nodes if node.isType(type)]
        return Nodes._wrap(nodes)

    def getNode(self, name):
        """名前空間を付けた名前で、ノードを取得する。

        例えば ``Namespace(":char").getNode("root")`` は ``char:root`` を取得する。

        Args:
            name (str): 名前空間を除いたノード名。DAGパスでは階層ごとに名前空間が要るため、
                ``"grp|char:child"`` のように、2階層目からは名前空間を付けて渡す。

        Returns:
            Node: 実際のノード型に合ったオブジェクト。

        Raises:
            TypeError: name が文字列でない場合。
            ValueError: name が空文字列の場合。
            RuntimeError: ノードが存在しない場合、または1つに決まらない場合。
        """
        if not isinstance(name, str):
            raise TypeError("nameはstrで指定してください")
        if not name:
            raise ValueError("nameは空でない文字列で指定してください")
        # nodes.nodeもcommon.namespaceを参照するため、循環回避のためここで遅延 import する。
        from ..nodes.node import Node

        full_name = self._name.rstrip(":") + ":" + name
        return Node._from_name(full_name)

    def setCurrent(self):
        """カレントの名前空間を、この名前空間に切り替える。

        cmdsを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 自身が存在しない場合。
        """
        with undoChunk("mlibNamespaceSetCurrent"):
            if not self.exists():
                raise RuntimeError(f"名前空間が存在しません: {self._name}")
            cmds.namespace(set=self._name)

    @contextmanager
    def asCurrent(self):
        """カレントの名前空間を、一時的にこの名前空間に切り替える。

        抜けるときは、例外が起きても起きなくても、元に戻そうとする。
        元の名前空間が削除されていれば戻さない。
        戻すときに失敗するとその例外を送出し、ブロックの中で起きた例外と置き換わることがある。

        Yields:
            Namespace: 自身。

        Raises:
            RuntimeError: 自身が存在しない場合、またはMayaが切り替えや戻しを拒否した場合。
        """
        previous = Namespace.getCurrent()
        self.setCurrent()
        try:
            yield self
        finally:
            if previous.exists():
                previous.setCurrent()

    def rename(self, name):
        """この名前空間の名前を変える。

        cmdsを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Args:
            name (str | Namespace): 新しい名前。最後の階層の名前だけを使い、今の親はそのままにする。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: nameが文字列でもNamespaceでもない場合。
            ValueError: ルートの名前を変えようとした場合、または名前が正しくない場合(空・使えない文字・空の階層)。
            RuntimeError: 移動先がすでにある場合、親が存在しない場合、または Maya の操作が失敗した場合。
        """
        _require_name(name, "name")
        with undoChunk("mlibNamespaceRename"):
            if self._name == ":":
                raise ValueError("ルートの名前空間は名前を変更できません")
            target = Namespace(name)
            parent = self.getParent()
            # ルートは先頭で拒否しているため、親は必ずある。
            assert parent is not None
            target = Namespace(f"{parent.name}:{target.name.rsplit(':', 1)[-1]}")
            self._move_contents(target)
            self._name = target.name

    def deleteNodes(self, *, preserveChildren=True):
        """名前空間を残して、直接所属するノードを削除する。

        既定では別の名前空間の子Transformをワールド直下へ退避する。子の名前空間は削除しない。
        Shapeだけの退避とインスタンスの退避は対応しない。ロックの自動解除はしない。
        cmdsを1つのUndoチャンクに記録する。途中でMayaが拒否した場合は変更が残る場合がある。
        fast引数は持たない(親子付けと削除をMayaコマンドで行うため)。

        Args:
            preserveChildren (bool): Trueなら別の名前空間の子を退避する。FalseならDAGの子孫も削除する。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: preserveChildrenがbool以外の場合。
            ValueError: ルート・UI・shared名前空間の場合。
            RuntimeError: 名前空間がない、または対象や子孫に削除不可・参照・ロックがある場合。
            NotImplementedError: 退避対象がShapeまたはインスタンスの場合。
        """
        _require_bool(preserveChildren, "preserveChildren")
        if self._name in (":", ":UI", ":shared"):
            raise ValueError("既定の名前空間の内容は削除できません")
        if not self.exists():
            raise RuntimeError(f"名前空間が存在しません: {self._name}")
        nodes = self.getNodes()
        check_deletion(nodes)
        preserved = []
        if preserveChildren:
            for node in nodes:
                if not node.mnode().hasFn(om2.MFn.kDagNode):
                    continue
                for child in node.getChildren(shapes=True, intermediates=True, underWorld=True):
                    if child.getNamespace() == self:
                        continue
                    if not child.mnode().hasFn(om2.MFn.kTransform) or child.isInstanced():
                        raise NotImplementedError("別の名前空間のShapeやインスタンスの退避には対応していません")
                    preserved.append(child)
        with undoChunk("mlibNamespaceDeleteNodes"):
            for child in preserved:
                child.setParent(None)
            nodes.delete()

    def delete(self, destination=":", *, deleteContents=False):
        """中身を別の名前空間へ移してから、この名前空間を削除する。

        ``deleteContents=True`` なら、中身ごと削除する。

        - 移すときに名前が重なるノードは、Mayaの規則(cmdsのforceでの移動)で末尾に番号を付けて名前を変える。
        - ``deleteContents=True`` は ``cmds.namespace(removeNamespace=..., deleteNamespaceContent=True)`` と同じ。
          名前空間の中のノードと子の名前空間を削除する(読み込んだアセットの後片付けに使う)。
          名前空間の外にある子孫も、親のDAGノードと一緒に削除される。

        cmdsを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Args:
            destination (str | Namespace): 中身を移す先の、既存の名前空間。既定はルート。
                deleteContents=True では使わない。
            deleteContents (bool): True なら、中身を移さずに削除する。既定は False。

        Returns:
            Namespace | None: 中身を受け取った移動先。deleteContents=True では ``None``。
                自身が持っている名前は、削除する前のまま。

        Raises:
            TypeError: deleteContents が bool でない場合。
            ValueError: ルートを削除しようとした場合、または destination が正しくない場合。
            RuntimeError: 自身か移動先が存在しない場合、または Maya の操作が失敗した場合。
        """
        _require_bool(deleteContents, "deleteContents")
        with undoChunk("mlibNamespaceDelete"):
            if self._name == ":":
                raise ValueError("ルートの名前空間は削除できません")
            if deleteContents:
                if not self.exists():
                    raise RuntimeError(f"名前空間が存在しません: {self._name}")
                cmds.namespace(removeNamespace=self._name, deleteNamespaceContent=True)
                return None
            destination_namespace = Namespace(destination)
            if not destination_namespace.exists():
                raise RuntimeError(f"名前空間が存在しません: {destination_namespace.name}")
            cmds.namespace(moveNamespace=(self._name, destination_namespace.name), force=True)
            cmds.namespace(removeNamespace=self._name)
            return destination_namespace

    @classmethod
    def _create(cls, name, parent):
        """createの中身の処理。Undoチャンクは呼び出す側が管理する。

        Args:
            name (str | Namespace): createのname。
            parent (str | Namespace): createのparent。

        Returns:
            Namespace: 作った名前空間の完全名を持つオブジェクト。
        """
        namespace = cls(name)
        parent_namespace = cls(parent)
        raw_name = name.name if isinstance(name, Namespace) else name.replace("/", ":")
        if namespace.name != ":" and not raw_name.startswith(":"):
            raw_parent = parent.name if isinstance(parent, Namespace) else parent.replace("/", ":")
            if not raw_parent.startswith(":"):
                parent_namespace = cls(cls.getCurrent().name.rstrip(":") + parent_namespace.name)
            namespace = cls(parent_namespace.name.rstrip(":") + namespace.name)
        parent_namespace = namespace.getParent()
        if namespace.exists():
            return namespace
        if parent_namespace is None:
            raise ValueError("ルートの名前空間は作成できません")
        if not parent_namespace.exists():
            cls._create(parent_namespace, ":")
        leaf_name = namespace.name.rsplit(":", 1)[-1]
        created_name = cmds.namespace(add=leaf_name, parent=parent_namespace.name)
        if not created_name.startswith(":") and om2.MNamespace.relativeNames():
            created_name = cls.getCurrent().name.rstrip(":") + ":" + created_name
        return cls(created_name)

    @staticmethod
    def _normalize(name):
        """名前空間の名前を、Mayaの絶対表記に揃える。

        Args:
            name (str): 揃える名前。

        Returns:
            str: / を : に置き換え、両端の : を除いてから、先頭に : を付けた名前。区切り文字だけなら :。
        """
        name = name.replace("/", ":")
        if name == ":" or not name.strip(":"):
            return ":"
        name = name.strip(":")
        return ":" + name

    def _move_contents(self, target):
        """名前空間の中身を別の名前空間へ移し、元の名前空間を削除する。

        移動先を作り、force=True で中身を移してから、元を削除する。
        自身が持っている名前は、ここでは新しくしない。

        Args:
            target (Namespace): 新しく作る移動先。親はすでに存在している必要がある。
                Undoチャンクは呼び出す側が管理する。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 移動先がすでにある場合、親が存在しない場合、または Maya の操作が失敗した場合。
        """
        if target.exists():
            raise RuntimeError(f"名前空間はすでに存在します: {target.name}")
        target_parent = target.getParent()
        if target_parent is None or not target_parent.exists():
            raise RuntimeError(f"名前空間が存在しません: {target_parent}")
        leaf_name = target.name.rsplit(":", 1)[-1]
        cmds.namespace(add=leaf_name, parent=target_parent.name)
        cmds.namespace(moveNamespace=(self._name, target.name), force=True)
        cmds.namespace(removeNamespace=self._name)


def _require_name(value, name):
    """名前空間の名前の引数を確かめる。

    / は : と同じ区切りとして扱い、先頭・末尾の : は絶対名・区切りとして受け付ける。

    Args:
        value (str | Namespace): 確かめる値。
        name (str): 例外メッセージに使う引数名。

    Raises:
        TypeError: 文字列でもNamespaceでもない場合。
        ValueError: 空、使えない文字を含む、または空の階層を含む場合。
    """
    if isinstance(value, Namespace):
        return
    if not isinstance(value, str):
        raise TypeError(f"{name}はstrかNamespaceで指定してください: {type(value).__name__}")
    text = value.replace("/", ":")
    if text == ":":
        return
    body = text[1:] if text.startswith(":") else text
    body = body[:-1] if body.endswith(":") else body
    for segment in body.split(":"):
        if not _LEGAL_SEGMENT.match(segment):
            raise ValueError(f"{name}は英数字と_の名前空間の名前で指定してください(先頭は数字以外。空の階層は不可): {value!r}")
