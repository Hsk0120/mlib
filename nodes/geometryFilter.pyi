# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya のデフォーマー(geometryFilter)の共通部分を扱う。"""

import json
import math
from pathlib import Path
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
from ..core.fastWrite import require_range, require_writable, set_attr
from ..core.object import Object
from ..decorator import _edit_context
from .node import Node
from typing import Iterable
from mlib.components.component import Component
from mlib.components.component import Components

_DEFORMER_WEIGHTS_VERSION: int


class GeometryFilter(Node):
    """デフォーマー(cluster・deltaMush・softMod・skinClusterなど)に共通する操作を持つクラス。

    Mayaの抽象型 ``geometryFilter`` に対応する。頂点ごとの効き具合(デフォーマーのウェイト)を
    読み書きできる。デフォーマーのウェイトは ``weightList[形状の番号].weights`` に入っている。

    skinClusterでは、同じアトリビュートにインフルエンスのウェイトが入る。そのため、
    :meth:`getDeformerWeights` などは使えない。
    代わりに :meth:`SkinCluster.getWeights <mlib.nodes.skinCluster.SkinCluster.getWeights>` を使う。
    """
    def getGeometry(self) -> list[Node]:
        """このデフォーマーが変形する形状(出力ジオメトリ)を取得する。

        ``outputGeometry`` の接続先の形状を、``input`` の番号順に返す。
        ``cmds.deformer(query=True, geometry=True)`` と同じ結果になる。
        skinCluster・cluster・deltaMushなど、どのデフォーマーでも使える。

        Returns:
            list[Node]: 変形する形状。無ければ空リスト。
        """
        ...
    def getInputGeometry(self) -> list[Node]:
        """このデフォーマーへ入る、変形前の形状(入力ジオメトリ)を取得する。

        ``input[].inputGeometry`` から上流をたどって見つけた形状を、``input`` の番号順に返す。
        ``MFnGeometryFilter.getInputGeometry`` と同じ結果になる。
        手前に別のデフォーマーがあっても、それを越えた先の形状(``Orig`` の中間形状など)を返す。

        Returns:
            list[Node]: 入力側の形状。無ければ空リスト。

        Raises:
            RuntimeError: ノードが無効な(削除された)場合。
        """
        ...
    def getDeformerWeights(self, geometryIndex: int = ...) -> list[float]:
        """頂点ごとのデフォーマーのウェイトを取得する。

        値が書かれていない頂点は、Mayaの既定どおり1.0(全部効く)として返す。

        Args:
            geometryIndex (int): 変形する形状の番号(``input``・``weightList`` の論理番号)。既定は0。

        Returns:
            list[float]: 形状の頂点(CV・ラティスの点)の番号順に並ぶ値。長さは形状の点の数と同じ。

        Raises:
            TypeError: geometryIndexがintでない場合、またはデフォーマーのウェイトを持たない型の場合。
            IndexError: geometryIndexの番号の形状が無い場合。
        """
        ...
    def setDeformerWeights(self, weights: Iterable[float], *, vertices: Component | Components | Iterable[int] | None = ..., geometryIndex: int = ..., fast: bool = ...) -> GeometryFilter:
        """頂点ごとのデフォーマーのウェイトを設定する。

        通常は ``cmds.setAttr`` で書き込む。番号が1ずつ続く頂点は、範囲を指定した1回のsetAttrにまとめる。

        Args:
            weights (Iterable[float]): 書き込む値。有限な数値を、verticesと同じ数だけ渡す。
                verticesがNoneなら、形状の点の数だけ渡す。
            vertices (Component | Components | Iterable[int] | None): 書き込む頂点(点)の番号。Noneなら全頂点。
                同じ番号を2回指定できない。指定した順にweightsと対応する。
            geometryIndex (int): 変形する形状の番号(``input``・``weightList`` の論理番号)。既定は0。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            GeometryFilter: 自身。

        Raises:
            TypeError: fastがbool以外の場合、geometryIndex・値・頂点の型が不正な場合、
                またはデフォーマーのウェイトを持たない型の場合。
            ValueError: 値の数が頂点の数と合わない場合、有限でない値がある場合、または頂点が重なっている場合。
            IndexError: geometryIndexの番号の形状が無い場合、または頂点番号が範囲外の場合。
            RuntimeError: アトリビュートがロックされているか入力が接続されている場合、
                またはMayaが書き込みを拒否した場合。
        """
        ...
    def dumpDeformerWeights(self, path: str | Path, geometryIndex: int | None = ...) -> None:
        """頂点ごとのデフォーマーのウェイトをJSONファイルへ書き出す。

        単純なJSON(UTF-8)で、次の項目を書く。

        - ``version``: 形式の版。今は1。
        - ``deformer``: ノード名。
        - ``geometries``: 形状ごとの ``index``・``numVertices``・``weights``。

        値が書かれていない頂点は、:meth:`getDeformerWeights` と同じく1.0で書く。

        Args:
            path (str | Path): 書き出し先のファイルパス。
            geometryIndex (int | None): 書き出す形状の番号。Noneなら変形するすべての形状を番号順に書く。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: geometryIndexがint・None以外の場合、またはデフォーマーのウェイトを持たない型の場合。
            IndexError: geometryIndexの番号の形状が無い場合。
        """
        ...
    def loadDeformerWeights(self, path: str | Path, *, fast: bool = ...) -> None:
        """JSONファイルからデフォーマーのウェイトを読み込んで設定する。

        :meth:`dumpDeformerWeights` が書き出したファイルを読む。
        ファイルの各形状は、形状の番号(``weightList`` の論理番号)と頂点数が合うかを確かめてから書き込む。
        デフォーマー名は比べないので、別のデフォーマーへも読み込める。

        書き込む前に全部の形状を確かめ、合わないものがあれば何も変えずにValueErrorにする。
        通常は、全部の形状の書き込みを1回のUndoにまとめる。

        Args:
            path (str | Path): 読み込むファイルパス。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合、ファイルの値が数値でない場合、
                またはデフォーマーのウェイトを持たない型の場合。
            ValueError: ファイルの形式や版が違う場合、形状の番号がこのデフォーマーに無い場合、
                または頂点数が違う場合。
            RuntimeError: アトリビュートがロックされているか入力が接続されている場合、
                またはMayaが書き込みを拒否した場合。
        """
        ...
    def copyDeformerWeightsTo(self, other: GeometryFilter | str, *, geometryIndex: int = ..., otherGeometryIndex: int = ..., fast: bool = ...) -> GeometryFilter:
        """デフォーマーのウェイトを別のデフォーマーへ写す。

        写す先は、頂点数が同じ別のデフォーマーか、同じデフォーマーの別の形状。
        頂点番号どうしで対応させ、位置では合わせない。通常は1回のUndoで戻せる。

        Args:
            other (GeometryFilter | str): 写す先のデフォーマー。
            geometryIndex (int): 写す元(自身)の形状の番号。既定は0。
            otherGeometryIndex (int): 写す先の形状の番号。既定は0。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            GeometryFilter: 写す先のデフォーマー。

        Raises:
            TypeError: fastがbool以外の場合、otherがデフォーマーでない場合、geometryIndexがintでない場合、
                またはどちらかがデフォーマーのウェイトを持たない型(skinClusterなど)の場合。
            ValueError: 頂点数が違う場合。
            IndexError: 指定した番号の形状が無い場合。
            RuntimeError: otherの名前のノードが無い場合、アトリビュートがロックされているか入力が接続されている場合、
                またはMayaが書き込みを拒否した場合。
        """
        ...
    def _geometry_indices(self) -> list[int]:
        """変形する形状の番号(``input``・``weightList`` の論理番号)を昇順で返す。

        Returns:
            list[int]: 番号。

        Raises:
            TypeError: デフォーマーのウェイトを持たない型の場合。
        """
        ...
    def _deformer_weight_plug(self, geometry_index: int) -> tuple[om2.MPlug, int]:
        """``weightList[geometry_index].weights`` の Plug と、形状の点の数を返す。

        Args:
            geometry_index (int): 変形する形状の番号。

        Returns:
            tuple[om2.MPlug, int]: weights のマルチアトリビュートの Plug と点の数。

        Raises:
            TypeError: geometry_index が int でない、またはデフォーマーのウェイトを持たない型の場合。
            IndexError: 形状が無い場合。
        """
        ...
    @staticmethod
    def _resolve_point_indices(vertices: Component | Components | Iterable[int], count: int) -> list[int]:
        """頂点の指定を、範囲内で重複の無い番号の list にする。

        Args:
            vertices (Component | Components | Iterable[int]): 頂点・点の参照または番号。
            count (int): 形状の点の数。

        Returns:
            list[int]: 指定順の番号。

        Raises:
            TypeError: 番号に変換できない型の場合。
            ValueError: 番号が重複している場合。
            IndexError: 番号が範囲外の場合。
        """
        ...
    @staticmethod
    def _resolve_weight_values(weights: Iterable[float], count: int) -> list[float]:
        """書き込む値を、有限な float の list にする。

        Args:
            weights (Iterable[float]): 値。
            count (int): 必要な数。

        Returns:
            list[float]: 値。

        Raises:
            TypeError: 数値でない値がある場合。
            ValueError: 数が合わない、または有限でない値がある場合。
        """
        ...
    def _set_deformer_weights_fast(self, plug: om2.MPlug, indices: list[int], values: list[float]) -> None:
        """全要素の書込み可否と範囲を先に調べてから、OpenMaya で書き込む。

        Args:
            plug (om2.MPlug): ``weightList[g].weights`` の Plug。
            indices (list[int]): 頂点番号。
            values (list[float]): 値。

        Returns:
            None: 値を返さない。
        """
        ...
    def _set_deformer_weights_cmds(self, geometry_index: int, indices: list[int], values: list[float]) -> None:
        """番号が1ずつ増える頂点を範囲にまとめ、cmds で書き込む。

        Args:
            geometry_index (int): 変形する形状の番号。
            indices (list[int]): 頂点番号。
            values (list[float]): 値。

        Returns:
            None: 値を返さない。
        """
        ...
