"""ノード・アトリビュート・コンポーネントの取得時点の選択を保持する。"""

from typing import Any, List, Optional, Tuple

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.mel as mel

from ..components.component import Component, Components
from ..components.cv import CV, CVs
from ..components.edge import Edge, Edges
from ..components.face import Face, Faces
from ..components.latticePoint import LatticePoint, LatticePoints
from ..components.surfaceCV import SurfaceCV, SurfaceCVs
from ..components.uv import UV, UVs
from ..components.vertex import Vertex, Vertices
from ..components.vertexFace import VertexFace, VertexFaces
from ..core.object import _exists, _selection_component, _selection_plug
from ..decorator import undoChunk
from ..nodes.node import Node
from ..plugs.plug import Plug
from .environment import Environment
from .keyframe import Keyframe, Keyframes

# まとめて解決するときに1つの選択リストへ続けて追加する名前の数。MSelectionList.add は追加のたびに
# 既存の要素との重複を照合するため、全件を1つのリストへ追加すると件数の2乗に比例して遅くなる。
_NAME_CHUNK = 16

#: repr に表示する保持参照の最大数。
_REPR_LIMIT = 10

#: Channel Boxの表示区分ごとの、選択アトリビュートと表示ノードの照会フラグ。
_CHANNEL_BOX_SECTIONS = (
    ("selectedMainAttributes", "mainObjectList"),
    ("selectedShapeAttributes", "shapeObjectList"),
    ("selectedHistoryAttributes", "historyObjectList"),
    ("selectedOutputAttributes", "outputObjectList"),
)


class Selection:
    """ノード・アトリビュート・コンポーネントの選択を、取得したときの順で持つクラス。

    中身は1つずつのオブジェクト(Node・Plug・Component)で持つ。
    取得した後にMayaの選択が変わっても、中身は変わらない。

    - コンポーネントは1つずつに分けて持つ。完全名が同じものは最初の1つだけを残す。
    - トポロジーやUVセットを変えた後は、同じ要素を指し続けるとは限らない。
    - Mayaの選択へ戻すには :meth:`select` を使う。削除された対象の扱いはmissingで選ぶ。
    - maya.cmdsへ直接渡すとき、コンパウンドアトリビュートとマルチアトリビュートのPlugは文字列にする必要がある。
    """

    def __init__(self, items=()):
        """指定した対象を持つ選択を作る。

        省略した場合は空になる。

        Args:
            items (Iterable[Node | Plug | Component | Components | Selection | str |
                om2.MObject | om2.MDagPath | om2.MPlug | om2.MSelectionList]): 対象。1つだけでも指定できる。
                文字列には範囲の指定(``pCubeShape1.vtx[0:3]`` など)も使える。
                MObject・MDagPathはノード、MPlugはアトリビュートとして扱う。
                MSelectionListとSelectionは、その中の要素を取り出して使う。
                fullNameが同じ対象は、最初の1つだけを持つ。

        Raises:
            TypeError: 対応していない型の場合、またはMesh/NurbsCurve以外のコンポーネントの場合。
            RuntimeError: 名前からノードなどを見つけられない場合。

        Note:
            ノード名だけの文字列(「.」もワイルドカードも含まないもの)は、1つの選択リストへまとめて調べる。
            ただし結果は文字列の順に対応付けるので、並び順と重なりの除き方は、名前を1つずつ調べた場合と同じになる。
        """
        singles = (str, Node, Plug, Component, Components, Selection, om2.MObject, om2.MDagPath, om2.MPlug, om2.MSelectionList)
        if isinstance(items, singles):
            items = [items]
        else:
            items = list(items)
        # ノード名(「.」もワイルドカードも含まない文字列)は、名前ごとに選択リストを作らずまとめて解決する。
        # 対応付けられなかった名前とそれ以外の文字列は、従来どおり名前ごとの選択リストで解決する。
        bulk_names = [item for item in items if isinstance(item, str) and _is_plain_node_name(item)]
        bulk = iter(_resolve_names(bulk_names))
        resolved = []
        for item in items:
            if isinstance(item, Components):
                resolved.extend(item)
            elif isinstance(item, Selection):
                resolved.extend(item._items)
            elif isinstance(item, (Node, Plug, Component)):
                resolved.append(item)
            elif isinstance(item, str):
                found = next(bulk) if _is_plain_node_name(item) else None
                if found is not None:
                    resolved.append(Node._wrap_resolved(found[0], found[1]))
                    continue
                selection = om2.MSelectionList()
                selection.add(item)
                resolved.extend(self._resolve(selection, item))
            elif isinstance(item, om2.MSelectionList):
                resolved.extend(self._resolve(item))
            elif isinstance(item, om2.MPlug):
                resolved.append(Plug._resolve_input(item))
            elif isinstance(item, (om2.MObject, om2.MDagPath)):
                resolved.append(Node(item))
            else:
                raise TypeError("対応していない選択項目です")
        unique = {}
        for item in resolved:
            unique.setdefault(item.getFullName(), item)
        self._items = tuple(unique.values())

    def __len__(self):
        """持っている対象の数を返す。

        fullNameが同じ対象は、作ったときに除いてある(__init__を参照)。

        Returns:
            int: 対象の数。コンポーネントは1つずつ数え、削除された対象も数に含める。
        """
        return len(self._items)

    def __iter__(self):
        """持っている順に対象を返す。

        Returns:
            Iterator: 持っている順に対象を返す。
        """
        return iter(self._items)

    def __getitem__(self, index):
        """番号で対象を取り出す。

        Args:
            index (int | slice): 持っている順の番号、または範囲。負の番号はPythonのtupleと同じ意味になる。

        Returns:
            Node | Plug | Component | tuple: 番号を指定した場合はその対象。sliceを指定した場合は対象のtuple。
        """
        return self._items[index]

    def __repr__(self):
        """デバッグ用に、型名と中身の対象を表す文字列を返す。

        Returns:
            str: ``Selection([Transform('a'), Vertex('boxShape.vtx[5]')])`` のような文字列。
                ``_REPR_LIMIT`` 件より多い場合は先頭だけを表示し、``..., count=N`` を付ける。
                削除された対象は、各型の無効の表示(``<Transform invalid>`` など)になる。
        """
        cls = type(self).__name__
        shown = ", ".join(repr(item) for item in self._items[:_REPR_LIMIT])
        if len(self._items) > _REPR_LIMIT:
            return f"{cls}([{shown}, ...], count={len(self._items)})"
        return f"{cls}([{shown}])"

    @classmethod
    def capture(cls):
        """Mayaで今選んでいるものを取得する。

        Channel Boxで選んでいるアトリビュートは含めない(:meth:`getChannelBoxPlugs` で取得する)。

        Returns:
            Selection: Mayaで今選んでいるもの。Channel Boxで選んでいるアトリビュートは含めない。
        """
        return cls(cls._resolve(om2.MGlobal.getActiveSelectionList()))

    @classmethod
    def getChannelBoxPlugs(cls):
        """メインのChannel Boxで選んでいるアトリビュートを、Plugとして取得する。

        :meth:`capture` はChannel Boxで選んだアトリビュートを含めないので、こちらを使う。
        シーンは変更しない。

        Channel Boxは、オブジェクト・シェイプ・入力・出力の区分に分かれている。区分ごとに、
        選んでいるアトリビュートと、その区分に表示しているノードを ``cmds.channelBox`` で調べる。
        結果はノードごとに、アトリビュートを選んだ順に並べる。

        Returns:
            list[Plug]: 選んでいるアトリビュート。区分の順(オブジェクト→シェイプ→入力→出力)に並び、
                完全名が同じものは最初の1つだけを残す。表示しているノードに無いアトリビュートは除く。
                バッチやmayapyの場合、Channel Boxが無いGUIの場合、何も選んでいない場合は空リスト。
        """
        if Environment.isBatch():
            return []
        try:
            # Channel Boxの名前はMayaのUIが保持するグローバル変数から取得する(既定はmainChannelBox)。
            name = mel.eval("global string $gChannelBoxName; $mlibChannelBoxName = $gChannelBoxName;")
        except RuntimeError:
            name = "mainChannelBox"
        if not name or not cmds.channelBox(name, exists=True):
            return []
        names = []
        for attributes_flag, objects_flag in _CHANNEL_BOX_SECTIONS:
            attributes = cmds.channelBox(name, query=True, **{attributes_flag: True}) or []
            if not attributes:
                continue
            objects = cmds.channelBox(name, query=True, **{objects_flag: True}) or []
            for owner in objects:
                for attribute in attributes:
                    plug_name = f"{owner}.{attribute}"
                    if cmds.objExists(plug_name):
                        names.append(plug_name)
        if not names:
            return []
        return [item for item in cls(names)._items if isinstance(item, Plug)]

    @classmethod
    def getKeyframes(cls):
        """Graph EditorやDope Sheetで選んでいるキーを取得する。

        シーンは変更しない。

        Returns:
            Keyframes: 選んでいるキー。カーブはMayaが返す順、同じカーブの中は番号の小さい順に並ぶ。
                選んでいなければ空。
        """
        keyframes = []
        for name in cmds.keyframe(query=True, selected=True, name=True) or []:
            curve = Node(name)
            for index in cmds.keyframe(name, query=True, selected=True, indexValue=True) or []:
                keyframes.append(Keyframe(curve, int(index)))
        return Keyframes(keyframes)

    @classmethod
    def getSoftSelection(cls):
        """ソフト選択(リッチ選択)の重みを、メッシュごと・頂点ごとに取得する。

        シーンは変更しない。

        - ソフト選択が有効なら、Mayaが計算した減衰を含む重み(0〜1)を返す。
          エッジやフェースを選んでいても、Mayaが頂点の重みに直して返す。
        - ソフト選択が無効なら、選んでいる頂点を重み1で返す。

        同じ頂点が何度も出てきた場合は、大きいほうの重みを使う。

        Returns:
            dict[Mesh, dict[int, float]]: {メッシュ: {頂点番号: 重み}}。メッシュは最初に現れた順。
                頂点の選択が無ければ空の辞書。
        """
        try:
            selection = om2.MGlobal.getRichSelection().getSelection()
        except RuntimeError:
            # 選択が無い等でリッチ選択を作れないときは、通常の選択を使う。
            selection = om2.MGlobal.getActiveSelectionList()
        iterator = om2.MItSelectionList(selection, om2.MFn.kMeshVertComponent)
        result = {}
        while not iterator.isDone():
            path, component = iterator.getComponent()
            if not component.isNull():
                if path.apiType() == om2.MFn.kTransform:
                    path.extendToShape()
                mesh = Node._wrap_dag_path(path)
                weights = result.setdefault(mesh, {})
                indexed = om2.MFnSingleIndexedComponent(component)
                has_weights = indexed.hasWeights
                for element in range(indexed.elementCount):
                    index = indexed.element(element)
                    weight = indexed.weight(element).influence if has_weights else 1.0
                    weights[index] = max(weights.get(index, 0.0), weight)
            iterator.next()
        return {mesh: weights for mesh, weights in result.items() if weights}

    @property
    def items(self):
        """list[Node | Plug | Component]: 持っている順の対象。削除された対象も含む。
        fullNameが同じ対象は、作ったときに除いてある(__init__を参照)。:meth:`getItems` と同じ値。"""
        return list(self._items)

    def getItems(self):
        """持っている対象を、新しいリストで取得する。

        :attr:`items` と同じ値になる。

        Returns:
            list[Node | Plug | Component]: 持っている順の対象。削除された対象も含む。
                このリストを変えても、このオブジェクトの中身は変わらない。
        """
        return list(self._items)

    def getNodes(self, type=None):
        """ノードとして選ばれた対象を取得する。

        Args:
            type (str | None): 絞り込むノード型。その型から派生した型も含む。Noneならすべての型。

        Returns:
            list[Node]: 削除されていないノード。コンポーネントを持つノードは含めない。
        """
        return [item for item in self._items if isinstance(item, Node) and item.isValid() and (type is None or item.isType(type))]

    def getPlugs(self):
        """アトリビュートとして選ばれた対象を取得する。

        Channel Boxで選んでいるアトリビュートは、ここでは取得しない(:meth:`getChannelBoxPlugs` を使う)。

        Returns:
            list[Plug]: 削除されていないアトリビュート。
        """
        return [item for item in self._items if isinstance(item, Plug) and self._valid(item)]

    def getComponents(self):
        """コンポーネントとして選ばれた対象を、まとめて取得する。

        削除されていない要素を、ShapeのDAGパスと要素の種類ごとに1つにまとめる。

        Returns:
            list[Components]: ShapeのDAGパスと種類ごとにまとめた要素。
        """
        groups = {}
        classes = {Vertex: Vertices, Edge: Edges, Face: Faces, UV: UVs, CV: CVs, SurfaceCV: SurfaceCVs, LatticePoint: LatticePoints, VertexFace: VertexFaces}
        for item in self._items:
            if isinstance(item, Component) and self._valid(item):
                key = (item.shape.getFullName(), item.__class__)
                groups.setdefault(key, (item.shape, []))[1].append(item.index)
        return [classes[kind](shape, indices) for (_, kind), (shape, indices) in groups.items()]

    def getOwners(self):
        """対象を持つノードを取得する。

        ノードはそのノード自身、アトリビュートはそのノード、コンポーネントはそのShapeになる。
        削除された対象は除く。

        Returns:
            list[Node]: 対象を持つノード。DAGパスが同じものは1つにまとめる。
        """
        result = {}
        for item in self._items:
            if self._valid(item):
                node = item if isinstance(item, Node) else item.shape if isinstance(item, Component) else item.getNode()
                result.setdefault(node.getFullName(), node)
        return list(result.values())

    def filter(self, type):
        """ノード型やコンポーネントの種類で絞り込んだ、新しい選択を返す。

        Args:
            type (str): 絞り込む種類。次のどれかを指定する。

                - jointなどのノード型。
                - コンポーネントの種類 vertex/edge/face/uv/controlVertex。
                  記号のvtx/e/f/map/cvでも指定できる。
                - アトリビュートを選ぶplug。

        Returns:
            Selection: 当てはまり、削除されていない対象。元の選択は変更しない。
        """
        component_type = {"vertex": "vtx", "edge": "e", "face": "f", "uv": "map", "controlVertex": "cv"}.get(type, type) if isinstance(type, str) else type
        result = []
        for item in self._items:
            if not self._valid(item):
                continue
            if isinstance(item, Node) and item.isType(type):
                result.append(item)
            elif isinstance(item, Component) and item.component_type == component_type:
                result.append(item)
            elif isinstance(item, Plug) and type == "plug":
                result.append(item)
        return Selection(result)

    def select(self, mode="replace", missing="skip"):
        """持っている対象をMayaの選択にする。

        ``cmds.select(noExpand=True)`` で選ぶ。Undoが有効なら、1回のUndoで戻せるようにまとめて記録する。
        fast引数は持たない。

        Args:
            mode (str): 選び方。replaceは置き換え、addは追加、removeは選択から外す。既定はreplace。
            missing (str): 削除された対象の扱い。skipは除いて続け、errorは選択を変える前に例外にする。
                既定はskip。

        Returns:
            Selection: 自身。中身が空の場合は、replaceのときだけ選択を解除する。

        Raises:
            ValueError: modeまたはmissingに対応していない値を指定した場合。
            RuntimeError: missingがerrorで、削除された対象がある場合。
        """
        with undoChunk("mlibSelectionSelect"):
            if mode not in ("replace", "add", "remove"):
                raise ValueError("modeはreplace・add・removeのどれかで指定してください")
            names = self._names(missing)
            if names:
                flag = {"replace": "replace", "add": "add", "remove": "deselect"}[mode]
                cmds.select(names, noExpand=True, **{flag: True})
            elif mode == "replace":
                cmds.select(clear=True)
            return self

    @staticmethod
    def _resolve(selection, name=None):
        """MSelectionListを、mlibのオブジェクト(Node・Plug・Component)の列へ変換する。

        対応していない要素はTypeErrorになる。

        nameは、選択リストへ要素を追加したときの文字列。要素が1つの場合に、インスタンス化された
        ノードのアトリビュートが、どのインスタンスのものかを決めるのに使う(_selection_ownerを参照)。

        Args:
            selection (om2.MSelectionList): 変換元の選択リスト。
            name (str | None): 要素を1つ追加したときの名前。どのDAGインスタンスのものかを決めるのに使う。

        Returns:
            list[Node | Plug | Component]: 選択リストの順のまま変換したオブジェクト。
        """
        result = []
        for index in range(selection.length()):
            plug = _selection_plug(selection, index)
            if plug is not None:
                # インスタンス化されたノードのアトリビュートは、選択されたインスタンスのノードを所有ノードにする。
                hint = name if selection.length() == 1 else None
                mobject, path = Node._selection_owner(selection, index, hint, plug=True)
                result.append(Plug(Node(path if path is not None else mobject), plug))
                continue
            found = _selection_component(selection, index)
            if found is None:
                result.append(Node(_selection_node(selection, index)))
                continue
            result.extend(Component._from_api(*found))
        return result

    def _valid(self, item):
        """対象がまだ使えるか調べる。

        削除されたノード・アトリビュートや、範囲の外になった要素を見つける。

        Args:
            item (Node | Plug | Component): 調べる対象。

        Returns:
            bool: 対象が存在し、種類ごとの条件を満たせばTrue。
        """
        try:
            if isinstance(item, Node):
                return item.isValid()
            if isinstance(item, Plug) and not item.isValid():
                # 所有ノードの削除に加え、deleteAttr で削除された動的アトリビュートも無効として扱う。
                return False
            return _exists(item.getFullName())
        except (RuntimeError, ValueError, IndexError):
            return False

    def _names(self, missing):
        """選択を変える前に、使える対象の名前を集める。

        missingが不正ならValueError、削除された対象があってmissingがerrorならRuntimeErrorにする。

        Args:
            missing (str): skipなら削除された対象を除き、errorなら選択を変える前に例外を送出する。

        Returns:
            list[str]: 使える対象のフルネーム。missingがskipなら、削除された対象を除く。
        """
        if missing not in ("skip", "error"):
            raise ValueError("missingは'skip'か'error'で指定してください")
        names = []
        for item in self._items:
            if self._valid(item):
                names.append(item.getFullName())
            elif missing == "error":
                raise RuntimeError("選択に存在しない項目が含まれています")
        return names


def _selection_node(selection, index):
    """選択リストのノードの要素を取得する。

    DAGノードは、選ばれたインスタンスのDAGパスで取得する。

    Args:
        selection (om2.MSelectionList): 選択リスト。
        index (int): 要素の番号。

    Returns:
        om2.MDagPath | om2.MObject: DAGノードならDAGパス、DGノードならMObject。
    """
    node = selection.getDependNode(index)
    if node.hasFn(om2.MFn.kDagNode):
        return selection.getDagPath(index)
    return node


def _is_plain_node_name(name):
    """ワイルドカード・アトリビュート・コンポーネントを含まない、ノード名だけの文字列か判定する。

    Args:
        name (str): 判定する名前。

    Returns:
        bool: 「.」「*」「?」のいずれも含まない空でない文字列なら True。
    """
    return bool(name) and "." not in name and "*" not in name and "?" not in name


def _resolve_names(names, plugs=False):
    """名前の列から、まとめてノードやアトリビュートを探す(lsとSelectionの内部で使う)。

    名前ごとに選択リストを作ると遅いので、``_NAME_CHUNK`` 件ずつ同じ選択リストを使い回して追加する。
    追加して要素がちょうど1つ増えた名前だけを、その要素へ対応付ける。
    対応付けは選択リストの並びではなくnamesの順に行うので、戻り値の順はnamesと同じになる。

    次の名前は対応付けずにNoneにする。呼び出し側が、名前を1つずつ調べる従来の方法で探し直す
    (結果と例外は、名前を1つずつ調べた場合と同じになる)。

    - 見つからない名前(存在しない、または1つに決まらない)。
    - 同じリストにすでにある要素と重なって、要素が増えない名前(重なりはまとめず、名前ごとに返す)。
    - 複数の要素に当てはまる名前と、ワイルドカード(「*」「?」)を含む名前。
    - plugsがTrueで、要素がアトリビュート(MPlug)にならない名前(コンポーネントなど)。

    Args:
        names (Sequence[str]): 探す名前。ノード名とアトリビュート名を混ぜずに渡す。
        plugs (bool): Trueならアトリビュート名(「.」を含む名前)、Falseならノード名として対応付ける。

    Returns:
        list[tuple | None]: namesと同じ長さの列。対応付けた名前は
            ``(MObject, MDagPath | None, MPlug | None)`` になる(DGノードのDAGパスと、ノード名のMPlugはNone)。
    """
    result: List[Optional[Tuple[Any, ...]]] = [None] * len(names)
    selection = om2.MSelectionList()
    for start in range(0, len(names), _NAME_CHUNK):
        selection.clear()
        added = []
        for position in range(start, min(start + _NAME_CHUNK, len(names))):
            name = names[position]
            if "*" in name or "?" in name:
                continue
            before = selection.length()
            try:
                selection.add(name)
            except RuntimeError:
                continue
            if selection.length() == before + 1:
                added.append((position, before))
        for position, index in added:
            name = names[position]
            if plugs:
                mplug = _selection_plug(selection, index)
                if mplug is None:
                    continue
                mobject, dag_path = Node._selection_owner(selection, index, name, plug=True)
                result[position] = (mobject, dag_path, mplug)
            else:
                mobject, dag_path = Node._selection_owner(selection, index, name)
                result[position] = (mobject, dag_path, None)
    return result
