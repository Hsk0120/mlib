"""Maya の blendShape デフォーマを扱う。"""

import math
import re

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
import maya.mel as mel

from ..components.vertex import Vertex, Vertices
from ..core.attributeType import typed_data
from ..core.fastWrite import require_writable, set_attr
from ..decorator import _edit_context, _require_bool, undoChunk
from ..maths.vector import Vector
from ..plugs.plug import Plug
from ..util import _mirror_axis
from .geometryFilter import GeometryFilter
from .node import Node

#: エイリアスの対象 ``weight[<番号>]`` から論理番号を取り出す。
_WEIGHT_ALIAS = re.compile(r"^(?:weight|w)\[(\d+)\]$")
#: ``inputTargetItem`` の論理番号は ``5000 + 項目のウェイト * 1000``。1.0の項目(ターゲット本体)は6000。
_ITEM_OFFSET = 5000
_FULL_ITEM = 6000
#: 論理番号の上限(MayaのMPlugの論理番号はint32)。
_MAX_INDEX = 2147483647
#: :meth:`BlendShape.exportTargets` が書くファイルの形式名と版。
_TARGETS_FORMAT = "mlib.blendShapeTargets"
_TARGETS_VERSION = 1
#: :meth:`BlendShape.setTargetsData` の既存ターゲットの扱い。
_TARGETS_MODES = ("replace", "empty")


class BlendShape(GeometryFilter):
    """blendShapeデフォーマを扱うクラス。ターゲットを調べる・変える・JSONに保存する操作を持つ。

    ターゲット名は、ウェイト(``weight[i]``)のエイリアスのこと。Shape Editorやチャンネルボックスに
    表示される名前と同じになる。``"smile_L" in blendShape`` で、そのターゲット名があるかを調べられる。

    ターゲットを受け取るメソッドには、次のどれを渡してもよい。

    - ターゲット名(str)
    - 論理番号(int。boolは不可)
    - このノードの ``weight`` の要素のPlug

    ベース(変形される形状)が複数あるときは、ベースごとの操作で ``base`` に対象の形状(かそのTransform)を渡す。
    省略すると、論理番号がいちばん小さいベースを使う。

    デルタは、ベースのオブジェクト空間での変位(cm)で、頂点番号と組にして扱う。
    in-betweenは ``fullWeight`` (1.0以外の項目のウェイト)で選ぶ。
    通常の変更はMaya標準のコマンドで行い、1回のUndoにまとめる。
    ``fast=True`` を使えるのは、デルタと頂点マスクの書き込みだけ。OpenMayaで書き込み、Undoには記録しない。

    Note:
        ターゲットを取り除くには :meth:`removeTarget` を使う。``getPlug("weight").removeElement(i)`` は
        ウェイトの要素だけを消し、エイリアスと ``inputTarget[].inputTargetGroup[i]`` は残ってしまう。
    """

    def __contains__(self, name):
        """ターゲット名(ウェイトのエイリアス)があるかを返す。

        Args:
            name (str): ターゲット名。

        Returns:
            bool: ターゲットがあればTrue。

        Raises:
            TypeError: nameが文字列以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        return self._target_lookup(name) is not None

    def getTargetNames(self):
        """ターゲット名を、論理番号の順に取得する。

        Returns:
            list[str]: ウェイトのエイリアス。エイリアスの無いウェイトの要素は含まない。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        return [name for _index, name in sorted(self._target_items())]

    def getTargetIndex(self, target):
        """ターゲットのウェイトの論理番号を取得する。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。

        Returns:
            int: ``weight`` の論理番号。``inputTargetGroup`` の番号と同じ。

        Raises:
            TypeError: targetが使えない型(boolを含む)の場合。
            ValueError: ターゲットが無い場合、またはtargetがほかのノードや別のアトリビュートのPlugの場合。
            RuntimeError: ノードが無効な場合。
        """
        return self._target_index(target)

    def getWeightPlug(self, target):
        """ターゲットのウェイトのアトリビュート(``weight[i]``)を取得する。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。

        Returns:
            Plug: ``weight`` の要素のPlug。接続や値の設定に使う。

        Raises:
            TypeError: targetが使えない型(boolを含む)の場合。
            ValueError: ターゲットが無い場合、またはtargetがほかのノードや別のアトリビュートのPlugの場合。
            RuntimeError: ノードが無効な場合。
        """
        return self.getPlug("weight")[self._target_index(target)]

    def getBaseGeometry(self):
        """変形する形状(出力ジオメトリ)を取得する。

        Returns:
            list[Node]: 変形される形状。geometryFilterの出力の順に並ぶ。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("ジオメトリの取得")
        return [Node(mobject) for mobject in oma2.MFnGeometryFilter(self.mnode()).getOutputGeometry()]

    def addTarget(self, mesh, name=None):
        """ターゲットを追加する。

        ``cmds.blendShape(edit=True, target=...)`` と同じ処理で、空いている次の論理番号へ追加する。
        最初のベース(:meth:`getBaseGeometry` の先頭)のターゲットとして追加し、ウェイトは0になる。
        ターゲット形状との接続は、Mayaの既定どおり残す。Undoが有効なら、1回のUndoで戻せる。

        Args:
            mesh (str | Node): ターゲットの形状、またはそのTransform。
            name (str | None): ターゲット名。Noneならメッシュの名前になる(Mayaの既定)。

        Returns:
            Plug: 追加したターゲットのウェイト(``weight[i]``)。

        Raises:
            TypeError: nameが文字列・None以外の場合、またはmeshが使えない型の場合。
            ValueError: nameが空文字列の場合、同じ名前のターゲットがすでにある場合、またはmeshが無効な場合。
            RuntimeError: ノードが無効な場合、ベースが無い場合、またはMayaが追加を拒否した場合。
        """
        if name is not None and not isinstance(name, str):
            raise TypeError("nameは文字列かNoneで指定してください")
        if name == "":
            raise ValueError("nameは空でない文字列かNoneで指定してください")
        self._require_valid("ターゲットの追加")
        mesh_name = Node._input_name(mesh)
        if name is not None and name in self:
            raise ValueError(f"blendShapeのターゲット{name!r}は{self.getName()}にすでに存在します")
        bases = self.getBaseGeometry()
        if not bases:
            raise RuntimeError(f"blendShape {self.getName()}にはターゲットを追加するジオメトリがありません")
        index = self._unused_index()
        with undoChunk("mlibBlendShapeAddTarget"):
            cmds.blendShape(self.getFullName(), edit=True, target=(bases[0].getFullName(), index, mesh_name, 1.0))
            if name is not None and self._alias_of(index) != name:
                cmds.aliasAttr(name, f"{self.getFullName()}.weight[{index}]")
            return self.getPlug("weight")[index]

    def removeTarget(self, target):
        """ターゲットを完全に取り除く。

        ターゲット形状がすでに削除されていてもよい。
        ``cmds.blendShape(edit=True, remove=True, target=...)`` と同じく、次のものを取り除く
        (Maya標準の ``blendShapeDeleteTargetGroup`` を使う)。

        - ウェイトの要素とエイリアス
        - すべてのベースの ``inputTarget[].inputTargetGroup[i]``
        - Shape Editorでどこに入っているかの情報

        ウェイトへの入力の接続は外し、ウェイトを動かしているcombinationShapeノードはMayaの決まりどおり削除する。
        ターゲット形状のノードは削除しない。Undoが有効なら、1回のUndoで戻せる。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: targetが使えない型(boolを含む)の場合。
            ValueError: ターゲットが無い場合。
            RuntimeError: ノードが無効な場合、ウェイトがロックされている場合、またはMayaが取り除くのを拒否した場合。
        """
        index = self._target_index(target)
        if self.getPlug("weight")[index].isLocked():
            raise RuntimeError(f"{self.getName()}のロックされたblendShapeのターゲット{target!r}は削除できません")
        with undoChunk("mlibBlendShapeRemoveTarget"):
            command = f'blendShapeDeleteTargetGroup("{self.getFullName()}", {index})'
            if not mel.eval(command):
                raise RuntimeError(f"Mayaが{self.getName()}のblendShapeのターゲット{target!r}を削除できませんでした")
            return self

    def getInBetweenWeights(self, target, base=None):
        """ターゲットのin-betweenの項目のウェイトを取得する。

        ``inputTargetItem`` の論理番号から `` (番号 - 5000) / 1000`` で求め、1.0(ターゲット本体)は除く。
        今の ``weight`` の値は見ない。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。

        Returns:
            list[float]: in-betweenの項目のウェイト。小さい順に並ぶ。in-betweenが無ければ空リスト。

        Raises:
            TypeError: target・baseが使えない型の場合。
            ValueError: ターゲットが無い場合、baseがこのblendShapeのベースでない場合、
                またはターゲットがそのベースのデータを持たない場合。
        """
        bi, index = self._resolve_group(target, base)
        return [(item - _ITEM_OFFSET) / 1000.0 for item in self._item_indices(bi, index) if item != _FULL_ITEM]

    def addInBetween(self, target, geometry, weight, base=None, relative=False):
        """すでにあるターゲットへin-betweenを追加する。

        ``cmds.blendShape(edit=True, inBetween=True)`` と同じ処理をする。
        ``geometry`` との接続は、Mayaの既定どおり残す。Undoが有効なら、1回のUndoで戻せる。

        Args:
            target (str | int | Plug): 追加先のターゲット。ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            geometry (str | Node): in-betweenの形状。ベースと頂点数が同じメッシュ(かそのTransform)。
            weight (float): in-betweenが完全に効くウェイト。0と1以外の、-5以上で0.001刻みの値。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            relative (bool): Trueならターゲット本体からの相対、Falseなら絶対(Mayaの既定)のin-betweenにする。既定はFalse。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: target・geometry・base・weightの型が不正な場合、relativeがbool以外の場合、
                またはgeometryがメッシュでない場合。
            ValueError: ターゲットが無い場合、weightが0か1・すでにある項目・範囲外・0.001刻みでない場合、
                または頂点数がベースと違う場合。
        """
        _require_bool(relative, "relative")
        bi, index = self._resolve_group(target, base)
        item = _weight_item(weight)
        if item in (_ITEM_OFFSET, _FULL_ITEM):
            raise ValueError(f"インビトウィーンのウェイトに0と1は指定できません: {weight}")
        if item in self._item_indices(bi, index):
            raise ValueError(f"ターゲット{index}には、ウェイト{weight}のインビトウィーンがすでに存在します")
        shape = _mesh_shape(geometry)
        self._require_vertex_count(bi, shape)
        with undoChunk("mlibBlendShapeAddInBetween"):
            cmds.blendShape(
                self.getFullName(),
                edit=True,
                inBetween=True,
                inBetweenType="relative" if relative else "absolute",
                target=(self._base_shape(bi).getFullName(), index, shape.getFullName(), weight),
            )
            return self

    def removeInBetween(self, target, weight):
        """指定したウェイトのin-betweenを取り除く。

        すべてのベースから取り除く。Maya標準の ``blendShapeDeleteInBetweenTarget`` を使う。
        Undoが有効なら、1回のUndoで戻せる。

        Args:
            target (str | int | Plug): in-betweenを持つターゲット。ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            weight (float): 取り除くin-betweenのウェイト。1.0(ターゲット本体)は指定できない。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: targetの型が不正な場合、またはweightが数値でない場合。
            ValueError: ターゲットが無い場合、またはそのウェイトのin-betweenが無い場合。
        """
        index = self._target_index(target)
        item = _weight_item(weight)
        if item == _FULL_ITEM or not any(item in self._item_indices(bi, index) for bi in self._base_indices()):
            raise ValueError(f"ターゲット{index}に、ウェイト{weight}のインビトウィーンはありません")
        with undoChunk("mlibBlendShapeRemoveInBetween"):
            mel.eval(f'blendShapeDeleteInBetweenTarget("{self.getFullName()}", {index}, {item})')
            return self

    def getTargetWeights(self, target, base=None):
        """ターゲットの頂点マスクを、頂点番号の順に取得する。

        頂点マスクは ``inputTargetGroup[i].targetWeights`` の値。
        値が書かれていない頂点は、Mayaの既定どおり1.0として返す。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。

        Returns:
            list[float]: ベースの頂点数と同じ長さの新しいlist。

        Raises:
            TypeError: target・baseが使えない型の場合、またはベースがメッシュでない場合。
            ValueError: ターゲットが無い場合、baseがこのblendShapeのベースでない場合、
                またはターゲットがそのベースのデータを持たない場合。
        """
        bi, index = self._resolve_group(target, base)
        return self._read_vertex_weights(self._group_path(bi, index) + ".targetWeights", self._vertex_count(bi))

    def setTargetWeights(self, target, weights, base=None, *, fast=False):
        """ターゲットの頂点マスクを設定する。

        頂点マスクは ``inputTargetGroup[i].targetWeights`` の値。値は0〜1に制限しない。

        - 並び(list等)を渡すと、頂点番号の順にすべての頂点を書き換える。
        - 辞書を渡すと、指定した頂点だけを書き換える。

        通常は、番号が1ずつ続く頂点を範囲指定の1回の ``setAttr`` にまとめ、全体を1回のUndoにする。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            weights (Sequence[float] | dict[int, float]): 頂点数と同じ数の値、または頂点番号から値への辞書。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: target・base・値の型が不正な場合、fastがbool以外の場合、またはベースがメッシュでない場合。
            ValueError: ターゲットが無い場合、並びの長さが頂点数と違う場合、または有限でない値がある場合。
            IndexError: 頂点番号が範囲外の場合。
            RuntimeError: アトリビュートがロックされているか入力が接続されている場合、
                またはMayaが書き込みを拒否した場合。
        """
        with _edit_context("mlibBlendShapeSetTargetWeights", fast):
            bi, index = self._resolve_group(target, base)
            values = _vertex_values(weights, self._vertex_count(bi))
            self._write_vertex_weights(self._group_path(bi, index) + ".targetWeights", values, fast=fast)
            return self

    def getTargetDeltas(self, target, base=None, fullWeight=1.0):
        """ターゲット(またはin-between)の項目に保存されたデルタを取得する。

        ターゲット形状が接続されていれば、Mayaが計算した今のデルタを返す。
        値はベースのオブジェクト空間での変位(cm)で、変位を持つ頂点だけを含む。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。1.0ならターゲット本体、それ以外ならin-between。既定は1.0。

        Returns:
            dict[int, Vector]: 頂点番号から変位への辞書。

        Raises:
            TypeError: target・baseの型が不正な場合、またはfullWeightが数値でない場合。
            ValueError: ターゲット、またはそのウェイトの項目が無い場合。
        """
        bi, index, item = self._resolve_item(target, base, fullWeight)
        indices, offsets = self._read_deltas(self._item_path(bi, index, item))
        return {vertex: Vector(offset) for vertex, offset in zip(indices, offsets)}

    def setTargetDeltas(self, target, deltas, base=None, fullWeight=1.0, disconnect=False, *, fast=False):
        """ターゲット(またはin-between)の項目のデルタを、まるごと置き換える。

        指定しなかった頂点は変位0になる。ほかの項目のデルタは変えない。
        ターゲット形状が接続されている場合、既定では何も変えずにエラーにする
        (接続から計算し直されて上書きされてしまうため)。``disconnect=True`` なら接続を外してから書き込む。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            deltas (dict[int, Sequence[float]]): 頂点番号から変位(xyz、cm)への辞書。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。1.0ならターゲット本体、それ以外ならin-between。既定は1.0。
            disconnect (bool): Trueなら、ターゲット形状の接続を外してから書き込む。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: 引数の型が不正な場合、disconnect・fastがbool以外の場合、またはベースがメッシュでない場合。
            ValueError: ターゲットや項目が無い場合、または変位が3つの有限な数値でない場合。
            IndexError: 頂点番号が範囲外の場合。
            RuntimeError: ターゲット形状が接続されていてdisconnect=Falseの場合、またはMayaが書き込みを拒否した場合。
        """
        with _edit_context("mlibBlendShapeSetTargetDeltas", fast):
            _require_bool(disconnect, "disconnect")
            bi, index, item = self._resolve_item(target, base, fullWeight)
            rows = _delta_values(deltas, self._vertex_count(bi))
            path = self._item_path(bi, index, item)
            self._release_input(path, disconnect, fast=fast)
            self._write_deltas(path, [row[0] for row in rows], [row[1] for row in rows], fast=fast)
            return self

    def getTargetVertices(self, target, base=None, fullWeight=1.0, *, tolerance=0.0):
        """デルタの長さがしきい値を超える頂点を取得する。

        今の ``weight``・envelope・頂点マスクは判定に使わない。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。1.0ならターゲット本体、それ以外ならin-between。既定は1.0。
            tolerance (float): この長さ(cm)以下の変位の頂点を除く。0以上の有限な数値。既定は0で、変位0の頂点だけを除く。

        Returns:
            Vertices: ベースの頂点。番号の小さい順に並ぶ。

        Raises:
            TypeError: 引数の型が不正な場合、またはベースがメッシュでない場合。
            ValueError: ターゲットや項目が無い場合、またはtoleranceが負の数か有限でない場合。
        """
        limit = _tolerance(tolerance)
        bi, index, item = self._resolve_item(target, base, fullWeight)
        indices, offsets = self._read_deltas(self._item_path(bi, index, item))
        return Vertices(self._base_shape(bi), [vertex for vertex, offset in zip(indices, offsets) if om2.MVector(offset).length() > limit])

    def resetTargetVertices(self, target, vertices, base=None, fullWeight=1.0, disconnect=False, *, fast=False):
        """指定した頂点の変位を0に戻す。

        ほかの頂点の変位はそのまま残す。ターゲット形状が接続されている場合の扱いは :meth:`setTargetDeltas` と同じ。
        変位を持たない頂点だけを指定した場合は、何も変えない。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            vertices (int | Vertex | Vertices | Iterable[int | Vertex]): ベースの頂点、または頂点番号。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。1.0ならターゲット本体、それ以外ならin-between。既定は1.0。
            disconnect (bool): Trueなら、ターゲット形状の接続を外してから書き込む。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: 引数の型が不正な場合、またはベースがメッシュでない場合。
            ValueError: ターゲットや項目が無い場合、または頂点が別の形状のものの場合。
            IndexError: 頂点番号が範囲外の場合。
            RuntimeError: ターゲット形状が接続されていてdisconnect=Falseの場合、またはMayaが書き込みを拒否した場合。
        """
        with _edit_context("mlibBlendShapeResetTargetVertices", fast):
            _require_bool(disconnect, "disconnect")
            bi, index, item = self._resolve_item(target, base, fullWeight)
            remove = set(self._vertex_indices(vertices, bi))
            self._remove_vertices(self._item_path(bi, index, item), remove, disconnect, fast=fast)
            return self

    def reduceTargetDeltas(self, target, tolerance=0.0, base=None, fullWeight=1.0, disconnect=False, *, fast=False):
        """デルタの長さがしきい値以下の頂点を、項目のデータから取り除く。

        保存するデータが減る。toleranceが0(既定)なら、変位0の頂点だけを取り除くので変形の結果は変わらない。
        正の値を指定すると、その長さ以下の小さな変位は0になるため、変形の結果もわずかに変わる。
        ターゲット形状が接続されている場合の扱いは :meth:`setTargetDeltas` と同じ。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            tolerance (float): この長さ(cm)以下の変位を取り除く。0以上の有限な数値。既定は0で、変位0の頂点だけを取り除く。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。1.0ならターゲット本体、それ以外ならin-between。既定は1.0。
            disconnect (bool): Trueなら、ターゲット形状の接続を外してから書き込む。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: 引数の型が不正な場合(ベースはメッシュ以外のカーブなどでもよい)。
            ValueError: ターゲットや項目が無い場合、またはtoleranceが負の数か有限でない場合。
            RuntimeError: ターゲット形状が接続されていてdisconnect=Falseの場合、またはMayaが書き込みを拒否した場合。
        """
        with _edit_context("mlibBlendShapeReduceTargetDeltas", fast):
            _require_bool(disconnect, "disconnect")
            limit = _tolerance(tolerance)
            bi, index, item = self._resolve_item(target, base, fullWeight)
            path = self._item_path(bi, index, item)
            indices, offsets = self._read_deltas(path)
            remove = {vertex for vertex, offset in zip(indices, offsets) if om2.MVector(offset).length() <= limit}
            self._remove_vertices(path, remove, disconnect, fast=fast)
            return self

    def mirrorTarget(self, target, axis="x", positiveToNegative=True, base=None):
        """ターゲットの片側の変形を、反対側へミラーする。

        ``cmds.blendShape(edit=True, mirrorTarget=...)`` を使う。対称の頂点は、オブジェクト空間の座標で探す。
        Undoが有効なら、1回のUndoで戻せる。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            axis (str | int): 反転する軸。既定は ``"x"``。``"x"``・``"y"``・``"z"`` (大文字・小文字は問わない)、
                ミラー面の ``"YZ"`` など、または0〜2で指定する。
            positiveToNegative (bool): Trueなら正の側を負の側へ、Falseなら負の側を正の側へ写す。既定はTrue。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: 引数の型が不正な場合、またはベースがメッシュでない場合。
            ValueError: ターゲットが無い場合、またはaxisが軸として使えない場合。
            RuntimeError: ターゲット形状が接続されている場合(先に :meth:`duplicateTarget` などでベイクしておく)。
        """
        _require_bool(positiveToNegative, "positiveToNegative")
        bi, index = self._resolve_group(target, base)
        name = self._mirror_axis_name(bi, index, axis)
        with undoChunk("mlibBlendShapeMirrorTarget"):
            cmds.blendShape(
                self.getFullName(), edit=True, mirrorTarget=(bi, index), symmetryAxis=name, symmetrySpace=1, mirrorDirection=0 if positiveToNegative else 1
            )
            return self

    def flipTarget(self, target, axis="x", base=None):
        """ターゲットの変形を左右反転する。

        ``cmds.blendShape(edit=True, flipTarget=...)`` を使う。
        左右で別々のターゲットを作るなら、:meth:`duplicateTarget` で複製してから反転する。
        Undoが有効なら、1回のUndoで戻せる。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            axis (str | int): 反転する軸。既定は ``"x"``。``"x"``・``"y"``・``"z"``、ミラー面の ``"YZ"`` など、または0〜2で指定する。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: 引数の型が不正な場合、またはベースがメッシュでない場合。
            ValueError: ターゲットが無い場合、またはaxisが軸として使えない場合。
            RuntimeError: ターゲット形状が接続されている場合。
        """
        bi, index = self._resolve_group(target, base)
        name = self._mirror_axis_name(bi, index, axis)
        with undoChunk("mlibBlendShapeFlipTarget"):
            cmds.blendShape(self.getFullName(), edit=True, flipTarget=(bi, index), symmetryAxis=name, symmetrySpace=1)
            return self

    def duplicateTarget(self, target, name=None):
        """ターゲットを複製する。

        すべてのベースのデルタ・in-between・頂点マスクごと、新しい論理番号へ複製する。

        - ターゲット形状が接続されていれば、今の形をベイクする。複製したほうは接続を持たない。
        - 新しいウェイトは0になる。外からウェイトを動かしているドライバーは複製しない。
        - Shape Editorでは、元のターゲットと同じフォルダーの最後に置く。

        Undoが有効なら、1回のUndoで戻せる。

        Args:
            target (str | int | Plug): 複製元のターゲット。ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            name (str | None): 新しいターゲット名。Noneなら ``<元の名前>Copy`` になる(重なれば末尾に番号が付く)。

        Returns:
            Plug: 新しいターゲットのウェイト(``weight[i]``)。

        Raises:
            TypeError: targetの型が不正な場合、nameが文字列・None以外の場合、またはベースがメッシュでない場合。
            ValueError: ターゲットが無い場合、またはnameが空かすでにあるアトリビュートと重なる場合。
        """
        index = self._target_index(target)
        if name is not None:
            self._require_new_name(name)
        record = self._capture_target(index)
        if name is None:
            name = self._copy_name(record["name"] or f"target{index}")
        destination = self._unused_index()
        with undoChunk("mlibBlendShapeDuplicateTarget"):
            self._write_target(destination, record, name, created=True)
            self.getPlug("weight")[destination].set(0.0)
            model = _Directories.read(self)
            model.move(destination, model.parentOf(index), after=index)
            model.write(self)
            return self.getPlug("weight")[destination]

    def replaceTarget(self, target, geometry, base=None, fullWeight=1.0):
        """ターゲット(またはin-between)の項目の形状を、別のメッシュに差し替える。

        別のメッシュを接続し、以後のデルタはそのメッシュから計算されるようにする。
        ターゲット名・ウェイトの値と接続・頂点マスクはそのまま残る。Undoが有効なら、1回のUndoで戻せる。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            geometry (str | Node): 新しいターゲット形状。ベースと頂点数が同じメッシュ(かそのTransform)。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。1.0ならターゲット本体、それ以外ならin-between。既定は1.0。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: 引数の型が不正な場合、またはgeometryかベースがメッシュでない場合。
            ValueError: ターゲットや項目が無い場合、または頂点数がベースと違う場合。
            RuntimeError: Mayaが接続を拒否した場合。
        """
        bi, index, item = self._resolve_item(target, base, fullWeight)
        shape = _mesh_shape(geometry)
        self._require_vertex_count(bi, shape)
        source = f"{shape.getFullName()}.worldMesh[{shape.mpath().instanceNumber()}]"
        path = self._item_path(bi, index, item)
        with undoChunk("mlibBlendShapeReplaceTarget"):
            if not self._mplug(path + ".inputGeomTarget").isDestination:
                # 接続のUndoは保存済みのデルタを戻さないため、今のデルタを書き直してUndoに記録する。
                indices, offsets = self._read_deltas(path)
                self._write_deltas(path, indices, offsets)
            cmds.connectAttr(source, self._attr(path + ".inputGeomTarget"), force=True)
            return self

    def targetEdit(self, target=None, state=True, fullWeight=1.0):
        """ターゲットの編集モード(Shape EditorのEdit)を始める、または終える。

        ``cmds.sculptTarget`` を使う。編集モードの間は、ベースをスカルプトした結果がターゲットのデルタへ書き込まれる。
        Undoが有効なら、1回のUndoで戻せる。

        Args:
            target (str | int | Plug | None): 編集を始めるターゲット。始めるときは必ず指定し、終えるときは使わない。
            state (bool): Trueなら編集を始め、FalseならこのblendShapeの編集モードを終える。既定はTrue。
            fullWeight (float): 編集する項目のウェイト。1.0ならターゲット本体、それ以外ならin-between。既定は1.0。

        Returns:
            BlendShape: 自身。

        Raises:
            TypeError: targetの型が不正な場合、stateがbool以外の場合、またはfullWeightが数値でない場合。
            ValueError: 始めるときにtargetが無い場合、またはターゲットや項目が無い場合。
        """
        _require_bool(state, "state")
        if not state:
            with undoChunk("mlibBlendShapeTargetEdit"):
                cmds.sculptTarget(self.getFullName(), edit=True, target=-1)
                return self
        if target is None:
            raise ValueError("blendShapeのターゲットの編集を始めるにはtargetが必要です")
        index = self._target_index(target)
        item = _weight_item(fullWeight)
        if not any(item in self._item_indices(bi, index) for bi in self._base_indices()):
            raise ValueError(f"ターゲット{index}に、ウェイト{fullWeight}の項目はありません")
        with undoChunk("mlibBlendShapeTargetEdit"):
            cmds.sculptTarget(self.getFullName(), edit=True, target=index, inbetweenWeight=fullWeight)
            return self

    def getTargetsData(self):
        """すべてのターゲットを、JSONへ書ける辞書として取得する。

        :meth:`setTargetsData` に渡せば元に戻せる。辞書には次のものが入る。

        - ベースごと: 頂点数と頂点マスク(baseWeights)
        - ターゲットごと: 名前・論理番号・今のウェイト・ウェイトへの入力の接続(ドライバー)・頂点マスク・
          デルタ・in-between
        - Shape Editorのフォルダー

        ターゲット形状が接続されていれば、今の形をベイクしたデルタとして記録する。

        Returns:
            dict: ``bases``・``targets``・``folders`` を持つ新しい辞書。数学型は含まない。

        Raises:
            TypeError: ベースがメッシュでない場合。
            RuntimeError: ノードが無効な場合。
        """
        # 循環参照の回避: mlib.jsonはノード・Plugのクラスを使う。
        from ..json.nodeRef import NodeRef

        self._require_valid("ターゲットの取得")
        bases = []
        for bi in self._base_indices():
            shape = self._base_shape(bi)
            count = self._vertex_count(bi)
            weights = self._read_vertex_weights(f"inputTarget[{bi}].baseWeights", count)
            bases.append({"index": bi, "geometry": NodeRef.capture(shape).toData(), "vertexCount": count, "baseWeights": _sparse(weights)})
        targets = [self._capture_target(index, driver=True) for index in self._target_indices()]
        return {
            "blendShape": NodeRef.capture(self).toData(),
            "bases": bases,
            "targets": targets,
            "folders": _Directories.read(self).toData(self._target_indices()),
        }

    def setTargetsData(self, data, *, nameMap=None, replace=None, namespaceMap=None, mode="replace"):
        """:meth:`getTargetsData` の辞書からターゲットを元に戻す。

        ベースは論理番号で対応させる。頂点数が違えば、何も変えずにValueErrorにする。

        - ``mode="replace"`` (既定): 同じ名前のターゲットの中身を置き換え、無いターゲットは追加する。
        - ``mode="empty"``: ターゲットが1つも無いblendShapeにだけ読み込む。

        ウェイトのドライバーは、``nameMap``・``replace``・``namespaceMap`` で名前を対応させてつなぎ直す
        (やり方は :class:`mlib.json.NameMapping` と同じ)。見つからないものは値だけを設定して警告する。
        全体を1回のUndoにまとめ、途中で失敗したら元に戻す。

        Args:
            data (dict): :meth:`getTargetsData` の形の辞書。
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。
            replace (Iterable[tuple[str, str]] | None): 順に当てはめる文字列の置き換え。
            namespaceMap (dict[str, str] | None): 名前空間の対応。
            mode (str): ``"replace"`` または ``"empty"``。既定は ``"replace"``。

        Returns:
            ValidationReport: 見つからなかったドライバー(``missing``)と、書けずに飛ばしたもの(``skipped``)。

        Raises:
            TypeError: dataが辞書でない場合、またはmodeが文字列でない場合。
            ValueError: データの形が違う場合、modeが不正な場合、``mode="empty"`` なのにターゲットがある場合、
                ベースが無いか頂点数が違う場合、またはターゲット名がすでにあるアトリビュートと重なる場合。
            RuntimeError: Undoが無効な場合、またはMayaが書き込みを拒否した場合。
        """
        # 循環参照の回避: mlib.jsonはノード・Plugのクラスを使う。
        from ..json.nameMapping import NameMapping
        from ..json.snapshot import ValidationReport

        if not isinstance(mode, str):
            raise TypeError("modeは文字列で指定してください")
        if mode not in _TARGETS_MODES:
            raise ValueError(f"modeは{_TARGETS_MODES}のどれかで指定してください: {mode!r}")
        if not isinstance(data, dict):
            raise TypeError("dataはdictで指定してください")
        mapping = NameMapping(nameMap, replace, namespaceMap)
        self._require_valid("ターゲットの復元")
        if mode == "empty" and self._target_indices():
            raise ValueError(f"blendShape {self.getName()}にはすでにターゲットがあります。mode='empty'はターゲットがない場合だけ使えます")
        report = ValidationReport()
        plan = self._plan_targets(data, mapping, report)
        if not report.valid:
            raise ValueError(f"{self.getName()}のblendShapeのターゲットを復元できません: {'; '.join(report.errors)}")
        with _edit_context("mlibBlendShapeSetTargetsData", False, transaction=True):
            self._apply_targets(data, plan, report)
        report.warn("BlendShape")
        return report

    def exportTargets(self, path):
        """すべてのターゲットをJSONファイルへ書き出す。

        中身は :meth:`getTargetsData` の辞書で、形式名は ``mlib.blendShapeTargets``。

        Args:
            path (str | os.PathLike): 書き出し先。

        Returns:
            pathlib.Path: 書き出したファイルの絶対パス。

        Raises:
            TypeError: ベースがメッシュでない場合。
            OSError: 書き出しに失敗した場合。
        """
        # 循環参照の回避: mlib.jsonはノード・Plugのクラスを使う。
        from ..json import file

        return file.dump(self.getTargetsData(), path, _TARGETS_FORMAT, _TARGETS_VERSION)

    def importTargets(self, path, *, nameMap=None, replace=None, namespaceMap=None, mode="replace"):
        """:meth:`exportTargets` で書き出したファイルからターゲットを元に戻す。

        読み込んだ内容を :meth:`setTargetsData` に渡す。

        Args:
            path (str | os.PathLike): 読み込むファイル。
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。
            replace (Iterable[tuple[str, str]] | None): 順に当てはめる文字列の置き換え。
            namespaceMap (dict[str, str] | None): 名前空間の対応。
            mode (str): ``"replace"`` または ``"empty"``。既定は ``"replace"``。

        Returns:
            ValidationReport: :meth:`setTargetsData` の結果。

        Raises:
            ValueError: 形式名や版が違う場合、または :meth:`setTargetsData` が拒否した場合。
            OSError: 読み込みに失敗した場合。
        """
        # 循環参照の回避: mlib.jsonはノード・Plugのクラスを使う。
        from ..json import file

        _header, data = file.load(path, _TARGETS_FORMAT, _TARGETS_VERSION)
        return self.setTargetsData(data, nameMap=nameMap, replace=replace, namespaceMap=namespaceMap, mode=mode)

    def _target_items(self):
        """エイリアスのあるウェイト要素を ``(論理番号, 名前)`` の並びで返す。

        Returns:
            list[tuple[int, str]]: OpenMayaのエイリアス一覧から得た対応。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("ターゲットの取得")
        items = []
        for alias, attribute in self._dependency_fn().getAliasList():
            match = _WEIGHT_ALIAS.match(attribute)
            if match is not None:
                items.append((int(match.group(1)), alias))
        return items

    def _target_lookup(self, name):
        """ターゲット名の論理番号を返す。無ければNone。

        Args:
            name (str): ターゲット名。

        Returns:
            int | None: 論理番号。

        Raises:
            TypeError: nameが文字列以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        if not isinstance(name, str):
            raise TypeError("blendShapeのターゲット名は文字列で指定してください")
        for index, alias in self._target_items():
            if alias == name:
                return index
        return None

    def _alias_of(self, index):
        """論理番号のウェイトのエイリアスを返す。無ければNone。

        Args:
            index (int): ウェイトの論理番号。

        Returns:
            str | None: エイリアス。
        """
        for item_index, alias in self._target_items():
            if item_index == index:
                return alias
        return None

    def _target_indices(self):
        """ターゲットの論理番号を昇順で返す。

        エイリアスのあるウェイト要素と、いずれかのベースに項目(``inputTargetItem``)を持つ番号の和集合。

        Returns:
            list[int]: 論理番号。
        """
        indices = {index for index, _alias in self._target_items()}
        for bi in self._base_indices():
            for index in self._existing(f"inputTarget[{bi}].inputTargetGroup"):
                if self._existing(self._group_path(bi, index) + ".inputTargetItem"):
                    indices.add(index)
        return sorted(indices)

    def _target_index(self, target):
        """ターゲットの指定を論理番号にする。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。

        Returns:
            int: 存在するターゲットの論理番号。

        Raises:
            TypeError: 対応しない型(boolを含む)の場合。
            ValueError: ターゲットが無い場合、またはtargetがほかのノードや別のアトリビュートのPlugの場合。
        """
        if isinstance(target, str):
            index = self._target_lookup(target)
            if index is None:
                raise ValueError(f"{self.getName()}に{target!r}という名前のblendShapeのターゲットはありません")
            return index
        if isinstance(target, Plug):
            mplug = target.mplug()
            weight = self._mplug("weight")
            if target.getNode().mnode() != self.mnode() or not mplug.isElement or mplug.isChild or mplug.array() != weight:
                raise ValueError(f"Plug {target}は{self.getName()}のウェイトの要素ではありません")
            index = mplug.logicalIndex()
        elif type(target) is int:
            index = target
        else:
            raise TypeError(f"targetは名前か、番号か、ウェイトのPlugで指定してください: {type(target).__name__}")
        if index not in self._target_indices():
            raise ValueError(f"{self.getName()}に番号{index}のblendShapeのターゲットはありません")
        return index

    def _base_indices(self):
        """ベース(出力ジオメトリ)の論理番号を昇順で返す。

        Returns:
            list[int]: 論理番号。
        """
        fn = oma2.MFnGeometryFilter(self.mnode())
        return sorted(fn.indexForOutputShape(shape) for shape in fn.getOutputGeometry())

    def _base_index(self, base):
        """ベースの指定を論理番号にする。

        Args:
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。

        Returns:
            int: ベースの論理番号。

        Raises:
            TypeError: 対応しない型の場合。
            ValueError: ベースが無い、またはこのblendShapeのベースでない場合。
        """
        indices = self._base_indices()
        if not indices:
            raise ValueError(f"blendShape {self.getName()}にベースジオメトリがありません")
        if base is None:
            return indices[0]
        node = Node(Node._input_name(base))
        fn = oma2.MFnGeometryFilter(self.mnode())
        shapes = [node.mnode()]
        if node.mnode().hasFn(om2.MFn.kTransform):
            dag = om2.MFnDagNode(node.mpath())
            shapes = [dag.child(i) for i in range(dag.childCount()) if dag.child(i).hasFn(om2.MFn.kShape)]
        for bi in indices:
            if fn.outputShapeAtIndex(bi) in shapes:
                return bi
        raise ValueError(f"{node.getName()}は{self.getName()}のベースジオメトリではありません")

    def _base_shape(self, bi):
        """ベースの論理番号のメッシュを返す。

        Args:
            bi (int): ベースの論理番号。

        Returns:
            Node: ベースのメッシュ(Mesh)。

        Raises:
            TypeError: ベースがメッシュでない場合。
        """
        mobject = oma2.MFnGeometryFilter(self.mnode()).outputShapeAtIndex(bi)
        if not mobject.hasFn(om2.MFn.kMesh):
            raise TypeError(f"blendShapeのターゲットの編集には、ベースがポリゴンメッシュである必要があります: {self.getName()}")
        return Node(om2.MDagPath.getAPathTo(mobject))

    def _vertex_count(self, bi):
        """ベースの頂点数を返す。

        Args:
            bi (int): ベースの論理番号。

        Returns:
            int: 頂点数。

        Raises:
            TypeError: ベースがメッシュでない場合。
        """
        return om2.MFnMesh(self._base_shape(bi).mpath()).numVertices

    def _require_vertex_count(self, bi, shape):
        """形状の頂点数がベースと同じことを確かめる。

        Args:
            bi (int): ベースの論理番号。
            shape (Node): 比べるメッシュ。

        Raises:
            ValueError: 頂点数が違う場合。
        """
        count = self._vertex_count(bi)
        other = om2.MFnMesh(shape.mpath()).numVertices
        if other != count:
            raise ValueError(f"{shape.getName()}の頂点数は{other}ですが、ベースは{count}です")

    def _resolve_group(self, target, base):
        """ターゲットとベースを解決し、そのベースにターゲットの項目があることを確かめる。

        Args:
            target (str | int | Plug): ターゲットの指定。
            base (str | Node | None): ベースの指定。

        Returns:
            tuple[int, int]: ベースとターゲットの論理番号。

        Raises:
            ValueError: ターゲットがそのベースに項目を持たない場合。
        """
        index = self._target_index(target)
        bi = self._base_index(base)
        if not self._item_indices(bi, index):
            raise ValueError(f"ターゲット{index}には、{self.getName()}のベース{bi}のデータがありません")
        return bi, index

    def _resolve_item(self, target, base, weight):
        """ターゲット・ベース・項目のウェイトを解決し、項目が存在することを確かめる。

        Args:
            target (str | int | Plug): ターゲットの指定。
            base (str | Node | None): ベースの指定。
            weight (float): 項目のウェイト。

        Returns:
            tuple[int, int, int]: ベース・ターゲット・項目の論理番号。

        Raises:
            ValueError: その項目が無い場合。
        """
        bi, index = self._resolve_group(target, base)
        item = _weight_item(weight)
        if item not in self._item_indices(bi, index):
            raise ValueError(f"ターゲット{index}には、ベース{bi}にウェイト{weight}の項目がありません")
        return bi, index, item

    def _unused_index(self, reserved=()):
        """ウェイト・ターゲット・エイリアスのどれにも使われていない最小の論理番号を返す。

        Args:
            reserved (Iterable[int]): 追加で使用中とみなす番号。

        Returns:
            int: 空いている論理番号。
        """
        used = set(self._target_indices()) | set(self._existing("weight")) | set(reserved)
        index = 0
        while index in used:
            index += 1
        return index

    def _require_new_name(self, name):
        """新しいターゲット名が使えることを確かめる。

        Args:
            name (str): ターゲット名。

        Raises:
            TypeError: 文字列でない場合。
            ValueError: 空、または既存のアトリビュート・エイリアスと重なる場合。
        """
        if not isinstance(name, str):
            raise TypeError("nameは文字列かNoneで指定してください")
        if not name:
            raise ValueError("nameは空でない文字列かNoneで指定してください")
        if self.hasAttr(name):
            raise ValueError(f"{self.getName()}には{name!r}という名前のアトリビュートかターゲットがすでにあります")

    def _copy_name(self, source):
        """複製の既定の名前(``<元の名前>Copy``、重なれば末尾に番号)を返す。

        Args:
            source (str): 元のターゲット名。

        Returns:
            str: 使われていない名前。
        """
        name = f"{source}Copy"
        number = 1
        while self.hasAttr(name):
            name = f"{source}Copy{number}"
            number += 1
        return name

    def _mirror_axis_name(self, bi, index, axis):
        """ミラー・反転の条件を確かめ、Mayaのsymmetryの軸名を返す。

        Args:
            bi (int): ベースの論理番号。
            index (int): ターゲットの論理番号。
            axis (str | int): 軸の指定。

        Returns:
            str: ``"x"``・``"y"``・``"z"``。

        Raises:
            TypeError: ベースがメッシュでない、またはaxisの型が不正な場合。
            ValueError: axisが軸でない場合。
            RuntimeError: ターゲット形状が接続中の場合。
        """
        self._base_shape(bi)
        name = "xyz"[_mirror_axis(axis)]
        for item in self._item_indices(bi, index):
            if self._mplug(self._item_path(bi, index, item) + ".inputGeomTarget").isDestination:
                raise RuntimeError(f"ターゲット{index}はシェイプに接続されています。ミラーする前にベイクしてください")
        return name

    def _attr(self, path):
        """アトリビュートのパスに、ノードの一意な名前を付ける。

        Args:
            path (str): ノード名を含まないアトリビュートのパス。

        Returns:
            str: ``<ノード>.<パス>``。
        """
        return f"{self.getFullName()}.{path}"

    def _mplug(self, path):
        """アトリビュートのパスのMPlugを返す。

        Args:
            path (str): ノード名を含まないアトリビュートのパス。

        Returns:
            om2.MPlug: Plug。
        """
        selection = om2.MSelectionList()
        selection.add(self._attr(path))
        return selection.getPlug(0)

    def _existing(self, path):
        """マルチアトリビュートの既存の論理番号を、要素を作らずに昇順で返す。

        Args:
            path (str): マルチアトリビュートのパス。

        Returns:
            list[int]: 論理番号。
        """
        return sorted(self._mplug(path).getExistingArrayAttributeIndices())

    @staticmethod
    def _group_path(bi, index):
        """ターゲットのグループのパスを返す。

        Args:
            bi (int): ベースの論理番号。
            index (int): ターゲットの論理番号。

        Returns:
            str: ``inputTarget[bi].inputTargetGroup[index]``。
        """
        return f"inputTarget[{bi}].inputTargetGroup[{index}]"

    @classmethod
    def _item_path(cls, bi, index, item):
        """ターゲットの項目のパスを返す。

        Args:
            bi (int): ベースの論理番号。
            index (int): ターゲットの論理番号。
            item (int): 項目の論理番号。

        Returns:
            str: ``inputTarget[bi].inputTargetGroup[index].inputTargetItem[item]``。
        """
        return cls._group_path(bi, index) + f".inputTargetItem[{item}]"

    def _item_indices(self, bi, index):
        """ターゲットのそのベースの項目の論理番号を昇順で返す。

        Args:
            bi (int): ベースの論理番号。
            index (int): ターゲットの論理番号。

        Returns:
            list[int]: 項目の論理番号。グループが無ければ空。
        """
        if index not in self._existing(f"inputTarget[{bi}].inputTargetGroup"):
            return []
        return self._existing(self._group_path(bi, index) + ".inputTargetItem")

    def _read_deltas(self, path):
        """項目のデルタを読む。接続中ならMayaが評価した値。

        Args:
            path (str): 項目のパス。

        Returns:
            tuple[list[int], list[tuple[float, float, float]]]: 頂点番号と変位。

        Raises:
            RuntimeError: Mayaが返した頂点と変位の数が合わない場合。
        """
        points_object = typed_data(self._mplug(path + ".inputPointsTarget"))
        points = [] if points_object.isNull() else om2.MFnPointArrayData(points_object).array()
        components_object = typed_data(self._mplug(path + ".inputComponentsTarget"))
        indices = []
        if not components_object.isNull():
            components = om2.MFnComponentListData(components_object)
            for i in range(components.length()):
                fn = om2.MFnSingleIndexedComponent(components.get(i))
                indices.extend(range(fn.getCompleteData()) if fn.isComplete else fn.getElements())
        if len(indices) != len(points):
            raise RuntimeError(f"Mayaが{len(indices)}個の頂点に対して{len(points)}個のデルタを返しました: {self._attr(path)}")
        return indices, [(point.x, point.y, point.z) for point in points]

    def _write_deltas(self, path, indices, offsets, *, fast=False):
        """項目のデルタを書き、相対in-betweenの補助の値を消す(Mayaが再計算する)。

        通常は ``setAttr`` の2回(pointArray・componentList。連続する頂点は範囲にまとめる)で書く。

        Args:
            path (str): 項目のパス。
            indices (list[int]): 頂点番号(重複なし)。
            offsets (list[Sequence[float]]): 頂点番号と同じ数の変位。
            fast (bool): TrueはUndoなしのOpenMaya更新。
        """
        points = [(x, y, z, 1.0) for x, y, z in offsets]
        relative = self._mplug(path + ".inputRelativePointsTarget")
        clear_relative = not typed_data(relative).isNull()
        if fast:
            points_plug = self._mplug(path + ".inputPointsTarget")
            components_plug = self._mplug(path + ".inputComponentsTarget")
            require_writable(points_plug)
            require_writable(components_plug)
            component_list = om2.MFnComponentListData()
            components = component_list.create()
            if indices:
                fn = om2.MFnSingleIndexedComponent()
                component = fn.create(om2.MFn.kMeshVertComponent)
                fn.addElements(list(indices))
                component_list.add(component)
            points_plug.setMObject(om2.MFnPointArrayData().create(om2.MPointArray(points)))
            components_plug.setMObject(components)
            if clear_relative:
                relative.setMObject(om2.MFnPointArrayData().create())
                self._mplug(path + ".inputRelativeComponentsTarget").setMObject(om2.MFnComponentListData().create())
            return
        ranges = [f"vtx[{first}:{last}]" if first != last else f"vtx[{first}]" for first, last in _runs(indices)]
        cmds.setAttr(self._attr(path + ".inputPointsTarget"), len(points), *points, type="pointArray")
        cmds.setAttr(self._attr(path + ".inputComponentsTarget"), len(ranges), *ranges, type="componentList")
        if clear_relative:
            cmds.setAttr(self._attr(path + ".inputRelativePointsTarget"), 0, type="pointArray")
            cmds.setAttr(self._attr(path + ".inputRelativeComponentsTarget"), 0, type="componentList")

    def _release_input(self, path, disconnect, *, fast=False):
        """項目のターゲット形状の接続を、disconnect=Trueなら切り、Falseなら拒否する。

        Args:
            path (str): 項目のパス。
            disconnect (bool): 接続を切るか。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Raises:
            RuntimeError: 接続中でdisconnect=Falseの場合。
        """
        destination = self._mplug(path + ".inputGeomTarget")
        sources = destination.connectedTo(True, False)
        if not sources:
            return
        if not disconnect:
            raise RuntimeError(f"{self._attr(path)}はターゲットのシェイプに接続されています。ベイクするにはdisconnect=Trueを使います")
        if fast:
            modifier = om2.MDGModifier()
            modifier.disconnect(sources[0], destination)
            modifier.doIt()
        else:
            cmds.disconnectAttr(sources[0].name(), self._attr(path + ".inputGeomTarget"))

    def _remove_vertices(self, path, remove, disconnect, *, fast=False):
        """項目のデータから指定した頂点を取り除く。該当が無ければ何も変えない。

        Args:
            path (str): 項目のパス。
            remove (set[int]): 取り除く頂点番号。
            disconnect (bool): 接続中のターゲット形状を切るか。
            fast (bool): TrueはUndoなしのOpenMaya更新。
        """
        indices, offsets = self._read_deltas(path)
        if not remove.intersection(indices):
            return
        self._release_input(path, disconnect, fast=fast)
        kept = [(vertex, offset) for vertex, offset in zip(indices, offsets) if vertex not in remove]
        self._write_deltas(path, [row[0] for row in kept], [row[1] for row in kept], fast=fast)

    def _vertex_indices(self, vertices, bi):
        """頂点の指定を、ベースの範囲内の頂点番号にする。

        Args:
            vertices (int | Vertex | Vertices | Iterable[int | Vertex]): 頂点の指定。
            bi (int): ベースの論理番号。

        Returns:
            list[int]: 頂点番号。

        Raises:
            TypeError: 対応しない型の場合。
            ValueError: 別の形状の頂点の場合。
            IndexError: 範囲外の番号の場合。
        """
        shape = self._base_shape(bi)
        count = self._vertex_count(bi)
        if isinstance(vertices, Vertices):
            if vertices.shape.mnode() != shape.mnode():
                raise ValueError(f"頂点はベースメッシュ{shape.getName()}のものを指定してください")
            vertices = vertices.indices
        elif isinstance(vertices, (int, Vertex)) and not isinstance(vertices, bool):
            vertices = [vertices]
        elif isinstance(vertices, (str, bytes)):
            raise TypeError("verticesは頂点番号かmlibのVertexで指定してください")
        result = []
        for vertex in vertices:
            if isinstance(vertex, Vertex):
                if vertex.shape.mnode() != shape.mnode():
                    raise ValueError(f"頂点はベースメッシュ{shape.getName()}のものを指定してください")
                vertex = vertex.index
            if type(vertex) is not int:
                raise TypeError(f"vertexはintかVertexで指定してください: {type(vertex).__name__}")
            if not 0 <= vertex < count:
                raise IndexError(f"頂点番号が範囲外です: {vertex}")
            result.append(vertex)
        return result

    def _read_vertex_weights(self, path, count):
        """頂点ごとの値のマルチアトリビュートを、未設定を1.0として読む。

        Args:
            path (str): マルチアトリビュートのパス。
            count (int): 頂点数。

        Returns:
            list[float]: 頂点番号順の値。
        """
        plug = self._mplug(path)
        values = [1.0] * count
        for index in plug.getExistingArrayAttributeIndices():
            if index < count:
                values[index] = plug.elementByLogicalIndex(index).asFloat()
        return values

    def _write_vertex_weights(self, path, values, *, fast=False):
        """頂点ごとの値を書く。通常は連続する番号を範囲指定の1回のsetAttrにまとめる。

        Args:
            path (str): マルチアトリビュートのパス。
            values (dict[int, float]): 検証済みの頂点番号と値。
            fast (bool): TrueはUndoなしのOpenMaya更新。
        """
        if not values:
            return
        if fast:
            plug = self._mplug(path)
            # 要素ごとにMFnAttributeを作り直さず、同じアトリビュートの関数セットを使い回す。
            fn = om2.MFnAttribute(plug.attribute())
            edits = []
            for index, value in values.items():
                element = plug.elementByLogicalIndex(index)
                require_writable(element, fn)
                edits.append((element, value))
            for element, value in edits:
                element.setFloat(value)
            return
        indices = sorted(values)
        prefix = self._attr(path)
        for first, last in _runs(indices):
            if first == last:
                set_attr(f"{prefix}[{first}]", values[first])
            else:
                set_attr(f"{prefix}[{first}:{last}]", *[values[i] for i in range(first, last + 1)])

    def _capture_target(self, index, driver=False):
        """ターゲットの全ベースのデータを、JSONへ書ける辞書として取得する。

        Args:
            index (int): ターゲットの論理番号。
            driver (bool): Trueならウェイトの入力接続を記録する。

        Returns:
            dict: ``name``・``index``・``weight``・``driver``・``inBetweens``・``bases`` を持つ辞書。
        """
        weight_plug = self.getPlug("weight")[index]
        value = weight_plug.get() if index in self._existing("weight") else 0.0
        source = None
        if driver and index in self._existing("weight"):
            # 循環参照の回避: mlib.jsonはノード・Plugのクラスを使う。
            from ..json.plugRef import PlugRef

            plug = weight_plug.getSource(skipConversionNodes=True)
            source = None if plug is None else PlugRef.capture(plug).toData()
        bases = []
        for bi in self._base_indices():
            items = self._item_indices(bi, index)
            if not items:
                continue
            entries = []
            for item in items:
                indices, offsets = self._read_deltas(self._item_path(bi, index, item))
                entries.append(
                    {"weight": (item - _ITEM_OFFSET) / 1000.0, "indices": indices, "offsets": [component for offset in offsets for component in offset]}
                )
            weights = self._read_vertex_weights(self._group_path(bi, index) + ".targetWeights", self._vertex_count(bi))
            bases.append({"base": bi, "targetWeights": _sparse(weights), "items": entries})
        return {"name": self._alias_of(index), "index": index, "weight": value, "driver": source, "inBetweens": self._capture_inbetweens(index), "bases": bases}

    def _capture_inbetweens(self, index):
        """ターゲットのin-betweenの情報(``inbetweenInfoGroup``)を取得する。

        Args:
            index (int): ターゲットの論理番号。

        Returns:
            list[dict]: ``weight``・``relative``・``name``・``interpolation``・``visibility``・``curve`` の辞書。
        """
        if index not in self._existing("inbetweenInfoGroup"):
            return []
        result = []
        root = f"inbetweenInfoGroup[{index}].inbetweenInfo"
        for item in self._existing(root):
            path = f"{root}[{item}]"
            curve = []
            for point in self._existing(path + ".interpolationCurve"):
                element = self._mplug(f"{path}.interpolationCurve[{point}]")
                curve.append([element.child(0).asFloat(), element.child(1).asFloat()])
            result.append(
                {
                    "weight": (item - _ITEM_OFFSET) / 1000.0,
                    "relative": self._mplug(path + ".inbetweenTargetType").asInt() == 1,
                    "name": self._mplug(path + ".inbetweenTargetName").asString(),
                    "interpolation": self._mplug(path + ".interpolation").asInt(),
                    "visibility": self._mplug(path + ".inbetweenVisibility").asBool(),
                    "curve": curve,
                }
            )
        return result

    def _create_target(self, index, bases):
        """空のターゲットを論理番号へ作る(Shape Editorの空のターゲットの追加と同じ手順)。

        ベースを一時的に複製してターゲットとして追加し、複製を削除してからデルタを0にする。
        ウェイト・エイリアス・Shape Editorの所属はMayaの既定のまま。

        Args:
            index (int): 使われていない論理番号。
            bases (Iterable[int]): ターゲットを作るベースの論理番号。
        """
        for bi in bases:
            shape = self._base_shape(bi).getFullName()
            temporary = cmds.duplicate(shape, returnRootsOnly=True)
            try:
                cmds.blendShape(self.getFullName(), edit=True, target=(shape, index, temporary[0], 1.0))
            finally:
                cmds.delete(temporary)

    def _write_target(self, index, record, name, created=False):
        """取得したターゲットのデータ(:meth:`_capture_target` の形)をターゲットへ書く。

        デルタ・in-between・頂点マスク・エイリアスを書き、記録に無い項目は取り除く。
        ウェイトの値と接続は扱わない。Undoのまとまりは呼出し側が持つ。

        Args:
            index (int): 書込み先の論理番号。
            record (dict): ターゲットのデータ。
            name (str | None): ターゲット名。Noneはエイリアスを付けない。
            created (bool): Trueなら書く前に空のターゲットを作る。
        """
        if created:
            self._create_target(index, [entry["base"] for entry in record["bases"]])
        for entry in record["bases"]:
            bi = entry["base"]
            saved = {_weight_item(item["weight"]): item for item in entry["items"]}
            for item in self._item_indices(bi, index):
                if item not in saved:
                    cmds.removeMultiInstance(self._attr(self._item_path(bi, index, item)), b=True)
            for item, payload in saved.items():
                path = self._item_path(bi, index, item)
                if item in self._item_indices(bi, index):
                    self._release_input(path, True)
                offsets = payload["offsets"]
                self._write_deltas(path, payload["indices"], [offsets[i : i + 3] for i in range(0, len(offsets), 3)])
            weights = _dense(entry["targetWeights"], self._vertex_count(bi))
            self._write_vertex_weights(self._group_path(bi, index) + ".targetWeights", dict(enumerate(weights)))
        self._write_inbetweens(index, record["inBetweens"])
        current = self._alias_of(index)
        if current != name:
            if current is not None:
                cmds.aliasAttr(self._attr(current), remove=True)
            if name is not None:
                cmds.aliasAttr(name, self._attr(f"weight[{index}]"))

    def _write_inbetweens(self, index, inbetweens):
        """in-betweenの情報を書き、記録に無いものを取り除く。

        Args:
            index (int): ターゲットの論理番号。
            inbetweens (list[dict]): :meth:`_capture_inbetweens` の形の情報。
        """
        root = f"inbetweenInfoGroup[{index}].inbetweenInfo"
        saved = {_weight_item(entry["weight"]): entry for entry in inbetweens}
        if index in self._existing("inbetweenInfoGroup"):
            for item in self._existing(root):
                if item not in saved:
                    cmds.removeMultiInstance(self._attr(f"{root}[{item}]"), b=True)
        for item, entry in saved.items():
            path = self._attr(f"{root}[{item}]")
            cmds.setAttr(path + ".inbetweenTargetType", 1 if entry["relative"] else 0)
            cmds.setAttr(path + ".inbetweenTargetName", entry["name"], type="string")
            cmds.setAttr(path + ".interpolation", entry["interpolation"])
            cmds.setAttr(path + ".inbetweenVisibility", entry["visibility"])
            for number, (position, value) in enumerate(entry["curve"]):
                cmds.setAttr(f"{path}.interpolationCurve[{number}]", position, value)

    def _plan_targets(self, data, mapping, report):
        """復元するデータを検査し、書込み先の論理番号とドライバーを決める。シーンは変えない。

        Args:
            data (dict): :meth:`getTargetsData` の形の辞書。
            mapping (NameMapping): ドライバーの名前の対応付け。
            report (ValidationReport): 問題の記録先。

        Returns:
            list[tuple[dict, int, bool, Plug | None]]: ターゲットのデータ・書込み先の番号・
                新しく作るか・ドライバーのPlug。
        """
        # 循環参照の回避: mlib.jsonはノード・Plugのクラスを使う。
        from ..json.plugRef import PlugRef

        bases, targets = data.get("bases"), data.get("targets")
        if not isinstance(bases, list) or not isinstance(targets, list) or not isinstance(data.get("folders"), list):
            raise ValueError("blendShapeのターゲットのデータには'bases'・'targets'・'folders'のリストが必要です")
        counts = {}
        current = set(self._base_indices())
        for entry in bases:
            bi = _data_index(entry.get("index") if isinstance(entry, dict) else None, "ベースの番号")
            if bi not in current:
                report.addError(f"{self.getName()}にベース{bi}はありません")
                continue
            count = self._vertex_count(bi)
            if entry.get("vertexCount") != count:
                report.addError(f"ベース{bi}の頂点数は{count}ですが、データは{entry.get('vertexCount')}です")
                continue
            counts[bi] = count
            _require_sparse(entry.get("baseWeights"), count)
        names = {}
        plan = []
        reserved = set()
        for target in targets:
            record = _validated_target(target, counts, report)
            if record is None:
                continue
            name = record["name"]
            index = None
            if name is not None:
                if name in names:
                    raise ValueError(f"データのターゲット名が重複しています: {name!r}")
                names[name] = True
                index = self._target_lookup(name)
                if index is None and self.hasAttr(name):
                    report.addError(f"{self.getName()}には{name!r}という名前の、ターゲットではないアトリビュートがすでにあります")
                    continue
            created = index is None
            if created:
                saved = record["index"]
                used = set(self._target_indices()) | set(self._existing("weight")) | reserved
                index = saved if saved not in used else self._unused_index(reserved)
            reserved.add(index)
            driver = None
            if record["driver"] is not None:
                reference = PlugRef.fromData(record["driver"])
                driver = reference.resolve(mapping)
                if driver is None:
                    report.addMissing(reference.mappedName(mapping))
            plan.append((record, index, created, driver))
        return plan

    def _apply_targets(self, data, plan, report):
        """検査済みの計画どおりにターゲットを書く。Undoのまとまりは呼出し側が持つ。

        Args:
            data (dict): :meth:`getTargetsData` の形の辞書。
            plan (list): :meth:`_plan_targets` の結果。
            report (ValidationReport): 飛ばしたものの記録先。
        """
        for entry in data["bases"]:
            count = self._vertex_count(entry["index"])
            weights = _dense(entry["baseWeights"], count)
            self._write_vertex_weights(f"inputTarget[{entry['index']}].baseWeights", dict(enumerate(weights)))
        index_map = {}
        for record, index, created, driver in plan:
            index_map[record["index"]] = index
            self._write_target(index, record, record["name"], created=created)
            weight = self.getPlug("weight")[index]
            label = record["name"] or f"weight[{index}]"
            if weight.isLocked():
                report.addSkipped(label, "locked")
            elif driver is not None:
                cmds.connectAttr(str(driver), str(weight), force=True)
            elif weight.isDestination():
                report.addSkipped(label, "connected")
            else:
                weight.set(record["weight"])
        model = _Directories.read(self)
        model.restore(data["folders"], index_map)
        model.write(self)


class _Directories:
    """Shape Editorのフォルダ(``targetDirectory``・``parentDirectory``)を読み書きする内部の補助。

    ``targetDirectory[d]`` はフォルダ(0は最上位)で、``childIndices`` に子の並びを持つ(0以上はターゲットの
    論理番号、負の値は ``-<フォルダの番号>``)。``parentDirectory[i]`` はターゲットの所属フォルダ。
    読んだ内容を変更してから :meth:`write` で変わったものだけをcmdsで書く。
    """

    def __init__(self, folders, parents):
        """読んだ内容を保持する。

        Args:
            folders (dict[int, dict]): フォルダの番号と ``name``・``parent``・``children``・``weight``・``visibility``。
            parents (dict[int, int]): ターゲットの論理番号と所属フォルダ。
        """
        self._folders = folders
        self._parents = parents
        self._original = ({key: dict(value, children=list(value["children"])) for key, value in folders.items()}, dict(parents))

    @classmethod
    def read(cls, node):
        """blendShapeのフォルダを読む。

        Args:
            node (BlendShape): 対象のblendShape。

        Returns:
            _Directories: 読んだ内容。
        """
        folders = {}
        for d in node._existing("targetDirectory"):
            path = f"targetDirectory[{d}]"
            data = typed_data(node._mplug(path + ".childIndices"))
            children = [] if data.isNull() else list(om2.MFnIntArrayData(data).array())
            folders[d] = {
                "name": node._mplug(path + ".directoryName").asString(),
                "parent": node._mplug(path + ".parentIndex").asInt(),
                "children": children,
                "weight": node._mplug(path + ".directoryWeight").asDouble(),
                "visibility": node._mplug(path + ".directoryVisibility").asBool(),
            }
        parents = {index: node._mplug(f"parentDirectory[{index}]").asInt() for index in node._existing("parentDirectory")}
        return cls(folders, parents)

    def parentOf(self, index):
        """ターゲットの所属フォルダを返す。

        Args:
            index (int): ターゲットの論理番号。

        Returns:
            int: フォルダの番号。不明なら0(最上位)。
        """
        parent = self._parents.get(index, 0)
        return parent if parent in self._folders else 0

    def move(self, index, folder, after=None):
        """ターゲットをフォルダへ移す。

        Args:
            index (int): ターゲットの論理番号。
            folder (int): 移動先のフォルダの番号。
            after (int | None): このターゲットの直後に置く。Noneは末尾。
        """
        self._ensure_root()
        for value in self._folders.values():
            if index in value["children"]:
                value["children"].remove(index)
        children = self._folders[folder]["children"]
        position = children.index(after) + 1 if after in children else len(children)
        children.insert(position, index)
        self._parents[index] = folder

    def toData(self, targets):
        """最上位からのフォルダの木を、JSONへ書けるlistにする。

        Args:
            targets (Iterable[int]): 書き出すターゲットの論理番号。

        Returns:
            list[dict]: 最上位の子の並び。``{"target": 番号}`` または
                ``{"folder": 名前, "weight": ..., "visibility": ..., "children": [...]}``。
        """
        wanted = set(targets)

        def visit(folder, seen):
            entries = []
            for child in self._folders.get(folder, {}).get("children", []):
                if child >= 0:
                    if child in wanted:
                        entries.append({"target": child})
                elif -child in self._folders and -child not in seen:
                    value = self._folders[-child]
                    entries.append(
                        {"folder": value["name"], "weight": value["weight"], "visibility": value["visibility"], "children": visit(-child, seen | {-child})}
                    )
            return entries

        return visit(0, {0})

    def restore(self, entries, index_map):
        """保存したフォルダの木に合わせて、復元したターゲットを配置する。

        フォルダは親と名前で既存のものを使い、無ければ作る。各フォルダの子の並びは、保存した順を先頭に、
        保存に無い既存の子をその後に置く。

        Args:
            entries (list[dict]): :meth:`toData` の形の木。
            index_map (dict[int, int]): 保存時のターゲットの番号と、復元先の番号。
        """
        self._ensure_root()
        self._place(entries, 0, index_map)

    def write(self, node):
        """変わった値だけを ``cmds.setAttr`` で書く。

        Args:
            node (BlendShape): 対象のblendShape。
        """
        folders, parents = self._original
        for d, value in sorted(self._folders.items()):
            before = folders.get(d)
            path = node._attr(f"targetDirectory[{d}]")
            if before is None or before["children"] != value["children"]:
                cmds.setAttr(path + ".childIndices", value["children"], type="Int32Array")
            if before is None or before["name"] != value["name"]:
                cmds.setAttr(path + ".directoryName", value["name"], type="string")
            if before is None or before["parent"] != value["parent"]:
                cmds.setAttr(path + ".parentIndex", value["parent"])
            if before is None or before["weight"] != value["weight"]:
                cmds.setAttr(path + ".directoryWeight", value["weight"])
            if before is None or before["visibility"] != value["visibility"]:
                cmds.setAttr(path + ".directoryVisibility", value["visibility"])
        for index, parent in sorted(self._parents.items()):
            if parents.get(index) != parent:
                cmds.setAttr(node._attr(f"parentDirectory[{index}]"), parent)

    def _place(self, entries, folder, index_map):
        """木の1階層をフォルダへ配置する。

        Args:
            entries (list[dict]): 子の並び。
            folder (int): 配置先のフォルダの番号。
            index_map (dict[int, int]): 保存時と復元先のターゲットの番号。
        """
        ordered = []
        for entry in entries:
            if "target" in entry:
                index = index_map.get(entry["target"])
                if index is None:
                    continue
                self.move(index, folder)
                ordered.append(index)
                continue
            child = next(
                (
                    -c
                    for c in self._folders[folder]["children"]
                    if c < 0 and -c in self._folders and self._folders[-c]["name"] == entry["folder"] and -c not in ordered
                ),
                None,
            )
            if child is None:
                child = self._new_folder(folder, entry["folder"])
            self._folders[child]["weight"] = float(entry.get("weight", 1.0))
            self._folders[child]["visibility"] = bool(entry.get("visibility", True))
            ordered.append(-child)
            self._place(entry.get("children", []), child, index_map)
        children = self._folders[folder]["children"]
        self._folders[folder]["children"] = ordered + [child for child in children if child not in ordered]

    def _new_folder(self, parent, name):
        """空のフォルダを作る(Mayaの ``blendShapeUnusedTargetDirectoryIndex`` と同じ番号の選び方)。

        Args:
            parent (int): 親フォルダの番号。
            name (str): フォルダ名。

        Returns:
            int: 作ったフォルダの番号。
        """
        number = 0
        while number in self._folders:
            number += 1
        self._folders[number] = {"name": name, "parent": parent, "children": [], "weight": 1.0, "visibility": True}
        self._folders[parent]["children"].append(-number)
        return number

    def _ensure_root(self):
        """最上位のフォルダ(0)が無ければ作る。"""
        if 0 not in self._folders:
            self._folders[0] = {"name": "Group", "parent": 0, "children": [], "weight": 1.0, "visibility": True}


def _weight_item(weight):
    """項目のウェイトを ``inputTargetItem`` の論理番号(``5000 + weight * 1000``)にする。

    Args:
        weight (float): 項目のウェイト。-5以上、0.001刻み。

    Returns:
        int: 論理番号。

    Raises:
        TypeError: 数値でない(boolを含む)場合。
        ValueError: 有限でない、範囲外、または0.001刻みで表せない場合。
    """
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise TypeError(f"weightは数値で指定してください: {type(weight).__name__}")
    if not math.isfinite(weight):
        raise ValueError(f"weightは有限な数値で指定してください: {weight}")
    scaled = weight * 1000.0 + _ITEM_OFFSET
    if scaled < 0 or scaled > _MAX_INDEX or abs(scaled - round(scaled)) > 1e-6:
        raise ValueError(f"weightは-5以上で、0.001の倍数で指定してください: {weight}")
    return int(round(scaled))


def _mesh_shape(value):
    """形状またはtransformを、中間オブジェクトでない1つのメッシュにする。

    Args:
        value (str | Node): メッシュまたはそのtransform。

    Returns:
        Node: メッシュ。

    Raises:
        TypeError: メッシュでない場合。
        ValueError: transformに中間オブジェクトでないメッシュが1つでない場合。
    """
    node = Node(Node._input_name(value))
    path = node.mpath()
    if node.mnode().hasFn(om2.MFn.kTransform):
        dag = om2.MFnDagNode(path)
        shapes = [dag.child(i) for i in range(dag.childCount()) if dag.child(i).hasFn(om2.MFn.kMesh) and not om2.MFnDagNode(dag.child(i)).isIntermediateObject]
        if len(shapes) != 1:
            raise ValueError(f"{node.getName()}にはメッシュのシェイプが1つだけ必要です")
        path.push(shapes[0])
        node = Node(path)
    if not node.mnode().hasFn(om2.MFn.kMesh):
        raise TypeError(f"{node.getName()}はポリゴンメッシュではありません")
    return node


def _runs(indices):
    """昇順の番号を、1ずつ増える区間の ``(最初, 最後)`` に分ける。

    Args:
        indices (Sequence[int]): 昇順の番号。

    Returns:
        list[tuple[int, int]]: 区間。
    """
    runs = []
    for index in indices:
        if runs and index == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], index)
        else:
            runs.append((index, index))
    return runs


def _vertex_values(weights, count):
    """頂点ごとの値の指定を、検証済みの辞書にする。

    Args:
        weights (Sequence[float] | dict[int, float]): 全頂点の並び、または頂点番号と値。
        count (int): 頂点数。

    Returns:
        dict[int, float]: 頂点番号と値。

    Raises:
        TypeError: 型が不正な場合。
        ValueError: 並びの長さが違う、または値が有限でない場合。
        IndexError: 頂点番号が範囲外の場合。
    """
    if isinstance(weights, dict):
        items = list(weights.items())
    elif isinstance(weights, (str, bytes)):
        raise TypeError("weightsは数値の並びかdictで指定してください")
    else:
        items = list(enumerate(weights))
        if len(items) != count:
            raise ValueError(f"ウェイトを{count}個指定してください: {len(items)}個")
    values = {}
    for index, value in items:
        if type(index) is not int:
            raise TypeError(f"頂点番号はintで指定してください: {type(index).__name__}")
        if not 0 <= index < count:
            raise IndexError(f"頂点番号が範囲外です: {index}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"weightは数値で指定してください: {type(value).__name__}")
        if not math.isfinite(value):
            raise ValueError(f"weightは有限な数値で指定してください: {value}")
        values[index] = float(value)
    return values


def _delta_values(deltas, count):
    """デルタの指定を、頂点番号の昇順の ``(番号, (x, y, z))`` にする。

    Args:
        deltas (dict[int, Sequence[float]]): 頂点番号と変位。
        count (int): 頂点数。

    Returns:
        list[tuple[int, tuple[float, float, float]]]: 検証済みの変位。

    Raises:
        TypeError: 辞書でない、番号がintでない、または変位が数値の並びでない場合。
        ValueError: 変位が3個の有限な数値でない場合。
        IndexError: 頂点番号が範囲外の場合。
    """
    if not isinstance(deltas, dict):
        raise TypeError("deltasは頂点番号からオフセットへのdictで指定してください")
    rows = []
    for index, delta in sorted(deltas.items()):
        if type(index) is not int:
            raise TypeError(f"頂点番号はintで指定してください: {type(index).__name__}")
        if not 0 <= index < count:
            raise IndexError(f"頂点番号が範囲外です: {index}")
        try:
            offset = tuple(delta)
        except TypeError:
            raise TypeError(f"deltaは3つの数値で指定してください: {type(delta).__name__}") from None
        if len(offset) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in offset):
            raise ValueError(f"deltaは3つの数値で指定してください: {delta!r}")
        if not all(math.isfinite(v) for v in offset):
            raise ValueError(f"deltaは有限な数値で指定してください: {delta!r}")
        rows.append((index, tuple(float(v) for v in offset)))
    return rows


def _tolerance(value):
    """しきい値を検証する。

    Args:
        value (float): 0以上の有限な数値。

    Returns:
        float: しきい値。

    Raises:
        TypeError: 数値でない場合。
        ValueError: 負または有限でない場合。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"toleranceは数値で指定してください: {type(value).__name__}")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"toleranceは0以上の有限な数値で指定してください: {value}")
    return float(value)


def _sparse(values):
    """頂点ごとの値から、既定値1.0でないものだけを取り出す。

    Args:
        values (list[float]): 頂点番号順の値。

    Returns:
        dict: ``{"indices": [...], "values": [...]}``。
    """
    pairs = [(index, value) for index, value in enumerate(values) if value != 1.0]
    return {"indices": [pair[0] for pair in pairs], "values": [pair[1] for pair in pairs]}


def _dense(sparse, count):
    """:func:`_sparse` の形を、全頂点の値の並びに戻す。

    Args:
        sparse (dict): ``{"indices": [...], "values": [...]}``。
        count (int): 頂点数。

    Returns:
        list[float]: 頂点番号順の値。
    """
    values = [1.0] * count
    for index, value in zip(sparse["indices"], sparse["values"]):
        values[index] = float(value)
    return values


def _data_index(value, label):
    """データの論理番号を検証する。

    Args:
        value (object): 値。
        label (str): メッセージに使う名前。

    Returns:
        int: 論理番号。

    Raises:
        ValueError: 0以上の論理番号でない場合。
    """
    if type(value) is not int or not 0 <= value <= _MAX_INDEX:
        raise ValueError(f"blendShapeのターゲットのデータの{label}が不正です: {value!r}")
    return value


def _require_sparse(value, count):
    """:func:`_sparse` の形と頂点番号の範囲を検証する。

    Args:
        value (object): 検証する値。
        count (int): 頂点数。

    Raises:
        ValueError: 形・番号・値が不正な場合。
    """
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("indices"), list)
        or not isinstance(value.get("values"), list)
        or len(value["indices"]) != len(value["values"])
    ):
        raise ValueError("blendShapeのターゲットのデータの頂点ウェイトには、'indices'と'values'のリストが必要です")
    for index, weight in zip(value["indices"], value["values"]):
        if type(index) is not int or not 0 <= index < count:
            raise ValueError(f"blendShapeのターゲットのデータの頂点番号が範囲外です: {index!r}")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
            raise ValueError(f"blendShapeのターゲットのデータの頂点ウェイトが不正です: {weight!r}")


def _validated_target(target, counts, report):
    """1つのターゲットのデータを検証する。

    ベースが見つからない・頂点数が違うものはreportへ記録する(ベースの検査で記録済み)。

    Args:
        target (object): ターゲットのデータ。
        counts (dict[int, int]): 検査に通ったベースの論理番号と頂点数。
        report (ValidationReport): 問題の記録先。

    Returns:
        dict | None: 検証済みのデータ。ベースの問題で使えなければNone。

    Raises:
        ValueError: データの形が違う場合。
    """
    if not isinstance(target, dict):
        raise ValueError(f"blendShapeのターゲットのデータのターゲットが不正です: {target!r}")
    name = target.get("name")
    if name is not None and (not isinstance(name, str) or not name):
        raise ValueError(f"blendShapeのターゲットのデータのターゲット名が不正です: {name!r}")
    _data_index(target.get("index"), "ターゲットの番号")
    value = target.get("weight")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"ターゲット{name!r}のウェイトの値が不正です: {value!r}")
    if target.get("driver") is not None and not isinstance(target["driver"], dict):
        raise ValueError(f"ターゲット{name!r}のドライバーが不正です")
    inbetweens = target.get("inBetweens")
    if not isinstance(inbetweens, list):
        raise ValueError(f"ターゲット{name!r}のインビトウィーンが不正です")
    for entry in inbetweens:
        if (
            not isinstance(entry, dict)
            or type(entry.get("relative")) is not bool
            or not isinstance(entry.get("name"), str)
            or type(entry.get("interpolation")) is not int
            or type(entry.get("visibility")) is not bool
            or not isinstance(entry.get("curve"), list)
        ):
            raise ValueError(f"ターゲット{name!r}のインビトウィーンが不正です: {entry!r}")
        _weight_item(entry.get("weight"))
    bases = target.get("bases")
    if not isinstance(bases, list) or not bases:
        raise ValueError(f"ターゲット{name!r}にベースのデータがありません")
    usable = True
    for entry in bases:
        if not isinstance(entry, dict) or not isinstance(entry.get("items"), list) or not entry["items"]:
            raise ValueError(f"ターゲット{name!r}のベースのデータが不正です")
        bi = _data_index(entry.get("base"), "ベースの番号")
        if bi not in counts:
            usable = False
            if not report.errors:
                report.addError(f"ターゲット{name!r}が使うベース{bi}は復元できません")
            continue
        _require_sparse(entry.get("targetWeights"), counts[bi])
        for item in entry["items"]:
            if not isinstance(item, dict):
                raise ValueError(f"ターゲット{name!r}の項目が不正です")
            _weight_item(item.get("weight"))
            indices, offsets = item.get("indices"), item.get("offsets")
            if not isinstance(indices, list) or not isinstance(offsets, list) or len(offsets) != 3 * len(indices) or len(set(indices)) != len(indices):
                raise ValueError(f"ターゲット{name!r}のデルタが不正です")
            if any(type(i) is not int or not 0 <= i < counts[bi] for i in indices):
                raise ValueError(f"ターゲット{name!r}のデルタの頂点番号が範囲外です")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in offsets):
                raise ValueError(f"ターゲット{name!r}のデルタの値が不正です")
    return target if usable else None
