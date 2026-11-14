# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
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
from typing import Any, Iterable, Sequence
from mlib.json.nameMapping import NameMapping
from mlib.json.snapshot import ValidationReport
import os
import pathlib

_WEIGHT_ALIAS: Any
_ITEM_OFFSET: int
_FULL_ITEM: int
_MAX_INDEX: int
_TARGETS_FORMAT: str
_TARGETS_VERSION: int
_TARGETS_MODES: tuple


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
    def __contains__(self, name: str) -> bool:
        """ターゲット名(ウェイトのエイリアス)があるかを返す。

        Args:
            name (str): ターゲット名。

        Returns:
            bool: ターゲットがあればTrue。

        Raises:
            TypeError: nameが文字列以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def getTargetNames(self) -> list[str]:
        """ターゲット名を、論理番号の順に取得する。

        Returns:
            list[str]: ウェイトのエイリアス。エイリアスの無いウェイトの要素は含まない。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def getTargetIndex(self, target: str | int | Plug) -> int:
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
        ...
    def getWeightPlug(self, target: str | int | Plug) -> Plug:
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
        ...
    def getBaseGeometry(self) -> list[Node]:
        """変形する形状(出力ジオメトリ)を取得する。

        Returns:
            list[Node]: 変形される形状。geometryFilterの出力の順に並ぶ。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def addTarget(self, mesh: str | Node, name: str | None = ...) -> Plug:
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
        ...
    def removeTarget(self, target: str | int | Plug) -> BlendShape:
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
        ...
    def getInBetweenWeights(self, target: str | int | Plug, base: str | Node | None = ...) -> list[float]:
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
        ...
    def addInBetween(self, target: str | int | Plug, geometry: str | Node, weight: float, base: str | Node | None = ..., relative: bool = ...) -> BlendShape:
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
        ...
    def removeInBetween(self, target: str | int | Plug, weight: float) -> BlendShape:
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
        ...
    def getTargetWeights(self, target: str | int | Plug, base: str | Node | None = ...) -> list[float]:
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
        ...
    def setTargetWeights(self, target: str | int | Plug, weights: Sequence[float] | dict[int, float], base: str | Node | None = ..., *, fast: bool = ...) -> BlendShape:
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
        ...
    def getTargetDeltas(self, target: str | int | Plug, base: str | Node | None = ..., fullWeight: float = ...) -> dict[int, Vector]:
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
        ...
    def setTargetDeltas(self, target: str | int | Plug, deltas: dict[int, Sequence[float]], base: str | Node | None = ..., fullWeight: float = ..., disconnect: bool = ..., *, fast: bool = ...) -> BlendShape:
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
        ...
    def getTargetVertices(self, target: str | int | Plug, base: str | Node | None = ..., fullWeight: float = ..., *, tolerance: float = ...) -> Vertices:
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
        ...
    def resetTargetVertices(self, target: str | int | Plug, vertices: int | Vertex | Vertices | Iterable[int | Vertex], base: str | Node | None = ..., fullWeight: float = ..., disconnect: bool = ..., *, fast: bool = ...) -> BlendShape:
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
        ...
    def reduceTargetDeltas(self, target: str | int | Plug, tolerance: float = ..., base: str | Node | None = ..., fullWeight: float = ..., disconnect: bool = ..., *, fast: bool = ...) -> BlendShape:
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
        ...
    def mirrorTarget(self, target: str | int | Plug, axis: str | int = ..., positiveToNegative: bool = ..., base: str | Node | None = ...) -> BlendShape:
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
        ...
    def flipTarget(self, target: str | int | Plug, axis: str | int = ..., base: str | Node | None = ...) -> BlendShape:
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
        ...
    def duplicateTarget(self, target: str | int | Plug, name: str | None = ...) -> Plug:
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
        ...
    def replaceTarget(self, target: str | int | Plug, geometry: str | Node, base: str | Node | None = ..., fullWeight: float = ...) -> BlendShape:
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
        ...
    def targetEdit(self, target: str | int | Plug | None = ..., state: bool = ..., fullWeight: float = ...) -> BlendShape:
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
        ...
    def getTargetsData(self) -> dict:
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
        ...
    def setTargetsData(self, data: dict, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ..., mode: str = ...) -> ValidationReport:
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
        ...
    def exportTargets(self, path: str | os.PathLike) -> pathlib.Path:
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
        ...
    def importTargets(self, path: str | os.PathLike, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ..., mode: str = ...) -> ValidationReport:
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
        ...
    def _target_items(self) -> list[tuple[int, str]]:
        """エイリアスのあるウェイト要素を ``(論理番号, 名前)`` の並びで返す。

        Returns:
            list[tuple[int, str]]: OpenMayaのエイリアス一覧から得た対応。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def _target_lookup(self, name: str) -> int | None:
        """ターゲット名の論理番号を返す。無ければNone。

        Args:
            name (str): ターゲット名。

        Returns:
            int | None: 論理番号。

        Raises:
            TypeError: nameが文字列以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def _alias_of(self, index: int) -> str | None:
        """論理番号のウェイトのエイリアスを返す。無ければNone。

        Args:
            index (int): ウェイトの論理番号。

        Returns:
            str | None: エイリアス。
        """
        ...
    def _target_indices(self) -> list[int]:
        """ターゲットの論理番号を昇順で返す。

        エイリアスのあるウェイト要素と、いずれかのベースに項目(``inputTargetItem``)を持つ番号の和集合。

        Returns:
            list[int]: 論理番号。
        """
        ...
    def _target_index(self, target: str | int | Plug) -> int:
        """ターゲットの指定を論理番号にする。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。

        Returns:
            int: 存在するターゲットの論理番号。

        Raises:
            TypeError: 対応しない型(boolを含む)の場合。
            ValueError: ターゲットが無い場合、またはtargetがほかのノードや別のアトリビュートのPlugの場合。
        """
        ...
    def _base_indices(self) -> list[int]:
        """ベース(出力ジオメトリ)の論理番号を昇順で返す。

        Returns:
            list[int]: 論理番号。
        """
        ...
    def _base_index(self, base: str | Node | None) -> int:
        """ベースの指定を論理番号にする。

        Args:
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。

        Returns:
            int: ベースの論理番号。

        Raises:
            TypeError: 対応しない型の場合。
            ValueError: ベースが無い、またはこのblendShapeのベースでない場合。
        """
        ...
    def _base_shape(self, bi: int) -> Node:
        """ベースの論理番号のメッシュを返す。

        Args:
            bi (int): ベースの論理番号。

        Returns:
            Node: ベースのメッシュ(Mesh)。

        Raises:
            TypeError: ベースがメッシュでない場合。
        """
        ...
    def _vertex_count(self, bi: int) -> int:
        """ベースの頂点数を返す。

        Args:
            bi (int): ベースの論理番号。

        Returns:
            int: 頂点数。

        Raises:
            TypeError: ベースがメッシュでない場合。
        """
        ...
    def _require_vertex_count(self, bi: int, shape: Node):
        """形状の頂点数がベースと同じことを確かめる。

        Args:
            bi (int): ベースの論理番号。
            shape (Node): 比べるメッシュ。

        Raises:
            ValueError: 頂点数が違う場合。
        """
        ...
    def _resolve_group(self, target: str | int | Plug, base: str | Node | None) -> tuple[int, int]:
        """ターゲットとベースを解決し、そのベースにターゲットの項目があることを確かめる。

        Args:
            target (str | int | Plug): ターゲットの指定。
            base (str | Node | None): ベースの指定。

        Returns:
            tuple[int, int]: ベースとターゲットの論理番号。

        Raises:
            ValueError: ターゲットがそのベースに項目を持たない場合。
        """
        ...
    def _resolve_item(self, target: str | int | Plug, base: str | Node | None, weight: float) -> tuple[int, int, int]:
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
        ...
    def _unused_index(self, reserved: Iterable[int] = ...) -> int:
        """ウェイト・ターゲット・エイリアスのどれにも使われていない最小の論理番号を返す。

        Args:
            reserved (Iterable[int]): 追加で使用中とみなす番号。

        Returns:
            int: 空いている論理番号。
        """
        ...
    def _require_new_name(self, name: str):
        """新しいターゲット名が使えることを確かめる。

        Args:
            name (str): ターゲット名。

        Raises:
            TypeError: 文字列でない場合。
            ValueError: 空、または既存のアトリビュート・エイリアスと重なる場合。
        """
        ...
    def _copy_name(self, source: str) -> str:
        """複製の既定の名前(``<元の名前>Copy``、重なれば末尾に番号)を返す。

        Args:
            source (str): 元のターゲット名。

        Returns:
            str: 使われていない名前。
        """
        ...
    def _mirror_axis_name(self, bi: int, index: int, axis: str | int) -> str:
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
        ...
    def _attr(self, path: str) -> str:
        """アトリビュートのパスに、ノードの一意な名前を付ける。

        Args:
            path (str): ノード名を含まないアトリビュートのパス。

        Returns:
            str: ``<ノード>.<パス>``。
        """
        ...
    def _mplug(self, path: str) -> om2.MPlug:
        """アトリビュートのパスのMPlugを返す。

        Args:
            path (str): ノード名を含まないアトリビュートのパス。

        Returns:
            om2.MPlug: Plug。
        """
        ...
    def _existing(self, path: str) -> list[int]:
        """マルチアトリビュートの既存の論理番号を、要素を作らずに昇順で返す。

        Args:
            path (str): マルチアトリビュートのパス。

        Returns:
            list[int]: 論理番号。
        """
        ...
    @staticmethod
    def _group_path(bi: int, index: int) -> str:
        """ターゲットのグループのパスを返す。

        Args:
            bi (int): ベースの論理番号。
            index (int): ターゲットの論理番号。

        Returns:
            str: ``inputTarget[bi].inputTargetGroup[index]``。
        """
        ...
    @classmethod
    def _item_path(cls, bi: int, index: int, item: int) -> str:
        """ターゲットの項目のパスを返す。

        Args:
            bi (int): ベースの論理番号。
            index (int): ターゲットの論理番号。
            item (int): 項目の論理番号。

        Returns:
            str: ``inputTarget[bi].inputTargetGroup[index].inputTargetItem[item]``。
        """
        ...
    def _item_indices(self, bi: int, index: int) -> list[int]:
        """ターゲットのそのベースの項目の論理番号を昇順で返す。

        Args:
            bi (int): ベースの論理番号。
            index (int): ターゲットの論理番号。

        Returns:
            list[int]: 項目の論理番号。グループが無ければ空。
        """
        ...
    def _read_deltas(self, path: str) -> tuple[list[int], list[tuple[float, float, float]]]:
        """項目のデルタを読む。接続中ならMayaが評価した値。

        Args:
            path (str): 項目のパス。

        Returns:
            tuple[list[int], list[tuple[float, float, float]]]: 頂点番号と変位。

        Raises:
            RuntimeError: Mayaが返した頂点と変位の数が合わない場合。
        """
        ...
    def _write_deltas(self, path: str, indices: list[int], offsets: list[Sequence[float]], *, fast: bool = ...):
        """項目のデルタを書き、相対in-betweenの補助の値を消す(Mayaが再計算する)。

        通常は ``setAttr`` の2回(pointArray・componentList。連続する頂点は範囲にまとめる)で書く。

        Args:
            path (str): 項目のパス。
            indices (list[int]): 頂点番号(重複なし)。
            offsets (list[Sequence[float]]): 頂点番号と同じ数の変位。
            fast (bool): TrueはUndoなしのOpenMaya更新。
        """
        ...
    def _release_input(self, path: str, disconnect: bool, *, fast: bool = ...):
        """項目のターゲット形状の接続を、disconnect=Trueなら切り、Falseなら拒否する。

        Args:
            path (str): 項目のパス。
            disconnect (bool): 接続を切るか。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Raises:
            RuntimeError: 接続中でdisconnect=Falseの場合。
        """
        ...
    def _remove_vertices(self, path: str, remove: set[int], disconnect: bool, *, fast: bool = ...):
        """項目のデータから指定した頂点を取り除く。該当が無ければ何も変えない。

        Args:
            path (str): 項目のパス。
            remove (set[int]): 取り除く頂点番号。
            disconnect (bool): 接続中のターゲット形状を切るか。
            fast (bool): TrueはUndoなしのOpenMaya更新。
        """
        ...
    def _vertex_indices(self, vertices: int | Vertex | Vertices | Iterable[int | Vertex], bi: int) -> list[int]:
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
        ...
    def _read_vertex_weights(self, path: str, count: int) -> list[float]:
        """頂点ごとの値のマルチアトリビュートを、未設定を1.0として読む。

        Args:
            path (str): マルチアトリビュートのパス。
            count (int): 頂点数。

        Returns:
            list[float]: 頂点番号順の値。
        """
        ...
    def _write_vertex_weights(self, path: str, values: dict[int, float], *, fast: bool = ...):
        """頂点ごとの値を書く。通常は連続する番号を範囲指定の1回のsetAttrにまとめる。

        Args:
            path (str): マルチアトリビュートのパス。
            values (dict[int, float]): 検証済みの頂点番号と値。
            fast (bool): TrueはUndoなしのOpenMaya更新。
        """
        ...
    def _capture_target(self, index: int, driver: bool = ...) -> dict:
        """ターゲットの全ベースのデータを、JSONへ書ける辞書として取得する。

        Args:
            index (int): ターゲットの論理番号。
            driver (bool): Trueならウェイトの入力接続を記録する。

        Returns:
            dict: ``name``・``index``・``weight``・``driver``・``inBetweens``・``bases`` を持つ辞書。
        """
        ...
    def _capture_inbetweens(self, index: int) -> list[dict]:
        """ターゲットのin-betweenの情報(``inbetweenInfoGroup``)を取得する。

        Args:
            index (int): ターゲットの論理番号。

        Returns:
            list[dict]: ``weight``・``relative``・``name``・``interpolation``・``visibility``・``curve`` の辞書。
        """
        ...
    def _create_target(self, index: int, bases: Iterable[int]):
        """空のターゲットを論理番号へ作る(Shape Editorの空のターゲットの追加と同じ手順)。

        ベースを一時的に複製してターゲットとして追加し、複製を削除してからデルタを0にする。
        ウェイト・エイリアス・Shape Editorの所属はMayaの既定のまま。

        Args:
            index (int): 使われていない論理番号。
            bases (Iterable[int]): ターゲットを作るベースの論理番号。
        """
        ...
    def _write_target(self, index: int, record: dict, name: str | None, created: bool = ...):
        """取得したターゲットのデータ(:meth:`_capture_target` の形)をターゲットへ書く。

        デルタ・in-between・頂点マスク・エイリアスを書き、記録に無い項目は取り除く。
        ウェイトの値と接続は扱わない。Undoのまとまりは呼出し側が持つ。

        Args:
            index (int): 書込み先の論理番号。
            record (dict): ターゲットのデータ。
            name (str | None): ターゲット名。Noneはエイリアスを付けない。
            created (bool): Trueなら書く前に空のターゲットを作る。
        """
        ...
    def _write_inbetweens(self, index: int, inbetweens: list[dict]):
        """in-betweenの情報を書き、記録に無いものを取り除く。

        Args:
            index (int): ターゲットの論理番号。
            inbetweens (list[dict]): :meth:`_capture_inbetweens` の形の情報。
        """
        ...
    def _plan_targets(self, data: dict, mapping: NameMapping, report: ValidationReport) -> list[tuple[dict, int, bool, Plug | None]]:
        """復元するデータを検査し、書込み先の論理番号とドライバーを決める。シーンは変えない。

        Args:
            data (dict): :meth:`getTargetsData` の形の辞書。
            mapping (NameMapping): ドライバーの名前の対応付け。
            report (ValidationReport): 問題の記録先。

        Returns:
            list[tuple[dict, int, bool, Plug | None]]: ターゲットのデータ・書込み先の番号・
                新しく作るか・ドライバーのPlug。
        """
        ...
    def _apply_targets(self, data: dict, plan: list, report: ValidationReport):
        """検査済みの計画どおりにターゲットを書く。Undoのまとまりは呼出し側が持つ。

        Args:
            data (dict): :meth:`getTargetsData` の形の辞書。
            plan (list): :meth:`_plan_targets` の結果。
            report (ValidationReport): 飛ばしたものの記録先。
        """
        ...


class _Directories:
    """Shape Editorのフォルダ(``targetDirectory``・``parentDirectory``)を読み書きする内部の補助。

    ``targetDirectory[d]`` はフォルダ(0は最上位)で、``childIndices`` に子の並びを持つ(0以上はターゲットの
    論理番号、負の値は ``-<フォルダの番号>``)。``parentDirectory[i]`` はターゲットの所属フォルダ。
    読んだ内容を変更してから :meth:`write` で変わったものだけをcmdsで書く。
    """
    def __init__(self, folders: dict[int, dict], parents: dict[int, int]) -> None:
        """読んだ内容を保持する。

        Args:
            folders (dict[int, dict]): フォルダの番号と ``name``・``parent``・``children``・``weight``・``visibility``。
            parents (dict[int, int]): ターゲットの論理番号と所属フォルダ。
        """
        ...
    @classmethod
    def read(cls, node: BlendShape) -> _Directories:
        """blendShapeのフォルダを読む。

        Args:
            node (BlendShape): 対象のblendShape。

        Returns:
            _Directories: 読んだ内容。
        """
        ...
    def parentOf(self, index: int) -> int:
        """ターゲットの所属フォルダを返す。

        Args:
            index (int): ターゲットの論理番号。

        Returns:
            int: フォルダの番号。不明なら0(最上位)。
        """
        ...
    def move(self, index: int, folder: int, after: int | None = ...):
        """ターゲットをフォルダへ移す。

        Args:
            index (int): ターゲットの論理番号。
            folder (int): 移動先のフォルダの番号。
            after (int | None): このターゲットの直後に置く。Noneは末尾。
        """
        ...
    def toData(self, targets: Iterable[int]) -> list[dict]:
        """最上位からのフォルダの木を、JSONへ書けるlistにする。

        Args:
            targets (Iterable[int]): 書き出すターゲットの論理番号。

        Returns:
            list[dict]: 最上位の子の並び。``{"target": 番号}`` または
                ``{"folder": 名前, "weight": ..., "visibility": ..., "children": [...]}``。
        """
        ...
    def restore(self, entries: list[dict], index_map: dict[int, int]):
        """保存したフォルダの木に合わせて、復元したターゲットを配置する。

        フォルダは親と名前で既存のものを使い、無ければ作る。各フォルダの子の並びは、保存した順を先頭に、
        保存に無い既存の子をその後に置く。

        Args:
            entries (list[dict]): :meth:`toData` の形の木。
            index_map (dict[int, int]): 保存時のターゲットの番号と、復元先の番号。
        """
        ...
    def write(self, node: BlendShape):
        """変わった値だけを ``cmds.setAttr`` で書く。

        Args:
            node (BlendShape): 対象のblendShape。
        """
        ...
    def _place(self, entries: list[dict], folder: int, index_map: dict[int, int]):
        """木の1階層をフォルダへ配置する。

        Args:
            entries (list[dict]): 子の並び。
            folder (int): 配置先のフォルダの番号。
            index_map (dict[int, int]): 保存時と復元先のターゲットの番号。
        """
        ...
    def _new_folder(self, parent: int, name: str) -> int:
        """空のフォルダを作る(Mayaの ``blendShapeUnusedTargetDirectoryIndex`` と同じ番号の選び方)。

        Args:
            parent (int): 親フォルダの番号。
            name (str): フォルダ名。

        Returns:
            int: 作ったフォルダの番号。
        """
        ...
    def _ensure_root(self):
        """最上位のフォルダ(0)が無ければ作る。"""
        ...

def _weight_item(weight: float) -> int:
    """項目のウェイトを ``inputTargetItem`` の論理番号(``5000 + weight * 1000``)にする。

    Args:
        weight (float): 項目のウェイト。-5以上、0.001刻み。

    Returns:
        int: 論理番号。

    Raises:
        TypeError: 数値でない(boolを含む)場合。
        ValueError: 有限でない、範囲外、または0.001刻みで表せない場合。
    """
    ...

def _mesh_shape(value: str | Node) -> Node:
    """形状またはtransformを、中間オブジェクトでない1つのメッシュにする。

    Args:
        value (str | Node): メッシュまたはそのtransform。

    Returns:
        Node: メッシュ。

    Raises:
        TypeError: メッシュでない場合。
        ValueError: transformに中間オブジェクトでないメッシュが1つでない場合。
    """
    ...

def _runs(indices: Sequence[int]) -> list[tuple[int, int]]:
    """昇順の番号を、1ずつ増える区間の ``(最初, 最後)`` に分ける。

    Args:
        indices (Sequence[int]): 昇順の番号。

    Returns:
        list[tuple[int, int]]: 区間。
    """
    ...

def _vertex_values(weights: Sequence[float] | dict[int, float], count: int) -> dict[int, float]:
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
    ...

def _delta_values(deltas: dict[int, Sequence[float]], count: int) -> list[tuple[int, tuple[float, float, float]]]:
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
    ...

def _tolerance(value: float) -> float:
    """しきい値を検証する。

    Args:
        value (float): 0以上の有限な数値。

    Returns:
        float: しきい値。

    Raises:
        TypeError: 数値でない場合。
        ValueError: 負または有限でない場合。
    """
    ...

def _sparse(values: list[float]) -> dict:
    """頂点ごとの値から、既定値1.0でないものだけを取り出す。

    Args:
        values (list[float]): 頂点番号順の値。

    Returns:
        dict: ``{"indices": [...], "values": [...]}``。
    """
    ...

def _dense(sparse: dict, count: int) -> list[float]:
    """:func:`_sparse` の形を、全頂点の値の並びに戻す。

    Args:
        sparse (dict): ``{"indices": [...], "values": [...]}``。
        count (int): 頂点数。

    Returns:
        list[float]: 頂点番号順の値。
    """
    ...

def _data_index(value: object, label: str) -> int:
    """データの論理番号を検証する。

    Args:
        value (object): 値。
        label (str): メッセージに使う名前。

    Returns:
        int: 論理番号。

    Raises:
        ValueError: 0以上の論理番号でない場合。
    """
    ...

def _require_sparse(value: object, count: int):
    """:func:`_sparse` の形と頂点番号の範囲を検証する。

    Args:
        value (object): 検証する値。
        count (int): 頂点数。

    Raises:
        ValueError: 形・番号・値が不正な場合。
    """
    ...

def _validated_target(target: object, counts: dict[int, int], report: ValidationReport) -> dict | None:
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
    ...
