"""Maya の名前空間を取得・作成・移動・削除する。"""

from contextlib import contextmanager

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..decorator import _require_bool, undoChunk


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
            int: 今持っている名前のハッシュ。rename/move で変わるため、集合や辞書のキーに入れている間は
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
            ValueError: nameまたはparentが正しくない場合。
            RuntimeError: Mayaが作成を拒否した場合。

        Note:
            使えない文字(``-``・空白・先頭の数字・``#`` など)は、Mayaの規則で置き換える。
            置き換えた名前がすでにあれば、末尾に番号を付ける。戻り値はMayaが実際に作った名前になる。
        """
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

    def getParent(self):
        """親の名前空間を返す。ルートの親は ``None``。

        Returns:
            Namespace | None: 名前から求めた親。ルートでは None。親が存在するかは確かめない。
        """
        if self._name == ":":
            return None
        parent_name = self._name.rsplit(":", 1)[0] or ":"
        return Namespace(parent_name)

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

    def getChildren(self, recurse=False):
        """子の名前空間を取得する。

        Args:
            recurse (bool): Trueなら、孫より下の子孫も含める(親が子より先に並ぶ)。既定は直下だけ。

        Returns:
            list[Namespace]: 子(recurse=Trueなら子孫)。自身が存在しない場合は空リスト。

        Raises:
            TypeError: recurse が bool でない場合。
        """
        _require_bool(recurse, "recurse")
        if not self.exists():
            return []
        names = om2.MNamespace.getNamespaces(self._name, recurse) or []
        children = []
        prefix = self._name if self._name.endswith(":") else self._name + ":"
        for name in names:
            absolute_name = name if name.startswith(":") else prefix + name
            child = Namespace(absolute_name)
            if recurse or child.getParent() == self:
                children.append(child)
        return children

    def getNodes(self, recurse=False):
        """名前空間の中のノードを、mlibのオブジェクトとして返す。

        Args:
            recurse (bool): Trueなら、子の名前空間の中のノードも含める。

        Returns:
            list[Node]: 名前空間の中のノードのオブジェクト。自身が存在しない場合は空リスト。
        """
        if not self.exists():
            return []
        # nodes.nodeもcommon.namespaceを参照するため、
        # 循環回避のためここで遅延 import する(mlib で意図的な相互依存の一つ)。
        from ..nodes.node import Node

        mobjects = om2.MNamespace.getNamespaceObjects(self._name, recurse) or []
        # Node(mobject)と同じ解決(DAGは最初のパス)・型選択を、生成の入口の再判定なしで行う。
        return [Node._from_name(mobject) for mobject in mobjects]

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
            Namespace: 自身。

        Raises:
            RuntimeError: 自身が存在しない場合。
        """
        with undoChunk("mlibNamespaceSetCurrent"):
            if not self.exists():
                raise RuntimeError(f"名前空間が存在しません: {self._name}")
            cmds.namespace(set=self._name)
            return self

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
            Namespace: 持っている名前を新しくした自身。

        Raises:
            ValueError: ルートの名前を変えようとした場合、または名前が正しくない場合。
            RuntimeError: 移動先がすでにある場合、親が存在しない場合、または Maya の操作が失敗した場合。
        """
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
            return self

    def move(self, parent=":"):
        """この名前空間を、指定した親の名前空間の下へ移す。

        cmdsを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Args:
            parent (str | Namespace): 移動先の、既存の親の名前空間。自身の最後の階層の名前はそのままにする。

        Returns:
            Namespace: 持っている名前を新しくした自身。

        Raises:
            ValueError: ルートを移動しようとした場合、または parent が正しくない場合。
            RuntimeError: 親が存在しない場合、移動先がすでにある場合、または Maya の操作が失敗した場合。
        """
        with undoChunk("mlibNamespaceMove"):
            if self._name == ":":
                raise ValueError("ルートの名前空間は移動できません")
            parent_namespace = Namespace(parent)
            if not parent_namespace.exists():
                raise RuntimeError(f"名前空間が存在しません: {parent_namespace.name}")
            leaf_name = self._name.rsplit(":", 1)[-1]
            target = Namespace(f"{parent_namespace.name}:{leaf_name}")
            self._move_contents(target)
            self._name = target.name
            return self

    def remove(self, destination=":", *, deleteContents=False):
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
        with undoChunk("mlibNamespaceRemove"):
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
