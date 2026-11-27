"""Maya の reference ノードを扱う。"""

import os
import re

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.fastWrite import require_writable
from ..decorator import _require_bool, undoChunk
from ..util import _require_choice
from .node import Node, Nodes

#: :meth:`Reference.getEdits` の kind と ``cmds.referenceQuery`` のフラグ。
_EDIT_KINDS = {"string": "editStrings", "node": "editNodes", "attr": "editAttrs"}


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

    def isReferenceLocked(self):
        """参照ファイルの編集ロック状態を取得する。

        referenceノード自身のロックとは異なる。

        Returns:
            bool: ファイル参照がロックされているか。
        """
        return cmds.file(self.getFilename(withCopyNumber=True), query=True, lockReference=True)

    def setReferenceLocked(self, state=True):
        """参照ファイルを編集ロック・解除する。

        Undo対象外。ロード中は一度アンロードして再ロードするため、保持済みの参照先オブジェクトは無効になる。
        アンロード中は設定だけを変更し、次のロード時に反映する。参照元ファイルは書き換えない。
        再ロード失敗時はアンロード状態で設定が残る。解除はFalseを指定する。
        fast引数は持たない(ファイル参照の状態操作のため)。

        Args:
            state (bool): Trueでロック、Falseで解除する。既定はTrue。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがboolでない場合。
            RuntimeError: 無効なリファレンス、またはMayaが変更を拒否した場合。
            NotImplementedError: 入れ子のリファレンスの場合。
        """
        _require_bool(state, "state")
        if self.isFromReferencedFile():
            raise NotImplementedError("入れ子のリファレンスの編集ロックには対応していません")
        plug = self.getPlug("locked").mplug()
        require_writable(plug)
        if plug.asBool() == state:
            return
        loaded = self.isLoaded()
        name = self.getName()
        if loaded:
            cmds.file(unloadReference=name)
        try:
            # 読み込み時にしか反映されない設定。部分的なUndo項目を残さず直接変更する。
            self.getPlug("locked").mplug().setBool(state)
        finally:
            if loaded:
                cmds.file(loadReference=name, loadReferenceDepth="asPrefs", prompt=False)

    def cleanEdits(self, *, editCommand=None):
        """アンロード済みリファレンスの編集履歴を削除する。

        Undo対象外。ロード中は拒否し、自動アンロードはしない。削除した編集は再ロード時に
        適用されず、このシーンを保存すると削除後の履歴が保存される。参照元ファイルは変更しない。
        fast引数は持たない(ファイル参照の履歴操作のため)。

        Args:
            editCommand (str | None): 削除するMaya編集コマンド。Noneなら全種類。既定はNone。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: editCommandが文字列・None以外の場合。
            ValueError: editCommandが対応する編集コマンドでない場合。
            RuntimeError: ロード中・ロック中、またはMayaが削除を拒否した場合。
        """
        if editCommand is not None and not isinstance(editCommand, str):
            raise TypeError("editCommandは文字列またはNoneで指定してください")
        if editCommand is not None and editCommand not in ("setAttr", "addAttr", "deleteAttr", "connectAttr", "disconnectAttr", "parent"):
            raise ValueError("editCommandが対応する編集コマンドではありません")
        if self.isLoaded() or self.isReferenceLocked():
            raise RuntimeError("編集履歴の削除にはアンロード済みでロックされていないリファレンスが必要です")
        if editCommand is None:
            cmds.file(cleanReference=self.getName())
        else:
            cmds.file(cleanReference=self.getName(), editCommand=editCommand)

    def getFilename(self, *, resolved=True, withCopyNumber=False):
        """リファレンスしているファイルのパスを取得する。

        Args:
            resolved (bool): Trueなら、パスの変数などを展開した実際のパスを返す。
                Falseなら、シーンに保存されている展開前のパスを返す。既定はTrue。
            withCopyNumber (bool): Trueなら、同じファイルを複数回リファレンスしたときに付く
                コピー番号(``{1}`` など)をパスの末尾に含める。最初のリファレンスには番号が付かない。
                Trueのときは ``cmds.referenceQuery(ref, filename=True)`` と同じ値になる。既定はFalse。

        Returns:
            str: リファレンスしているファイルのパス。常にフォルダーを含む。

        Raises:
            TypeError: resolved・withCopyNumberがboolでない場合。
        """
        _require_bool(resolved, "resolved")
        _require_bool(withCopyNumber, "withCopyNumber")
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

    def setLoaded(self, state=True):
        """リファレンスをロードする。``state=False`` なら、アンロードする。

        :meth:`isLoaded` と対になる。ファイルの操作なので、Undoには記録されない。

        Args:
            state (bool): Trueならロード、Falseならアンロードする。既定はTrue。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがboolでない場合。
            RuntimeError: Mayaがロード・アンロードを拒否した場合。
        """
        _require_bool(state, "state")
        if state:
            with undoChunk("mlibReferenceLoad"):
                # GUIでも確認ダイアログで止めず、読み込めないときは例外にする。
                cmds.file(loadReference=self.getName(), prompt=False)
            return
        with undoChunk("mlibReferenceUnload"):
            cmds.file(unloadReference=self.getName())

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

    def getParentReference(self, *, root=False):
        """親のリファレンスを取得する。``root=True`` なら、入れ子のいちばん上(トップレベル)のリファレンスを取得する。

        リファレンスしたファイルの中に、さらにリファレンスがある(入れ子になっている)場合に使う。

        Args:
            root (bool): Trueなら、親をいちばん上までたどる。既定はFalse(1つ上の親)。

        Returns:
            Reference | None: 親のリファレンス。トップレベルのリファレンスではNone。
                ファイルを持たないreferenceノード(createNodeで作ったものなど)もNoneになる。
                このノードではMFnReference.parentReferenceが失敗するため。
                ``root=True`` では必ずReferenceを返し、自身がトップレベルなら自身を返す(Noneにならない)。

        Raises:
            TypeError: rootがboolでない場合。
        """
        _require_bool(root, "root")
        if root:
            reference = self
            parent = reference.getParentReference()
            while parent is not None:
                reference = parent
                parent = reference.getParentReference()
            return reference
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

        own_name = self._full_name()
        children = []
        for reference in listReferences():
            parent = reference.getParentReference()
            if parent is not None and parent._full_name() == own_name:
                children.append(reference)
        return Nodes._wrap(children)

    def isTopLevel(self):
        """トップレベルのリファレンス(親を持たないもの)かを判定する。

        Returns:
            bool: 親のリファレンスが無ければTrue。
        """
        return self.getParentReference() is None

    def getEdits(self, *, successful=True, failed=False, what="string", editCommand=None, onReferenceNode=None):
        """このリファレンスに対するEditの一覧を取得する。

        ``what`` で、Editの何を返すかを選ぶ。

        - ``"string"`` (既定): Editを表すMELコマンドの文字列。過去の名前を含む場合がある。
        - ``"node"``: Editに記録されたノード名。過去の名前や重複を含み、現在のDAGパスとは限らない。
        - ``"attr"``: Editで変更されたアトリビュートの短縮名。Mayaの ``referenceQuery -editAttrs`` は、ノード名を含まない
          アトリビュート名だけを返す。コンパウンドアトリビュートの子を編集した場合は、親の短縮名になる。同じ名前が重なることがある。
          どのノードのアトリビュートかは、``"node"``・``"string"`` と合わせて調べる。

        Args:
            successful (bool): Trueなら、適用に成功したEditを含める。既定はTrue。
            failed (bool): Trueなら、適用に失敗したEditを含める。既定はFalse。
            what (str): 返すもの。``"string"``・``"node"``・``"attr"``。既定は ``"string"``。
            editCommand (str | None): addAttr・connectAttr・deleteAttr・disconnectAttr・parent・setAttr・lock・unlockの1種類。
                Noneなら種類を絞らない。既定はNone。
            onReferenceNode (Reference | str | None): Editの保存元referenceノード。Noneなら保存元を絞らない。既定はNone。

        Returns:
            list[str]: Editの文字列・ノード名・アトリビュート名。無ければ空リスト。

        Raises:
            TypeError: successful・failedがboolでない場合、what・editCommandの型、またはonReferenceNodeのノード型が不正な場合。
            ValueError: what・editCommandが未対応の名前の場合。
            RuntimeError: 指定ノードが無効か、Mayaが照会を拒否した場合。
        """
        _require_bool(successful, "successful")
        _require_bool(failed, "failed")
        what = _require_choice(what, "what", tuple(_EDIT_KINDS))
        flags = self._edit_query_filters(editCommand, onReferenceNode)
        flags[_EDIT_KINDS[what]] = True
        return cmds.referenceQuery(self.getName(), successfulEdits=successful, failedEdits=failed, **flags) or []

    @undoChunk("mlibReferenceRemoveEdits")
    def removeEdits(self, *, successful=True, failed=True, editCommand=None):
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
        ファイルがあるかは置き換える前に確かめ、無ければ何も変えずにOSErrorにする(相対パスはMayaのプロジェクトから探す。
        :func:`~mlib.common.references.createReference` と同じ)。Mayaは無いファイルでも参照先を書き換えてしまうため。

        Args:
            path (str | os.PathLike): 新しいファイルのパス。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: pathが文字列でもPathLikeでもない場合。
            ValueError: pathが空の場合。
            OSError: ファイルが無い場合(``FileNotFoundError``)。
            RuntimeError: referenceノードが無効な場合、またはMayaが読み込みを拒否した場合。
        """
        if not isinstance(path, (str, os.PathLike)):
            raise TypeError("pathはstrかos.PathLikeで指定してください")
        path = os.fspath(path)
        if not path:
            raise ValueError("pathは空でない文字列で指定してください")
        self._require_valid("ファイルの置き換え")
        # 循環参照の回避: common.references は使う時点で nodes を読み込むため、こちらも使う時点で読み込む。
        from ..common.references import _require_scene_file

        _require_scene_file(path)
        # GUIでも「ファイルが見つかりません」の確認ダイアログで止めず、例外にする。
        cmds.file(path.replace("\\", "/"), loadReference=self.getName(), prompt=False)

    def importContents(self, *, removeNamespace=False):
        """リファレンスの内容をシーンへ読み込み、リファレンスを解除する。

        ``cmds.file(importReference=True)`` で読み込む。呼び出した後、このreferenceノードはシーンから無くなる。
        入れ子になった子のリファレンスは、リファレンスのまま残る。
        ファイルの操作なので、Undoには記録されない(removeNamespace=Trueの名前空間の削除も記録しない)。

        Args:
            removeNamespace (bool): Trueなら、読み込んだ名前空間を削除し、内容を親の名前空間へ移す。
                名前がぶつかるノードには、:meth:`Namespace.delete` と同じく末尾に番号を付ける。既定はFalse。

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
            # 読み込みはUndoに記録されないため、名前空間の削除だけがUndoで戻ると、シーンが読み込みの途中の形になる。
            # 読み込みと同じく記録しない(キューは消さない)。
            state = cmds.undoInfo(query=True, state=True)
            cmds.undoInfo(stateWithoutFlush=False)
            try:
                namespace.delete(namespace.getParent())
            finally:
                cmds.undoInfo(stateWithoutFlush=state)
        return Nodes._wrap([node for node in nodes if node.isValid()])

    @undoChunk("mlibReferenceRemoveReference")
    def removeReference(self):
        """リファレンスを削除する(``cmds.file(removeReference=True)`` 相当)。

        referenceノードと、リファレンスで読み込んだ内容をシーンから取り除く。
        呼び出した後、このオブジェクトが指していたノードはシーンから無くなる。
        :meth:`~mlib.nodes.node.Node.delete` (referenceノードだけを消す基底の操作)とは別の操作。

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
