# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の reference ノードを扱う。"""

import os
import re
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import _require_bool, undoChunk
from .node import Node, Nodes
from mlib.common.namespace import Namespace



class Reference(Node):
    """Mayaのreferenceノードを扱うクラス。

    リファレンスしているファイルの情報を調べたり、ロード・アンロードを切り替えたりする。
    """
    def mfn(self) -> om2.MFnReference:
        """このreferenceノードのfunction setを取得する。

        referenceノードに使えるもののうち、最も具体的な ``om2.MFnReference`` を返す。
        呼び出すたびに新しく作る。

        Returns:
            om2.MFnReference: この reference ノードの function set。
        """
        ...
    def getFilename(self, resolved: bool = ..., withCopyNumber: bool = ...) -> str:
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
        ...
    def getAssociatedNamespace(self) -> Namespace:
        """リファレンスの内容が読み込まれている名前空間を取得する。

        Returns:
            Namespace: リファレンスの名前空間。
        """
        ...
    def getCopyNumber(self) -> int:
        """同じファイルを複数回リファレンスしたときのコピー番号を取得する。

        :meth:`getFilename` に ``withCopyNumber=True`` を指定したとき、末尾に付く ``{N}`` の番号になる。

        Returns:
            int: コピー番号。番号の付かない最初のリファレンスでは 0。
        """
        ...
    def getCopyNumbers(self) -> list[int]:
        """同じファイルを参照しているリファレンスのコピー番号一覧を取得する。

        自身の番号だけを返すgetCopyNumberとは異なる。ロード状態や参照の数は変更しない。

        Returns:
            list[int]: Mayaの列挙順のコピー番号。最初の参照は0。欠番は詰めない。

        Raises:
            RuntimeError: リファレンスが無効、またはMayaが照会を拒否した場合。
        """
        ...
    def isUsingNamespaces(self) -> bool:
        """リファレンスの内容が名前空間で読み込まれているかを判定する。

        Falseなら、名前の先頭に文字を付ける古い方式で読み込まれている。

        Returns:
            bool: ``cmds.file(..., query=True, usingNamespaces=True)`` の結果。
        """
        ...
    def isDeferred(self) -> bool:
        """シーンを開いたときにロードしない設定かを判定する。

        ``cmds.file(deferReference=True)`` で設定する、ロードを後回しにする設定を調べる。

        Returns:
            bool: ``cmds.file(..., query=True, deferReference=True)`` の結果。
        """
        ...
    def isLoaded(self) -> bool:
        """リファレンスが今ロードされているかを判定する。

        Returns:
            bool: ロード済みなら True。
        """
        ...
    def getNodes(self) -> Nodes:
        """このリファレンスがシーンへ読み込んだノードを取得する。

        Returns:
            Nodes: リファレンスの中のノードのオブジェクト。

        Raises:
            RuntimeError: リファレンスが今アンロードされている場合。
        """
        ...
    def getParentReference(self) -> Reference | None:
        """親のリファレンスを取得する。

        リファレンスしたファイルの中に、さらにリファレンスがある(入れ子になっている)場合に使う。

        Returns:
            Reference | None: 親のリファレンス。トップレベルのリファレンスではNone。
                ファイルを持たないreferenceノード(createNodeで作ったものなど)もNoneになる。
                このノードではMFnReference.parentReferenceが失敗するため。
        """
        ...
    def getChildren(self) -> Nodes[Reference]:
        """子のリファレンスを取得する。

        自身を親に持つ、1段下の入れ子のリファレンスだけを返す。

        Returns:
            Nodes[Reference]: 子のリファレンス。無ければ空の集まり。孫より下は含めない。
        """
        ...
    def getRoot(self) -> Reference:
        """入れ子のいちばん上(トップレベル)のリファレンスを取得する。

        Returns:
            Reference: トップレベルのリファレンス。自身がトップレベルなら自身。
        """
        ...
    def isTopLevel(self) -> bool:
        """トップレベルのリファレンス(親を持たないもの)かを判定する。

        Returns:
            bool: 親のリファレンスが無ければTrue。
        """
        ...
    def getEditStrings(self, successful: bool = ..., failed: bool = ..., *, editCommand: str | None = ..., onReferenceNode: Reference | str | None = ...) -> list[str]:
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
        ...
    def getEditNodeNames(self, successful: bool = ..., failed: bool = ..., *, editCommand: str | None = ..., onReferenceNode: Reference | str | None = ...) -> list[str]:
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
        ...
    def getEditAttrNames(self, successful: bool = ..., failed: bool = ..., *, editCommand: str | None = ..., onReferenceNode: Reference | str | None = ...) -> list[str]:
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
        ...
    def load(self) -> None:
        """リファレンスをロードする。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: Mayaがロードを拒否した場合。
        """
        ...
    def unload(self) -> None:
        """リファレンスをアンロードする。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: Mayaがアンロードを拒否した場合。
        """
        ...
    def removeEdits(self, successful: bool = ..., failed: bool = ..., editCommand: str | None = ...) -> None:
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
        ...
    def replaceFile(self, path: str | os.PathLike) -> None:
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
        ...
    def importContents(self, removeNamespace: bool = ...) -> Nodes:
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
        ...
    def remove(self) -> None:
        """リファレンスを削除する。

        referenceノードと、リファレンスで読み込んだ内容をシーンから取り除く。
        呼び出した後、このオブジェクトが指していたノードはシーンから無くなる。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: Mayaが削除を拒否した場合。
        """
        ...
    @staticmethod
    def _edit_query_filters(edit_command, on_reference_node):
        """Edit照会の種類と保存元を検証してMayaのフラグを返す。"""
        ...
