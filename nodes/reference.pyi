# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の reference ノードを扱う。"""

import os
import re
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.fastWrite import require_writable
from ..decorator import _require_bool, undoChunk
from ..util import _require_choice
from .node import Node, Nodes
from mlib.common.namespace import Namespace

_EDIT_KINDS: dict


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
    def isReferenceLocked(self) -> bool:
        """参照ファイルの編集ロック状態を取得する。

        referenceノード自身のロックとは異なる。

        Returns:
            bool: ファイル参照がロックされているか。
        """
        ...
    def setReferenceLocked(self, state: bool = ...) -> None:
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
        ...
    def cleanEdits(self, *, editCommand: str | None = ...) -> None:
        """アンロード済みリファレンスの編集履歴を削除する。

        Undo対象外。ロード中は拒否し、自動アンロードはしない。削除した編集は再ロード時に
        適用されず、このシーンを保存すると削除後の履歴が保存される。参照元ファイルは変更しない。
        fast引数は持たない(ファイル参照の履歴操作のため)。

        Args:
            editCommand (str | None): 削除するMaya編集コマンド。Noneなら全種類。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: editCommandが文字列・None以外の場合。
            ValueError: editCommandが対応する編集コマンドでない場合。
            RuntimeError: ロード中・ロック中、またはMayaが削除を拒否した場合。
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
    def setLoaded(self, state: bool = ...) -> None:
        """リファレンスをロードする。``state=False`` なら、アンロードする。

        :meth:`isLoaded` と対になる。

        Args:
            state (bool): Trueならロード、Falseならアンロードする。既定はTrue。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがboolでない場合。
            RuntimeError: Mayaがロード・アンロードを拒否した場合。
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
    def getParentReference(self, *, root: bool = ...) -> Reference | None:
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
        ...
    def getChildren(self) -> Nodes[Reference]:
        """子のリファレンスを取得する。

        自身を親に持つ、1段下の入れ子のリファレンスだけを返す。

        Returns:
            Nodes[Reference]: 子のリファレンス。無ければ空の集まり。孫より下は含めない。
        """
        ...
    def isTopLevel(self) -> bool:
        """トップレベルのリファレンス(親を持たないもの)かを判定する。

        Returns:
            bool: 親のリファレンスが無ければTrue。
        """
        ...
    def getEdits(self, successful: bool = ..., failed: bool = ..., *, what: str = ..., editCommand: str | None = ..., onReferenceNode: Reference | str | None = ...) -> list[str]:
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
                Noneなら種類を絞らない。
            onReferenceNode (Reference | str | None): Editの保存元referenceノード。Noneなら保存元を絞らない。

        Returns:
            list[str]: Editの文字列・ノード名・アトリビュート名。無ければ空リスト。

        Raises:
            TypeError: what・editCommandの型、またはonReferenceNodeのノード型が不正な場合。
            ValueError: what・editCommandが未対応の名前の場合。
            RuntimeError: 指定ノードが無効か、Mayaが照会を拒否した場合。
        """
        ...
    def removeEdits(self, successful: bool = ..., failed: bool = ..., *, editCommand: str | None = ...) -> None:
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
        ...
    def importContents(self, removeNamespace: bool = ...) -> Nodes:
        """リファレンスの内容をシーンへ読み込み、リファレンスを解除する。

        ``cmds.file(importReference=True)`` で読み込む。呼び出した後、このreferenceノードはシーンから無くなる。
        入れ子になった子のリファレンスは、リファレンスのまま残る。
        ファイルの操作なので、Undoには記録されない。

        Args:
            removeNamespace (bool): Trueなら、読み込んだ名前空間を削除し、内容を親の名前空間へ移す。
                名前がぶつかるノードには、:meth:`Namespace.delete` と同じく末尾に番号を付ける。既定はFalse。

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
