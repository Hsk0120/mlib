"""Maya の reference ノードを扱う。"""

import os
import re

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..decorator import _require_bool, undoChunk
from .node import Node, Nodes


class Reference(Node):
    """Mayaのreferenceノードを扱うクラス。

    リファレンスしているファイルの情報を調べたり、ロード・アンロードを切り替えたりする。
    """

    def mfn(self):
        """このreferenceノードのfunction setを取得する。

        referenceノードに使えるもののうち、最も具体的な ``om2.MFnReference`` を返す。
        呼び出すたびに新しく作る。

        Returns:
            om2.MFnReference: この reference ノードの function set。
        """
        return om2.MFnReference(self.mnode())

    def getFilename(self, resolved=True, withCopyNumber=False):
        """リファレンスしているファイルのパスを取得する。

        Args:
            resolved (bool): Trueなら、パスの変数などを展開した実際のパスを返す。
                Falseなら、シーンに保存されている展開前のパスを返す。既定はTrue。
            withCopyNumber (bool): Trueなら、同じファイルを複数回リファレンスしたときに付く
                コピー番号(``{1}`` など)をパスの末尾に含める。最初のリファレンスには番号が付かない。
                Trueのときは ``cmds.referenceQuery(ref, filename=True)`` と同じ値になる。既定はFalse。

        Returns:
            str: リファレンスしているファイルのパス。常にフォルダーを含む。
        """
        # MFnReference.fileName の2番目はパスを除く指定(Falseでディレクトリを含む)、
        # 3番目がコピー番号を含める指定。
        return self.mfn().fileName(resolved, False, withCopyNumber)

    def getAssociatedNamespace(self):
        """リファレンスの内容が読み込まれている名前空間を取得する。

        Returns:
            Namespace: リファレンスの名前空間。
        """
        # common.namespaceの初期化順に依存しないよう、
        # mlib 内の他の相互依存箇所と合わせて遅延 import で統一する。
        from ..common import Namespace

        return Namespace(self.mfn().associatedNamespace(False))

    def getCopyNumber(self):
        """同じファイルを複数回リファレンスしたときのコピー番号を取得する。

        :meth:`getFilename` に ``withCopyNumber=True`` を指定したとき、末尾に付く ``{N}`` の番号になる。

        Returns:
            int: コピー番号。番号の付かない最初のリファレンスでは 0。
        """
        match = re.search(r"\{(\d+)\}$", self.getFilename(withCopyNumber=True))
        return int(match.group(1)) if match else 0

    def getCopyNumbers(self):
        """同じファイルを参照しているリファレンスのコピー番号一覧を取得する。

        自身の番号だけを返すgetCopyNumberとは異なる。ロード状態や参照の数は変更しない。

        Returns:
            list[int]: Mayaの列挙順のコピー番号。最初の参照は0。欠番は詰めない。

        Raises:
            RuntimeError: リファレンスが無効、またはMayaが照会を拒否した場合。
        """
        self._require_valid("コピー番号一覧の取得")
        return [int(value) for value in (cmds.file(self.getFilename(), query=True, copyNumberList=True) or [])]

    def isUsingNamespaces(self):
        """リファレンスの内容が名前空間で読み込まれているかを判定する。

        Falseなら、名前の先頭に文字を付ける古い方式で読み込まれている。

        Returns:
            bool: ``cmds.file(..., query=True, usingNamespaces=True)`` の結果。
        """
        return bool(cmds.file(self.getFilename(withCopyNumber=True), query=True, usingNamespaces=True))

    def isDeferred(self):
        """シーンを開いたときにロードしない設定かを判定する。

        ``cmds.file(deferReference=True)`` で設定する、ロードを後回しにする設定を調べる。

        Returns:
            bool: ``cmds.file(..., query=True, deferReference=True)`` の結果。
        """
        return bool(cmds.file(self.getFilename(withCopyNumber=True), query=True, deferReference=True))

    def isLoaded(self):
        """リファレンスが今ロードされているかを判定する。

        Returns:
            bool: ロード済みなら True。
        """
        return self.mfn().isLoaded()

    def getNodes(self):
        """このリファレンスがシーンへ読み込んだノードを取得する。

        Returns:
            Nodes: リファレンスの中のノードのオブジェクト。

        Raises:
            RuntimeError: リファレンスが今アンロードされている場合。
        """
        if not self.isLoaded():
            raise RuntimeError("アンロードされたリファレンスのノードは列挙できません")
        return Nodes._wrap([Node(mobject) for mobject in self.mfn().nodes()])

    def getParentReference(self):
        """親のリファレンスを取得する。

        リファレンスしたファイルの中に、さらにリファレンスがある(入れ子になっている)場合に使う。

        Returns:
            Reference | None: 親のリファレンス。トップレベルのリファレンスではNone。
                ファイルを持たないreferenceノード(createNodeで作ったものなど)もNoneになる。
                このノードではMFnReference.parentReferenceが失敗するため。
        """
        try:
            parent = self.mfn().parentReference()
        except RuntimeError:
            if not self.isValid():
                raise
            return None
        if parent.isNull():
            return None
        return Reference(parent)

    def getChildren(self):
        """子のリファレンスを取得する。

        自身を親に持つ、1段下の入れ子のリファレンスだけを返す。

        Returns:
            Nodes[Reference]: 子のリファレンス。無ければ空の集まり。孫より下は含めない。
        """
        # mlib 内の他の相互依存箇所と合わせて遅延 import で統一する。
        from ..common.references import listReferences

        own_name = self.getFullName()
        children = []
        for reference in listReferences():
            parent = reference.getParentReference()
            if parent is not None and parent.getFullName() == own_name:
                children.append(reference)
        return Nodes._wrap(children)

    def getRoot(self):
        """入れ子のいちばん上(トップレベル)のリファレンスを取得する。

        Returns:
            Reference: トップレベルのリファレンス。自身がトップレベルなら自身。
        """
        reference = self
        parent = reference.getParentReference()
        while parent is not None:
            reference = parent
            parent = reference.getParentReference()
        return reference

    def isTopLevel(self):
        """トップレベルのリファレンス(親を持たないもの)かを判定する。

        Returns:
            bool: 親のリファレンスが無ければTrue。
        """
        return self.getParentReference() is None

    def getEditStrings(self, successful=True, failed=False, *, editCommand=None, onReferenceNode=None):
        """このリファレンスに対するEditの一覧を、MELコマンドの文字列で取得する。

        Args:
            successful (bool): Trueなら、適用に成功したEditを含める。既定はTrue。
            failed (bool): Trueなら、適用に失敗したEditを含める。既定はFalse。
            editCommand (str | None): addAttr・connectAttr・deleteAttr・disconnectAttr・parent・setAttr・lock・unlockの1種類。
                Noneなら種類を絞らない。
            onReferenceNode (Reference | str | None): Editの保存元referenceノード。Noneなら保存元を絞らない。

        Returns:
            list[str]: Editを表すMELコマンド文字列。過去の名前を含む場合がある。無ければ空リスト。

        Raises:
            TypeError: editCommandの型、またはonReferenceNodeのノード型が不正な場合。
            ValueError: editCommandが未対応の名前の場合。
            RuntimeError: 指定ノードが無効か、Mayaが照会を拒否した場合。
        """
        flags = self._edit_query_filters(editCommand, onReferenceNode)
        return cmds.referenceQuery(self.getName(), editStrings=True, successfulEdits=successful, failedEdits=failed, **flags) or []

    def getEditNodeNames(self, successful=True, failed=False, *, editCommand=None, onReferenceNode=None):
        """Editに記録されたノード名の一覧を取得する。

        Args:
            successful (bool): Trueなら、適用に成功したEditを含める。既定はTrue。
            failed (bool): Trueなら、適用に失敗したEditを含める。既定はFalse。
            editCommand (str | None): Editのコマンド名。対応する名前はgetEditStringsを参照。Noneなら全種類。
            onReferenceNode (Reference | str | None): Editの保存元referenceノード。Noneなら保存元を絞らない。

        Returns:
            list[str]: Mayaが返すノード名。過去の名前や重複を含み、現在のDAGパスとは限らない。無ければ空リスト。

        Raises:
            TypeError: editCommandの型、またはonReferenceNodeのノード型が不正な場合。
            ValueError: editCommandが未対応の名前の場合。
            RuntimeError: 指定ノードが無効か、Mayaが照会を拒否した場合。
        """
        flags = self._edit_query_filters(editCommand, onReferenceNode)
        return cmds.referenceQuery(self.getName(), editNodes=True, successfulEdits=successful, failedEdits=failed, **flags) or []

    def getEditAttrNames(self, successful=True, failed=False, *, editCommand=None, onReferenceNode=None):
        """Editで変更されたアトリビュートの短縮名の一覧を取得する。

        Mayaの ``referenceQuery -editAttrs`` は、ノード名を含まないアトリビュート名だけを返す。
        コンパウンドアトリビュートの子を編集した場合は、親の短縮名になる。
        どのノードのアトリビュートかは、``getEditNodeNames()`` や ``getEditStrings()`` と合わせて調べる。

        Args:
            successful (bool): Trueなら、適用に成功したEditを含める。既定はTrue。
            failed (bool): Trueなら、適用に失敗したEditを含める。既定はFalse。
            editCommand (str | None): Editのコマンド名。対応する名前はgetEditStringsを参照。Noneなら全種類。
            onReferenceNode (Reference | str | None): Editの保存元referenceノード。Noneなら保存元を絞らない。

        Returns:
            list[str]: Editの対象になったアトリビュートの短縮名。同じ名前が重なることがある。無ければ空リスト。

        Raises:
            TypeError: editCommandの型、またはonReferenceNodeのノード型が不正な場合。
            ValueError: editCommandが未対応の名前の場合。
            RuntimeError: 指定ノードが無効か、Mayaが照会を拒否した場合。
        """
        flags = self._edit_query_filters(editCommand, onReferenceNode)
        return cmds.referenceQuery(self.getName(), editAttrs=True, successfulEdits=successful, failedEdits=failed, **flags) or []

    @undoChunk("mlibReferenceLoad")
    def load(self):
        """リファレンスをロードする。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: Mayaがロードを拒否した場合。
        """
        # GUIでも確認ダイアログで止めず、読み込めないときは例外にする。
        cmds.file(loadReference=self.getName(), prompt=False)

    @undoChunk("mlibReferenceUnload")
    def unload(self):
        """リファレンスをアンロードする。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: Mayaがアンロードを拒否した場合。
        """
        cmds.file(unloadReference=self.getName())

    @undoChunk("mlibReferenceRemoveEdits")
    def removeEdits(self, successful=True, failed=True, editCommand=None):
        """このリファレンスに対するEditを削除する。

        ``cmds.referenceEdit(removeEdits=True)`` で削除する。
        Mayaは、ロード中のリファレンスでは適用に成功したEditを削除しない。そのため、ロード中に
        ``successful=True`` を指定した場合は、いったんアンロードしてから削除し、もう一度ロードする。
        ファイルの操作なので、Undoには記録されない。

        Args:
            successful (bool): Trueなら、適用に成功したEditを削除する。既定はTrue。
            failed (bool): Trueなら、適用に失敗したEditを削除する。既定はTrue。
            editCommand (str | None): 削除するEditのコマンド名(``"setAttr"``・``"connectAttr"``・``"parent"`` など)。
                Noneならすべてのコマンドが対象。既定はNone。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: successful・failedがboolでない場合、またはeditCommandが文字列でもNoneでもない場合。
            ValueError: editCommandが空文字列の場合。
            RuntimeError: referenceノードが無効な場合、またはMayaが操作を拒否した場合。
        """
        _require_bool(successful, "successful")
        _require_bool(failed, "failed")
        flags = {"removeEdits": True, "successfulEdits": successful, "failedEdits": failed}
        if editCommand is not None:
            if not isinstance(editCommand, str):
                raise TypeError("editCommandはstrかNoneで指定してください")
            if not editCommand:
                raise ValueError("editCommandは空でない文字列で指定してください")
            flags["editCommand"] = editCommand
        self._require_valid("編集の削除")
        name = self.getName()
        reload = successful and self.isLoaded()
        if reload:
            cmds.file(unloadReference=name)
        try:
            cmds.referenceEdit(name, **flags)
        finally:
            if reload:
                cmds.file(loadReference=name, prompt=False)

    @undoChunk("mlibReferenceReplaceFile")
    def replaceFile(self, path):
        """リファレンスするファイルを別のファイルに置き換えて読み込む。

        ``cmds.file(path, loadReference=ref)`` と同じ。名前空間とEditはそのまま残る。
        ファイルの操作なので、Undoには記録されない。

        Args:
            path (str | os.PathLike): 新しいファイルのパス。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: pathが文字列でもPathLikeでもない場合。
            ValueError: pathが空の場合。
            RuntimeError: referenceノードが無効な場合、ファイルが無い場合、またはMayaが読み込みを拒否した場合。
        """
        if not isinstance(path, (str, os.PathLike)):
            raise TypeError("pathはstrかos.PathLikeで指定してください")
        path = os.fspath(path)
        if not path:
            raise ValueError("pathは空でない文字列で指定してください")
        self._require_valid("ファイルの置き換え")
        # GUIでも「ファイルが見つかりません」の確認ダイアログで止めず、例外にする。
        cmds.file(path.replace("\\", "/"), loadReference=self.getName(), prompt=False)

    def importContents(self, removeNamespace=False):
        """リファレンスの内容をシーンへ読み込み、リファレンスを解除する。

        ``cmds.file(importReference=True)`` で読み込む。呼び出した後、このreferenceノードはシーンから無くなる。
        入れ子になった子のリファレンスは、リファレンスのまま残る。
        ファイルの操作なので、Undoには記録されない。

        Args:
            removeNamespace (bool): Trueなら、読み込んだ名前空間を削除し、内容を親の名前空間へ移す。
                名前がぶつかるノードには、:meth:`Namespace.remove` と同じく末尾に番号を付ける。既定はFalse。

        Returns:
            Nodes: 読み込んだノード。referenceノードは含まない。

        Raises:
            TypeError: removeNamespaceがboolでない場合。
            RuntimeError: referenceノードが無効な場合、アンロードされている場合、またはMayaが操作を拒否した場合。
        """
        _require_bool(removeNamespace, "removeNamespace")
        self._require_valid("読み込み")
        if not self.isLoaded():
            raise RuntimeError("アンロードされたリファレンスは読み込めません")
        namespace = self.getAssociatedNamespace() if removeNamespace else None
        nodes = [node for node in self.getNodes() if not node.isType("reference")]
        cmds.file(importReference=True, referenceNode=self.getName())
        if namespace is not None and namespace.name != ":" and namespace.exists():
            namespace.remove(namespace.getParent())
        return Nodes._wrap([node for node in nodes if node.isValid()])

    @undoChunk("mlibReferenceRemove")
    def remove(self):
        """リファレンスを削除する。

        referenceノードと、リファレンスで読み込んだ内容をシーンから取り除く。
        呼び出した後、このオブジェクトが指していたノードはシーンから無くなる。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: Mayaが削除を拒否した場合。
        """
        cmds.file(removeReference=True, referenceNode=self.getName())

    @staticmethod
    def _edit_query_filters(edit_command, on_reference_node):
        """Edit照会の種類と保存元を検証してMayaのフラグを返す。"""
        flags = {}
        if edit_command is not None:
            if not isinstance(edit_command, str):
                raise TypeError("editCommandはstrかNoneで指定してください")
            if edit_command not in ("addAttr", "connectAttr", "deleteAttr", "disconnectAttr", "parent", "setAttr", "lock", "unlock"):
                raise ValueError("editCommandに未対応のコマンド名が指定されています")
            flags["editCommand"] = edit_command
        if on_reference_node is not None:
            reference = on_reference_node if isinstance(on_reference_node, Node) else Node(on_reference_node)
            if not isinstance(reference, Reference):
                raise TypeError("onReferenceNodeはreferenceノードで指定してください")
            flags["onReferenceNode"] = reference.getName()
        return flags
