# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya のデフォーマー(geometryFilter)の共通部分を扱う。"""

import json
import math
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
from ..core.fastWrite import require_range, require_writable, set_attr
from ..core.object import Object
from ..decorator import _edit_context, _require_bool
from .node import Node, Nodes
from typing import Iterable, Literal
from mlib.components.component import Component
from mlib.components.component import Components
from mlib.nodes.objectSet import ObjectSet
from typing import overload
import os

_DEFORMER_WEIGHTS_VERSION: int


class GeometryFilter(Node):
    """デフォーマー(cluster・deltaMush・softMod・skinClusterなど)に共通する操作を持つクラス。

    Mayaの抽象型 ``geometryFilter`` に対応する。頂点ごとの効き具合(デフォーマーのウェイト)を
    読み書きできる。デフォーマーのウェイトは ``weightList[形状の番号].weights`` に入っている。

    skinClusterでは、同じアトリビュートにインフルエンスのウェイトが入る。そのため、
    :meth:`getDeformerWeights` などは使えない。
    代わりに :meth:`SkinCluster.getWeights <mlib.nodes.skinCluster.SkinCluster.getWeights>` を使う。
    """
    def getDeformerTools(self) -> Nodes:
        """デフォーマーを操作するMayaのツールオブジェクトを取得する。

        汎用deformerコマンドのdeformerToolsを使う。clusterではハンドルShape、
        skinClusterではJointなど、ノード型によって対象が異なる。Mayaの返却順を保持する。

        Returns:
            Nodes: 操作用ノード。存在しなければ空。

        Raises:
            RuntimeError: デフォーマーが無効、またはMayaが照会を拒否した場合。
        """
        ...
    @overload
    def getGeometry(self, *, input: bool = ..., geometryIndex: int | None = ..., all: Literal[True]) -> Nodes: ...
    @overload
    def getGeometry(self, *, input: bool = ..., geometryIndex: int | None = ..., all: Literal[False] = ...) -> Node | None: ...
    @overload
    def getGeometry(self, *, input: bool = ..., geometryIndex: int | None = ..., all: bool = ...) -> Node | Nodes | None:
        """このデフォーマーが変形する形状(出力ジオメトリ)を取得する。``input=True`` なら、変形前の形状(入力ジオメトリ)を取得する。

        - 既定: 先頭の形状(``outputGeometry`` の物理的な並びの最初)を1つ返す。``geometryIndex`` を渡すと、その論理番号の形状を1つ返す。
        - ``all=True``: すべての形状を、``input`` の番号順の集まりで返す。``cmds.deformer(query=True, geometry=True)`` と同じ結果になる。
        - ``input=True``: ``input[].inputGeometry`` から上流をたどって見つけた形状を返す。
          ``MFnGeometryFilter.getInputGeometry`` と同じ結果になる。
          手前に別のデフォーマーがあっても、それを越えた先の形状(``Orig`` の中間形状など)を返す。

        skinCluster・cluster・deltaMushなど、どのデフォーマーでも使える。

        Args:
            input (bool): Trueなら、入力側の形状を取得する。既定はFalse(出力側)。
            geometryIndex (int | None): input/outputGeometryの論理番号。既定はNone(先頭の形状)。
            all (bool): Trueなら、すべての形状を集まりで返す。既定はFalse。geometryIndexとは同時に指定できない。

        Returns:
            Node | Nodes | None: Mayaが返すDAGパスを持つShapeを1つ。形状が1つも無い場合と、
                ``input=True`` でその番号に入力のShapeが無い場合はNone。all=Trueなら形状の集まり(無ければ空の集まり)。

        Raises:
            TypeError: input・allがboolでない場合、geometryIndexがintでない場合、またはall=TrueとgeometryIndexを同時に指定した場合。
            IndexError: geometryIndexの論理番号の出力が無い場合。
            RuntimeError: ノードが無効な(削除された)場合、またはMayaが入力のShapeの取得を拒否した場合。
        """
        ...
    @overload
    def getGeometryIndices(self, geometry: str | Node | om2.MObject | om2.MDagPath) -> int: ...
    @overload
    def getGeometryIndices(self, geometry: None = ...) -> list[int]: ...
    @overload
    def getGeometryIndices(self, geometry: str | Node | om2.MObject | om2.MDagPath | None = ...) -> list[int] | int:
        """接続されている出力の形状の論理番号を取得する。``geometry`` を渡すと、その形状の論理番号を1つ返す。

        Args:
            geometry (str | Node | om2.MObject | om2.MDagPath | None): 出力側のShape、または直下に対象のShapeを1つだけ持つTransform。
                既定のNoneなら、すべての出力の番号を返す。

        Returns:
            list[int] | int: 出力の接続の物理的な並び順に対応する論理番号(欠番を詰め直さない)。
                geometryを渡したときは、その形状の論理番号(疎になり得る。getGeometryの一覧の位置とは違う)。

        Raises:
            TypeError: geometryがDAGノードでない場合。
            ValueError: geometryが変形の対象の形状でない場合、またはTransformに対象のShapeが複数ある場合。
            RuntimeError: デフォーマーが無効な場合、またはgeometryの名前を解決できない場合。
        """
        ...
    def getGeometryComponents(self, *, geometryIndex: int | None = ...) -> list[Components]:
        """指定した出力形状で変形対象となるコンポーネントを取得する。

        セット所属またはコンポーネントタグからMayaが返す対象を読む。必要に応じてDGが評価される。
        セット所属・タグ・選択は変更しない。

        Args:
            geometryIndex (int | None): input/outputGeometryの論理番号。既定はNone(先頭の形状)。

        Returns:
            list[Components]: Shapeと種類ごとのコンポーネント。対象が無ければ空のlist。

        Raises:
            TypeError: geometryIndexがintでない場合、または未対応のコンポーネント種別の場合。
            IndexError: 指定した論理番号の出力が無い場合、または形状が1つも無い場合。
            RuntimeError: デフォーマーが無効、またはMayaが対象を取得できない場合。
        """
        ...
    def getDeformerSet(self) -> ObjectSet | None:
        """このデフォーマーの所属を保持するobjectSetを取得する。

        Returns:
            ObjectSet | None: 所属セット。コンポーネントタグ方式などでセットを持たない場合はNone。

        Raises:
            RuntimeError: デフォーマーが無効な場合。
        """
        ...
    def getDeformerWeights(self, *, geometryIndex: int | None = ...) -> list[float]:
        """頂点ごとのデフォーマーのウェイトを取得する。

        値が書かれていない頂点は、Mayaの既定どおり1.0(全部効く)として返す。

        Args:
            geometryIndex (int | None): 変形する形状の番号(``input``・``weightList`` の論理番号)。既定はNone(先頭の形状)。

        Returns:
            list[float]: 形状の頂点(CV・ラティスの点)の番号順に並ぶ値。長さは形状の点の数と同じ。

        Raises:
            TypeError: geometryIndexがintでない場合、またはデフォーマーのウェイトを持たない型の場合。
            IndexError: geometryIndexの番号の形状が無い場合、または形状が1つも無い場合。
        """
        ...
    def setDeformerWeights(self, weights: Iterable[float], *, vertices: Component | Components | Iterable[int] | None = ..., geometryIndex: int | None = ..., fast: bool = ..., check: bool = ...) -> None:
        """頂点ごとのデフォーマーのウェイトを設定する。

        通常は ``cmds.setAttr`` で書き込む。番号が1ずつ続く頂点は、範囲を指定した1回のsetAttrにまとめる。

        Args:
            weights (Iterable[float]): 書き込む値。有限な数値を、verticesと同じ数だけ渡す。
                verticesがNoneなら、形状の点の数だけ渡す。
            vertices (Component | Components | Iterable[int] | None): 書き込む頂点(点)の番号。Noneなら全頂点。
                同じ番号を2回指定できない。指定した順にweightsと対応する。既定はNone。
            geometryIndex (int | None): 変形する形状の番号(``input``・``weightList`` の論理番号)。既定はNone(先頭の形状)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fast・checkがbool以外の場合、geometryIndex・値・頂点の型が不正な場合、
                またはデフォーマーのウェイトを持たない型の場合。
            ValueError: 値の数が頂点の数と合わない場合、有限でない値がある場合、頂点が重なっている場合、
                または頂点が変形する形状のものでない場合。
            IndexError: geometryIndexの番号の形状が無い場合、形状が1つも無い場合、または頂点番号が範囲外の場合。
            RuntimeError: アトリビュートがロックされているか入力が接続されている場合、
                またはMayaが書き込みを拒否した場合。
        """
        ...
    def dumpDeformerWeights(self, path: str | os.PathLike, *, geometryIndex: int | None = ..., all: bool = ...) -> None:
        """頂点ごとのデフォーマーのウェイトをJSONファイルへ書き出す。

        単純なJSON(UTF-8)で、次の項目を書く。

        - ``version``: 形式の版。今は1。
        - ``deformer``: ノード名。
        - ``geometries``: 形状ごとの ``index``・``numVertices``・``weights``。

        値が書かれていない頂点は、:meth:`getDeformerWeights` と同じく1.0で書く。

        Args:
            path (str | os.PathLike): 書き出し先のファイルパス。フォルダーは作らない。
            geometryIndex (int | None): 書き出す形状の番号。既定はNone(先頭の形状)。
            all (bool): Trueなら、変形するすべての形状を番号順に書く。既定はFalse。geometryIndexとは同時に指定できない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: pathがstr・os.PathLikeでない場合、geometryIndexがint・None以外の場合、allがboolでない場合、
                all=TrueとgeometryIndexを同時に指定した場合、またはデフォーマーのウェイトを持たない型の場合。
            IndexError: geometryIndexの番号の形状が無い場合、または形状が1つも無い場合。
            OSError: 書き出しに失敗した場合。
        """
        ...
    def loadDeformerWeights(self, path: str | os.PathLike, *, fast: bool = ..., check: bool = ...) -> None:
        """JSONファイルからデフォーマーのウェイトを読み込んで設定する。

        :meth:`dumpDeformerWeights` が書き出したファイルを読む。
        ファイルの各形状は、形状の番号(``weightList`` の論理番号)と頂点数が合うかを確かめてから書き込む。
        デフォーマー名は比べないので、別のデフォーマーへも読み込める。

        書き込む前に全部の形状を確かめ、合わないものがあれば何も変えずにValueErrorにする。
        通常は、全部の形状の書き込みを1回のUndoにまとめる。

        Args:
            path (str | os.PathLike): 読み込むファイルパス。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、全部の形状の要素へ書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: pathがstr・os.PathLikeでない場合、fast・checkがbool以外の場合、ファイルの値が数値でない場合、
                またはデフォーマーのウェイトを持たない型の場合。
            ValueError: ファイルの形式や版が違う場合、形状の番号がこのデフォーマーに無い場合、
                または頂点数が違う場合。
            RuntimeError: アトリビュートがロックされているか入力が接続されている場合、
                またはMayaが書き込みを拒否した場合。
            OSError: ファイルの読み込みに失敗した場合。
        """
        ...
    def copyDeformerWeightsTo(self, other: GeometryFilter | str, *, geometryIndex: int | None = ..., otherGeometryIndex: int | None = ..., fast: bool = ..., check: bool = ...) -> GeometryFilter:
        """デフォーマーのウェイトを別のデフォーマーへ写す。

        写す先は、頂点数が同じ別のデフォーマーか、同じデフォーマーの別の形状。
        頂点番号どうしで対応させ、位置では合わせない。通常は1回のUndoで戻せる。

        Args:
            other (GeometryFilter | str): 写す先のデフォーマー。
            geometryIndex (int | None): 写す元(自身)の形状の番号。既定はNone(先頭の形状)。
            otherGeometryIndex (int | None): 写す先の形状の番号。既定はNone(先頭の形状)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。:meth:`setDeformerWeights` の ``check`` と同じ。

        Returns:
            GeometryFilter: 写す先のデフォーマー。

        Raises:
            TypeError: fast・checkがbool以外の場合、otherがデフォーマーでない場合、geometryIndexがintでない場合、
                またはどちらかがデフォーマーのウェイトを持たない型(skinClusterなど)の場合。
            ValueError: 頂点数が違う場合。
            IndexError: 指定した番号の形状が無い場合、または形状が1つも無い場合。
            RuntimeError: otherの名前のノードが無い場合、アトリビュートがロックされているか入力が接続されている場合、
                またはMayaが書き込みを拒否した場合。
        """
        ...
    def _deformer_fn(self) -> oma2.MFnGeometryFilter:
        """有効性を確かめてデフォーマーのfunction setを取得する。

        Returns:
            oma2.MFnGeometryFilter: このノードのfunction set。
        """
        ...
    @staticmethod
    def _require_geometry_index(fn: oma2.MFnGeometryFilter, geometry_index: int):
        """出力に実在する論理番号かを確かめる。

        Args:
            fn (oma2.MFnGeometryFilter): 有効なデフォーマー。
            geometry_index (int): 出力の論理番号。
        """
        ...
    @classmethod
    def _resolve_geometry_index(cls, fn: oma2.MFnGeometryFilter, geometry_index: int | None) -> int:
        """形状の番号の指定を、出力に実在する論理番号にする。Noneなら先頭の形状の番号にする。

        Args:
            fn (oma2.MFnGeometryFilter): 有効なデフォーマー。
            geometry_index (int | None): 出力の論理番号。Noneなら先頭(出力の物理的な並びの最初)の形状。

        Returns:
            int: 論理番号。

        Raises:
            TypeError: geometry_indexがint・None以外の場合。
            IndexError: その番号の出力が無い場合、またはNoneで形状が1つも無い場合。
        """
        ...
    def _default_geometry_index(self, geometry_index: int | None) -> int | object:
        """geometryIndexの既定(None)を先頭の形状の論理番号にする。int・それ以外の値はそのまま返す(呼び出し側で確かめる)。

        Args:
            geometry_index (int | None): 形状の番号の指定。

        Returns:
            int | object: Noneなら先頭の形状の論理番号、それ以外はそのままの値。

        Raises:
            IndexError: Noneで、形状が1つも無い場合。
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
    def _resolve_point_indices(vertices: Component | Components | Iterable[int], count: int, shape: om2.MObject) -> list[int]:
        """頂点の指定を、範囲内で重複の無い番号の list にする。

        Args:
            vertices (Component | Components | Iterable[int]): 頂点・点の参照または番号。
            count (int): 形状の点の数。
            shape (om2.MObject): 変形する形状。コンポーネントで指定したときは、この形状のものかを確かめる。

        Returns:
            list[int]: 指定順の番号。

        Raises:
            TypeError: 番号に変換できない型の場合。
            ValueError: 番号が重複している場合、または別の形状のコンポーネントの場合。
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
    def _set_deformer_weights_fast(self, plug: om2.MPlug, indices: list[int], values: list[float], check: bool = ...) -> None:
        """全要素の範囲(check=Trueなら書込み可否も)を先に調べてから、OpenMaya で書き込む。

        Args:
            plug (om2.MPlug): ``weightList[g].weights`` の Plug。
            indices (list[int]): 頂点番号。
            values (list[float]): 値。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

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
