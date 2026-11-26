# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の blendShape デフォーマを扱う。"""

import math
import re
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
import maya.mel as mel
from ..components.edge import Edge
from ..components.vertex import Vertex, Vertices
from ..core.attributeType import typed_data
from ..core.fastWrite import require_writable, set_attr
from ..core.nodeEdit import require_editable
from ..decorator import _edit_context, _require_bool, undoChunk
from ..maths.vector import Vector
from ..plugs.plug import Plug
from ..util import _UNSET, _mirror_axis
from .geometryFilter import GeometryFilter
from .node import Node, Nodes
from typing import Any, Iterable, Sequence
from mlib.json.nameMapping import NameMapping
from mlib.json.snapshot import ValidationReport
from mlib.nodes.mesh import Mesh
import os
import pathlib

_WEIGHT_ALIAS: Any
_ITEM_OFFSET: int
_FULL_ITEM: int
_MAX_INDEX: int
_TARGETS_FORMAT: str
_TARGETS_VERSION: int
_TARGETS_MODES: tuple
_ATTRIBUTE_NAME: Any


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
    本体とin-betweenの項目は ``fullWeight`` (項目が完全に効くウェイト)で選ぶ。
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
    def getWeightCount(self) -> int:
        """Mayaが保持するターゲットウェイトの数を取得する。

        blendShapeコマンドのweightCountを返す。疎な論理番号や事前確保によって、ターゲット項目数とは異なる。

        Returns:
            int: Mayaのウェイト数。
        """
        ...
    def getNormalizationGroups(self) -> list[int]:
        """使用されている正規化グループの番号を取得する。

        Returns:
            list[int]: Mayaが返す順のグループ番号。未使用なら空。
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
    def getBaseGeometry(self) -> Nodes:
        """変形する形状(出力ジオメトリ)を取得する。

        Returns:
            Nodes: 変形される形状。geometryFilterの出力の順に並ぶ。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def addBaseGeometry(self, geometry: str | Node) -> None:
        """既存のblendShapeへ変形対象のベース形状を追加する。

        ヒストリへの配置はcmds.blendShape(edit=True, geometry=...)に従う。
        既存ターゲットの別ベースへの複製は行わない。追加後はaddTargetのbaseで指定する。
        fast引数は持たない(ヒストリと所属の更新をcmdsへ任せるため)。Undoが有効なら1回で戻せる。

        Args:
            geometry (str | Node): 追加する形状、またはそのTransform。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: geometryの型が不正な場合。
            ValueError: geometryが無効な場合、変形できる形状(deformableShape)でもそれを持つTransformでもない場合、
                またはすでにベースとして登録されている場合。
            RuntimeError: ノードが無効な場合、blendShapeがロックされているかリファレンスの場合
                (Mayaはロックを見ずに追加するため、追加する前に確かめる)、またはMayaが追加を拒否した場合。
        """
        ...
    def addTarget(self, mesh: str | Node, name: str | None = ..., *, base: str | Node | None = ..., index: int | None = ..., fullWeight: float = ..., inBetween: str | int | Plug | None = ..., relative: bool = ...) -> Plug:
        """指定したベースへターゲット形状を追加する。``inBetween`` を渡すと、すでにあるターゲットへin-betweenを追加する。

        ターゲットの追加(既定):

        - 省略時はgetBaseGeometryの先頭へ、空いている次の番号・fullWeight=1.0で追加する。
        - 別のベースで使用中のindexを指定すると、同じweight要素とエイリアスを共有する。同じベースの既存番号への追加は拒否する。

        in-betweenの追加(``inBetween=ターゲット``):

        - ``cmds.blendShape(edit=True, inBetween=True)`` と同じ処理をする。``fullWeight`` が、in-betweenが完全に効くウェイトになる
          (0と1以外の、-5以上で0.001刻みの値。省略できない)。
        - ``name``・``index`` は指定できない。

        形状との接続はMayaの既定どおり残す。Undoが有効なら1回で戻せる。
        fast引数は持たない(デフォーマーの接続とターゲット登録をcmdsで更新するため)。

        Args:
            mesh (str | Node): ターゲット(in-between)の形状、またはそのTransform。in-betweenはベースと頂点数が同じメッシュ。
            name (str | None): ターゲット名。新しい番号ではNoneならMayaの既定名。共有番号では既存名だけを指定できる。
            base (str | Node | None): 登録済みのベース形状かそのTransform。Noneなら先頭のベース
                (in-betweenでは論理番号がいちばん小さいベース)。
            index (int | None): weightの論理番号。Noneなら未使用の番号。boolは不可。
            fullWeight (float): 完全に変形するウェイト。ターゲットでは0より大きい0.001刻みの値。現在のweight値は変更しない。
            inBetween (str | int | Plug | None): in-betweenの追加先のターゲット。ターゲット名・論理番号、
                またはこのノードの ``weight`` の要素のPlug。Noneならターゲットを追加する。既定はNone。
            relative (bool): Trueならターゲット本体からの相対、Falseなら絶対(Mayaの既定)のin-betweenにする。既定はFalse。
                ``inBetween`` を渡したときだけ指定できる。

        Returns:
            Plug: 追加したターゲット(in-betweenでは追加先のターゲット)のウェイト(``weight[i]``)。

        Raises:
            TypeError: name・index・fullWeight・形状の型が不正な場合(形状の無いTransformを含む)、relativeがbool以外の場合、
                in-betweenの形状がメッシュでない場合、inBetweenとname・indexを同時に指定した場合、
                またはinBetweenを渡さずにrelative=Trueを指定した場合。
            ValueError: 名前・番号・ウェイトが不正(アトリビュートの名前に使えない文字・すでにあるアトリビュートと同じ名前を含む)、
                ベースが未登録、同じベースの番号が使用中の場合。
                in-betweenでは、ターゲットが無い場合、fullWeightが0か1・すでにある項目・範囲外・0.001刻みでない場合、
                または頂点数がベースと違う場合。
            RuntimeError: ノードが無効な場合、ベースが無い場合、またはMayaが追加を拒否した場合。
        """
        ...
    def removeTarget(self, target: str | int | Plug, *, inBetween: float | None = ...) -> None:
        """ターゲットを完全に取り除く。``inBetween`` にウェイトを渡すと、そのウェイトのin-betweenだけを取り除く。

        ターゲット形状がすでに削除されていてもよい。
        既定では ``cmds.blendShape(edit=True, remove=True, target=...)`` と同じく、次のものを取り除く
        (Maya標準の ``blendShapeDeleteTargetGroup`` を使う)。

        - ウェイトの要素とエイリアス
        - すべてのベースの ``inputTarget[].inputTargetGroup[i]``
        - Shape Editorでどこに入っているかの情報

        ウェイトへの入力の接続は外し、ウェイトを動かしているcombinationShapeノードはMayaの決まりどおり削除する。
        ターゲット形状のノードは削除しない。

        ``inBetween`` を渡したときは、そのウェイトのin-betweenをすべてのベースから取り除く
        (Maya標準の ``blendShapeDeleteInBetweenTarget`` を使う)。ターゲット本体は残す。

        Undoが有効なら、1回のUndoで戻せる。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            inBetween (float | None): 取り除くin-betweenのウェイト。1.0は指定できない。Noneならターゲットを取り除く。既定はNone。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: targetが使えない型(boolを含む)の場合、またはinBetweenが数値でない場合。
            ValueError: ターゲットが無い場合、またはそのウェイトのin-betweenが無い場合。
            RuntimeError: ノードが無効な場合、ウェイトがロックされている場合(ターゲットを取り除くとき)、
                またはMayaが取り除くのを拒否した場合。
        """
        ...
    def getInBetweenWeights(self, target: str | int | Plug, base: str | Node | None = ...) -> list[float]:
        """ターゲットのin-betweenの項目のウェイトを取得する。

        ``inputTargetItem`` の論理番号から `` (番号 - 5000) / 1000`` で求め、1.0は除く。
        今の ``weight`` の値は見ない。addTargetでfullWeightを1.0以外にした本体の項目も含む。

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
    def getTargetItemIndices(self, target: str | int | Plug, base: str | Node | None = ...) -> list[int]:
        """ターゲット本体とin-betweenの項目の論理番号を取得する。

        未作成要素は作らず、値も評価しない。番号は5000 + ウェイト * 1000に対応する。

        Args:
            target (str | int | Plug): ターゲットの別名、ウェイトの論理番号、またはPlug。
            base (str | Node | None): ベース形状。Noneは先頭のベース。

        Returns:
            list[int]: 項目の論理番号の昇順。ターゲット本体も含む。

        Raises:
            TypeError: target・baseが使えない型(boolを含む)の場合。
            ValueError: ターゲットまたはベースが存在しない場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def getTargetGeometry(self, target: str | int | Plug, base: str | Node | None = ...) -> dict[int, Node | None]:
        """ターゲットの各項目へ接続された元形状を取得する。

        保存済みデルタだけを持ち、元Shapeへの接続がない項目はNone。
        形状の再生成や評価は要求しない。

        Args:
            target (str | int | Plug): ターゲットの別名、ウェイトの論理番号、またはPlug。
            base (str | Node | None): ベース形状。Noneは先頭のベース。

        Returns:
            dict[int, Node | None]: 項目の論理番号から接続元ノードへの対応。

        Raises:
            TypeError: target・baseが使えない型(boolを含む)の場合。
            ValueError: ターゲットまたはベースが存在しない場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def getTargetWeights(self, target: str | int | Plug | None = ..., base: str | Node | None = ...) -> list[float]:
        """ターゲットの頂点マスクを、頂点番号の順に取得する。``target=None`` なら、ベースのbaseWeightsを取得する。

        - ターゲット: 頂点マスクは ``inputTargetGroup[i].targetWeights`` の値。
        - ベース(``target=None``): ``inputTarget[].baseWeights`` の値。ターゲットに共通するマスクを保持する。
          Maya 2022〜2024では変形へ作用する。Maya 2025〜2027の標準blendShapeでは、変形に使われるのは
          weightListのウェイトで、baseWeightsだけを変更しても変形へ反映されない。
          weightListを読む場合はgetDeformerWeightsを使う。

        値が書かれていない頂点は、Mayaの既定どおり1.0として返す。アトリビュートの要素は作らない。

        Args:
            target (str | int | Plug | None): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
                Noneならベースのウェイト。既定はNone。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。

        Returns:
            list[float]: ベースの頂点数と同じ長さの新しいlist。

        Raises:
            TypeError: target・baseが使えない型の場合、またはベースがメッシュでない場合。
            ValueError: ターゲットが無い場合、ベースが無い場合、baseがこのblendShapeのベースでない場合、
                またはターゲットがそのベースのデータを持たない場合。
        """
        ...
    def setTargetWeights(self, target: str | int | Plug | None, weights: Sequence[float] | dict[int, float], base: str | Node | None = ..., *, fast: bool = ..., check: bool = ...) -> None:
        """ターゲットの頂点マスクを設定する。``target`` にNoneを渡すと、ベースのbaseWeightsを設定する。

        ターゲットの頂点マスクは ``inputTargetGroup[i].targetWeights``、ベースは ``inputTarget[].baseWeights`` の値。
        値は0〜1に制限しない。互いのウェイトとweightListは変更しない。
        baseWeightsのMaya版による変形への作用の違いは :meth:`getTargetWeights` を参照。

        - 並び(list等)を渡すと、頂点番号の順にすべての頂点を書き換える。
        - 辞書を渡すと、指定した頂点だけを書き換える。

        通常は、番号が1ずつ続く頂点を範囲指定の1回の ``setAttr`` にまとめ、全体を1回のUndoにする。
        ベースのウェイトを複数回に分けて書く場合は、checkにかかわらず全対象のロックと接続を先に確かめる。

        Args:
            target (str | int | Plug | None): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
                Noneならベースのウェイト。
            weights (Sequence[float] | dict[int, float]): 頂点数と同じ数の値、または頂点番号から値への辞書。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。ベースのウェイトでは、有限な値かも確かめる。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: target・base・値の型が不正な場合、fast・checkがbool以外の場合、またはベースがメッシュでない場合。
            ValueError: ターゲットが無い場合、ベースが無い場合、並びの長さが頂点数と違う場合、または有限でない値がある場合。
            IndexError: 頂点番号が範囲外の場合。
            RuntimeError: ノードがロック・リファレンスの場合(ベースのウェイト)、アトリビュートがロックされているか
                入力が接続されている場合、またはMayaが書き込みを拒否した場合。
        """
        ...
    def getTargetDeltas(self, target: str | int | Plug, base: str | Node | None = ..., *, fullWeight: float = ...) -> dict[int, Vector]:
        """ターゲット(またはin-between)の項目に保存されたデルタを取得する。

        ターゲット形状が接続されていれば、Mayaが計算した今のデルタを返す。
        値はベースのオブジェクト空間での変位(cm)で、変位を持つ頂点だけを含む。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。既定1.0。addTargetで別のfullWeightを指定した本体にも、その値を指定する。

        Returns:
            dict[int, Vector]: 頂点番号から変位への辞書。

        Raises:
            TypeError: target・baseの型が不正な場合、またはfullWeightが数値でない場合。
            ValueError: ターゲット、またはそのウェイトの項目が無い場合。
        """
        ...
    def setTargetDeltas(self, target: str | int | Plug, deltas: dict[int, Sequence[float]], base: str | Node | None = ..., *, fullWeight: float = ..., disconnect: bool = ..., fast: bool = ..., check: bool = ...) -> None:
        """ターゲット(またはin-between)の項目のデルタを、まるごと置き換える。

        指定しなかった頂点は変位0になる。ほかの項目のデルタは変えない。
        ターゲット形状が接続されている場合、既定では何も変えずにエラーにする
        (接続から計算し直されて上書きされてしまうため)。``disconnect=True`` なら接続を外してから書き込む。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            deltas (dict[int, Sequence[float]]): 頂点番号から変位(xyz、cm)への辞書。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。既定1.0。addTargetで別のfullWeightを指定した本体にも、その値を指定する。
            disconnect (bool): Trueなら、ターゲット形状の接続を外してから書き込む。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 引数の型が不正な場合、disconnect・fast・checkがbool以外の場合、またはベースがメッシュでない場合。
            ValueError: ターゲットや項目が無い場合、または変位が3つの有限な数値でない場合。
            IndexError: 頂点番号が範囲外の場合。
            RuntimeError: ターゲット形状が接続されていてdisconnect=Falseの場合、またはMayaが書き込みを拒否した場合。
        """
        ...
    def getTargetVertices(self, target: str | int | Plug, base: str | Node | None = ..., *, fullWeight: float = ..., tolerance: float = ...) -> Vertices:
        """デルタの長さがしきい値を超える頂点を取得する。

        今の ``weight``・envelope・頂点マスクは判定に使わない。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。既定1.0。addTargetで別のfullWeightを指定した本体にも、その値を指定する。
            tolerance (float): この長さ(cm)以下の変位の頂点を除く。0以上の有限な数値。既定は0で、変位0の頂点だけを除く。

        Returns:
            Vertices: ベースの頂点。番号の小さい順に並ぶ。

        Raises:
            TypeError: 引数の型が不正な場合、またはベースがメッシュでない場合。
            ValueError: ターゲットや項目が無い場合、またはtoleranceが負の数か有限でない場合。
        """
        ...
    def resetTargetVertices(self, target: str | int | Plug, vertices: int | Vertex | Vertices | Iterable[int | Vertex] | None = ..., base: str | Node | None = ..., *, fullWeight: float = ..., disconnect: bool = ..., tolerance: float | None = ..., fast: bool = ..., check: bool = ...) -> None:
        """指定した頂点の変位を0に戻す。``tolerance`` を渡すと、デルタの長さがしきい値以下の頂点を項目のデータから取り除く。

        ``vertices`` と ``tolerance`` のどちらか1つを指定する。

        - ``vertices``: 指定した頂点の変位を0に戻す。変位を持たない頂点だけを指定した場合は、何も変えない。
        - ``tolerance``: その長さ(cm)以下の変位の頂点を取り除く。保存するデータが減る。0なら、変位0の頂点だけを取り除くので
          変形の結果は変わらない。正の値を指定すると、その長さ以下の小さな変位は0になるため、変形の結果もわずかに変わる。

        ほかの頂点の変位はそのまま残す。ターゲット形状が接続されている場合の扱いは :meth:`setTargetDeltas` と同じ。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            vertices (int | Vertex | Vertices | Iterable[int | Vertex] | None): ベースの頂点、または頂点番号。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。既定1.0。addTargetで別のfullWeightを指定した本体にも、その値を指定する。
            disconnect (bool): Trueなら、ターゲット形状の接続を外してから書き込む。既定はFalse。
            tolerance (float | None): この長さ(cm)以下の変位を取り除く。0以上の有限な数値。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 引数の型が不正な場合(fast・check・disconnectがbool以外を含む)、verticesとtoleranceを両方指定したか、どちらも指定しない場合、
                またはverticesの指定でベースがメッシュでない場合(toleranceの指定では、ベースはメッシュ以外のカーブなどでもよい)。
            ValueError: ターゲットや項目が無い場合、頂点が別の形状のものの場合、またはtoleranceが負の数か有限でない場合。
            IndexError: 頂点番号が範囲外の場合。
            RuntimeError: ターゲット形状が接続されていてdisconnect=Falseの場合、またはMayaが書き込みを拒否した場合。
        """
        ...
    def mirrorTarget(self, target: str | int | Plug, axis: str | int = ..., positiveToNegative: bool = ..., base: str | Node | None = ..., *, flip: bool = ..., symmetrySpace: str = ..., symmetryEdge: str | Edge | None = ...) -> None:
        """ターゲットの片側の変形を、反対側へミラーする。``flip=True`` なら、ターゲットの変形を左右反転する。

        ``cmds.blendShape(edit=True, mirrorTarget=...)``(``flip=True`` では ``flipTarget=...``)を使う。
        既定では対称の頂点をオブジェクト空間の座標で探す。
        topology指定では基準エッジから対応を求め、基準エッジ情報もノードに保存する。
        ターゲットと基準エッジ設定は1回のUndoで戻せる。
        Mayaの対称編集キャッシュ(topoSymmetrySet)の作成・破棄はUndoでは復元されない。
        左右で別々のターゲットを作るなら、ターゲットを複製してから反転する。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            axis (str | int): 反転する軸。既定は ``"x"``。``"x"``・``"y"``・``"z"`` (大文字・小文字は問わない)、
                ミラー面の ``"YZ"`` など、または0〜2で指定する。
            positiveToNegative (bool): Trueなら正の側を負の側へ、Falseなら負の側を正の側へ写す。既定はTrue。
                ``flip=True`` では指定できない。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            flip (bool): Trueなら、片側を写すのでなく、左右を入れ替える。既定はFalse。
            symmetrySpace (str): object(既定)またはtopology。UV基準は未対応。
            symmetryEdge (str | Edge | None): topologyで必須の、ベース上の対称中心エッジ。Shape名は階層なしで一意であること。objectでは指定しない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 引数の型が不正な場合、ベースがメッシュでない場合、またはflip=TrueとpositiveToNegativeを同時に指定した場合。
            ValueError: ターゲットが無い場合、またはaxisが軸として使えない場合。
            RuntimeError: ターゲット形状が接続されている場合(先に複製するなどして、接続の無い形状にしておく)。
        """
        ...
    def replaceTarget(self, target: str | int | Plug, geometry: str | Node, base: str | Node | None = ..., *, fullWeight: float = ...) -> None:
        """ターゲット(またはin-between)の項目の形状を、別のメッシュに差し替える。

        別のメッシュを接続し、以後のデルタはそのメッシュから計算されるようにする。
        ターゲット名・ウェイトの値と接続・頂点マスクはそのまま残る。Undoが有効なら、1回のUndoで戻せる。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードの ``weight`` の要素のPlug。
            geometry (str | Node): 新しいターゲット形状。ベースと頂点数が同じメッシュ(かそのTransform)。
            base (str | Node | None): ベースの形状、またはそのTransform。Noneなら論理番号がいちばん小さいベースを使う。
            fullWeight (float): 項目のウェイト。既定1.0。addTargetで別のfullWeightを指定した本体にも、その値を指定する。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 引数の型が不正な場合、またはgeometryかベースがメッシュでない場合。
            ValueError: ターゲットや項目が無い場合、または頂点数がベースと違う場合。
            RuntimeError: Mayaが接続を拒否した場合。
        """
        ...
    def regenerateTarget(self, target: str | int | Plug, *, fullWeight: float = ...) -> Nodes[Mesh]:
        """保存済みターゲットから、全ベースの編集用メッシュを再生成する。

        sculptTarget(regenerate=True)で、形状の接続が無い項目にメッシュとTransformを作り、
        inputGeomTargetへ接続する。接続済みのメッシュは作り直さず、そのまま返す。
        全ベースに作用するため、ベースを1つだけ選ぶ指定はない。全ベースに同じターゲットと項目が必要。
        選択とターゲットの編集モードは維持する。新規生成は1回のUndoで戻せる。

        本体のfullWeightが1.0の通常ターゲットと、0〜1の間のin-betweenに対応する。1より大きい項目を持つターゲットは扱わない。
        タンジェント空間・Transform空間ターゲットは変更前に拒否する。
        fast引数は持たない(OpenMayaに同等の生成操作がないため)。

        Args:
            target (str | int | Plug): ターゲット名・論理番号、またはこのノードのweightの要素。
            fullWeight (float): 再生成する項目のウェイト。0.001刻み、既定1.0。全対象ベースに同じ項目が必要。

        Returns:
            Nodes[Mesh]: ベースの論理番号順のメッシュ。新規生成と接続済みの両方を含む。
                接続元がインスタンスの場合、接続に使ったインスタンスのDAGパスは保持しない。

        Raises:
            TypeError: target・fullWeightの型が不正、またはベースがメッシュでない場合。
            ValueError: ターゲットか指定項目が無い、またはfullWeightが不正な場合。
            RuntimeError: ノードがロック・リファレンス、生成先にロックがある、またはMayaが生成を拒否した場合。
            NotImplementedError: fullWeightが0以下か1より大きい、本体1.0が無い、1を超える項目がある、ポストデフォーメーションターゲット、
                または既存の接続元がメッシュでない場合。
        """
        ...
    def targetEdit(self, target: str | int | Plug | None = ..., state: bool = ..., *, fullWeight: float = ...) -> None:
        """ターゲットの編集モード(Shape EditorのEdit)を始める、または終える。

        ``cmds.sculptTarget`` を使う。編集モードの間は、ベースをスカルプトした結果がターゲットのデルタへ書き込まれる。
        Undoが有効なら、1回のUndoで戻せる。

        すでに同じターゲット・同じ項目を編集しているときに始めると、何もしない(編集を続ける)。

        Args:
            target (str | int | Plug | None): 編集を始めるターゲット。始めるときは必ず指定する。
                終えるときは使わない(渡したときは、型とターゲットがあるかだけを確かめる)。
            state (bool): Trueなら編集を始め、FalseならこのblendShapeの編集モードを終える。既定はTrue。
            fullWeight (float): 編集する項目のウェイト。既定1.0。addTargetで別のfullWeightを指定した本体にも、その値を指定する。
                終えるときは使わない(値は確かめる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: targetの型が不正な場合、stateがbool以外の場合、またはfullWeightが数値でない場合。
            ValueError: 始めるときにtargetが無い場合、ターゲットや項目が無い場合、またはfullWeightが有限でない・0.001刻みでない場合。
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
        Undoの状態に関係なく書き込む。Undoが有効なら全体を1回のUndoにまとめ、途中で失敗したら元に戻す
        (Undoが無効なときは、途中で失敗しても、それまでに書いた分は戻らない)。

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
            RuntimeError: ノードが無効な場合、またはMayaが書き込みを拒否した場合。
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
            TypeError: pathがstr・os.PathLikeでない場合、またはベースがメッシュでない場合。
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
            TypeError: pathがstr・os.PathLikeでない場合、またはnameMap・replace・namespaceMap・modeの型が正しくない場合。
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
    def _editing_item(self) -> tuple[int, int] | None:
        """編集モード(sculptTarget)で編集しているターゲットと項目を返す。

        Returns:
            tuple[int, int] | None: ターゲットの論理番号と ``inputTargetItem`` の論理番号。編集していなければNone。
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
    def _symmetry_settings(self, bi: int, space: str, edge: str | Edge | None) -> tuple[int, str | None]:
        """操作時の対称空間とベース上の基準エッジを検証する。

        Args:
            bi (int): ベースの論理番号。
            space (str): objectまたはtopology。
            edge (str | Edge | None): topologyの基準エッジ。

        Returns:
            tuple[int, str | None]: Mayaの空間番号と完全パスのエッジ名。
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
    def _write_deltas(self, path: str, indices: list[int], offsets: list[Sequence[float]], *, fast: bool = ..., check: bool = ...):
        """項目のデルタを書き、相対in-betweenの補助の値を消す(Mayaが再計算する)。

        通常は ``setAttr`` の2回(pointArray・componentList。連続する頂点は範囲にまとめる)で書く。

        Args:
            path (str): 項目のパス。
            indices (list[int]): 頂点番号(重複なし)。
            offsets (list[Sequence[float]]): 頂点番号と同じ数の変位。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。
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
    def _remove_vertices(self, path: str, remove: set[int], disconnect: bool, *, fast: bool = ..., check: bool = ...):
        """項目のデータから指定した頂点を取り除く。該当が無ければ何も変えない。

        Args:
            path (str): 項目のパス。
            remove (set[int]): 取り除く頂点番号。
            disconnect (bool): 接続中のターゲット形状を切るか。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。
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
    def _write_vertex_weights(self, path: str, values: dict[int, float], *, fast: bool = ..., check: bool = ...):
        """頂点ごとの値を書く。通常は連続する番号を範囲指定の1回のsetAttrにまとめる。

        Args:
            path (str): マルチアトリビュートのパス。
            values (dict[int, float]): 検証済みの頂点番号と値。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。
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

def _data_weight_item(weight: object) -> int:
    """保存データの項目のウェイトを、:func:`_weight_item` と同じ論理番号にする。

    保存データの形の不正はValueErrorにそろえるため、数値でない場合もValueErrorにする。

    Args:
        weight (object): 保存データの項目のウェイト。

    Returns:
        int: 論理番号。

    Raises:
        ValueError: 数値でない(boolを含む)、有限でない、範囲外、または0.001刻みで表せない場合。
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

def _target_shape(value: str | Node) -> Node:
    """ターゲットに使う形状(またはそれを持つTransform)を、形状のノードにする。

    Args:
        value (str | Node): 形状、またはそれを持つTransform。

    Returns:
        Node: Transformなら直下の中間オブジェクトでない最初の形状、形状ならそのもの。

    Raises:
        TypeError: 形状でも、形状を持つTransformでもない場合。
        RuntimeError: 名前のノードが無い場合。
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

def _vertex_values(weights: Sequence[float] | dict[int, float], count: int, *, check: bool = ...) -> dict[int, float]:
    """頂点ごとの値の指定を、検証済みの辞書にする。

    Args:
        weights (Sequence[float] | dict[int, float]): 全頂点の並び、または頂点番号と値。
        count (int): 頂点数。
        check (bool): Trueなら値が有限かを確かめる。

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
