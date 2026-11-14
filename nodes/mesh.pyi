# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya のメッシュシェイプを扱う。"""

import math
from collections import Counter, defaultdict
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..components.edge import Edge, Edges
from ..components.face import Face, Faces
from ..components.pointComponent import _mirror_plan, _write_points
from ..components.uv import UV, UVs
from ..components.vertex import Vertex, Vertices
from ..components.vertexFace import VertexFaces
from ..core import geometryEdit as geometry_edit
from ..core.fastWrite import require_writable
from ..decorator import _edit_context, _pick_alias, _require_bool, undoChunk, undoTransaction
from ..maths.vector import Vector, _vector_of, _vectors_of_points
from ..util import _UNSET, _checked_tolerance, _finite_vector, _mirror_axis, _PointGrid, _world_space
from .shape import Shape
from typing import Any, Iterable, Sequence
from mlib.components.component import Component
from mlib.components.component import Components
from mlib.nodes.node import Node
from mlib.nodes.shadingEngine import ShadingEngine

_NO_DISTANCE_LIMIT: float
_INTERSECT_MERGE: float
_UNSET_COLOR_VALUES: tuple
_UNSET_COLOR: Any


class Mesh(Shape):
    """Mayaのmeshシェイプノードを扱うクラス。"""
    def reorderVertices(self, reference: Mesh | Node | str, uvSet: str = ..., tolerance: float = ..., *, fast: bool = ..., match: str = ..., worldSpace: bool = ..., ws: bool = ...) -> Mesh:
        """頂点番号の並びを、基準のメッシュに合わせる。

        UVか頂点の位置で、基準のメッシュの頂点と1対1に対応させ、その番号へ並べ替える。

        - 頂点の位置・面の順と向き・UV・法線・面のマテリアルは変わらない。エッジの番号は変わることがある。
        - スキンなど、頂点番号に頼るデータは移し替えない。すでに取得したComponentは、処理の後に取り直す。
        - UVの切れ目(シーム)は、頂点ごとの面頂点のUVの組で照らし合わせる。対応があいまいなら、何も変えずにエラーにする。

        Args:
            reference (Mesh | Node | str): 基準のMesh、またはメッシュを1つだけ持つTransform。
            uvSet (str): UVで照らし合わせるときのUVセットの名前。既定は ``"map1"``。位置で照らし合わせるときは使わない。
            tolerance (float): 許す誤差。0以上の有限な数値。UVでは成分の差、位置ではcmの距離。既定は1e-6。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。Trueなら、0でないtweakを今の位置へベイクしてから作り直す。
                FalseならUndoが有効である必要があり、0でないtweakには対応しない。
            match (str): 照らし合わせ方。``"uv"`` (既定)か ``"position"``。
            worldSpace (bool): 位置で照らし合わせるとき、Trueならワールド空間、Falseなら各Shapeのオブジェクト空間で比べる。
                既定はFalse。UVで照らし合わせるときは使わない。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Mesh: 自身。番号の対応がすでに同じなら、作り直さずにそのまま返す(作り直すための制限の確認もしない)。

        Raises:
            TypeError: 入力の型やfast・worldSpaceが不正な場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 対応があいまいか足りない場合、トポロジーや面の向きが合わない場合、
                または作り直すときに、入出力のヒストリ・インスタンス・リファレンス・カラーセット・クリースなどがある場合。
            RuntimeError: 作り直すときにロックされている場合、または通常の処理でUndoが無効な場合。
            NotImplementedError: 通常の処理で、頂点のtweakがあるメッシュの法線を並べ替える場合。
        """
        ...
    def getVertex(self, index: int) -> Vertex:
        """頂点番号から頂点を1つ取得する。

        Args:
            index (int): 0から始まる頂点番号。

        Returns:
            Vertex: シーンの頂点を指すオブジェクト。

        Raises:
            IndexError: 頂点番号が範囲外の場合。
        """
        ...
    def getVertices(self, indices: Iterable[int] | None = ...) -> Vertices:
        """指定した頂点をまとめて取得する。

        Args:
            indices (Iterable[int] | None): 頂点番号。Noneなら今あるすべての頂点。

        Returns:
            Vertices: 頂点のコレクション。番号の順はそのままで、同じ番号は1回だけ含む。
        """
        ...
    def getVertexFaces(self, indices: Iterable[int | tuple[int, int]] | None = ...) -> VertexFaces:
        """指定した頂点フェース(``vtxFace[v][f]``)をまとめて取得する。

        Args:
            indices (Iterable[int | tuple[int, int]] | None): 通しの番号か ``(頂点番号, フェース番号)``。
                Noneなら今あるすべての頂点フェース。

        Returns:
            VertexFaces: 頂点フェースのコレクション。番号の順はそのままで、同じものは1回だけ含む。

        Raises:
            IndexError: 頂点がそのフェースに含まれない場合、または番号が範囲外の場合。
        """
        ...
    def getShadingEngines(self) -> list[ShadingEngine]:
        """フェースに割り当てられているShadingEngineを取得する。

        このオブジェクトが持つDAGパス(インスタンス)での割り当てを調べる。

        Returns:
            list[ShadingEngine]: 使われているShadingEngine。何も割り当てられていないフェースの分は含まない。
        """
        ...
    def getFaceShadingEngines(self) -> list[ShadingEngine | None]:
        """フェースごとに割り当てられているShadingEngineを、フェース番号の順に取得する。

        Returns:
            list[ShadingEngine | None]: すべてのフェースの割り当て。何も割り当てられていないフェースはNone。
        """
        ...
    def mfn(self) -> om2.MFnMesh | om2.MFnDagNode:
        """このメッシュのfunction setを取得する。

        呼び出すたびに新しく作る。形状のデータを持つ場合は ``om2.MFnMesh`` を返す。
        ``mlib.createNode("mesh")`` の直後のように形状のデータを持たない空のシェイプでは、
        ``om2.MFnMesh`` が使えない(Maya 2027では作るときにValueError、版によっては作った後の取得でRuntimeError)。
        そのため ``om2.MFnDagNode`` を返す。DagNodeに共通の取得(中間オブジェクトかの判定・親の一覧など)は、
        空のシェイプでも使える。

        Returns:
            om2.MFnMesh | om2.MFnDagNode: このメッシュのfunction set。空のシェイプではMFnDagNode。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        ...
    def getNumVertices(self) -> int:
        """頂点数を取得する。

        Returns:
            int: メッシュの頂点数。
        """
        ...
    def getNumPolygons(self) -> int:
        """ポリゴン数を取得する。

        Returns:
            int: メッシュのポリゴン数。
        """
        ...
    def getNumEdges(self) -> int:
        """エッジ数を取得する。

        Returns:
            int: メッシュのエッジ数。
        """
        ...
    def getPoints(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """全頂点の位置を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間で扱う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[Vector]: 頂点番号の順に並ぶ位置(:class:`~mlib.maths.vector.Vector`)。
                距離はMaya APIの内部単位(cm)。そのまま :meth:`setPoints` へ渡せる。

        Raises:
            TypeError: worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
        """
        ...
    def setPoints(self, points: Iterable[Sequence[float] | om2.MPoint | om2.MVector], worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> Mesh:
        """全頂点の位置をまとめて書き込み、自身を返す。

        :meth:`getPoints` と同じ並び・単位(内部単位のcm)の点の並びを受け取る。
        通常は ``cmds.xform`` で書き込み、1回のUndoにまとめる。
        ``fast=True`` なら ``MFnMesh.setPoints`` で全頂点を1回で書き込み、Undoには記録しない。
        頂点数・トポロジー・UVは変えない。
        :meth:`NurbsCurve.setCvPositions <mlib.nodes.nurbsCurve.NurbsCurve.setCvPositions>` と同じ使い方ができる。

        Args:
            points (Iterable[Sequence[float] | om2.MPoint | om2.MVector]): 頂点番号の順の位置。
                :meth:`getPoints` の結果(list[Vector])・3つの数値のtupleの並び・``om2.MPointArray`` を
                そのまま渡せる。各点は3つの有限な数値。MPointはwで割らずにXYZを使う。
            worldSpace (bool): Trueならワールド空間、Falseならローカル(オブジェクト)空間で書き込む。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: worldSpace・fastがbool以外の場合、点の型や成分が不正な場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 点の数が頂点数と合わない場合、または有限でない成分がある場合。
            RuntimeError: 形状のデータが無いか無効なシェイプの場合、またはロックなどでMayaが書き込みを拒否した場合。
            NotImplementedError: fast=Trueで、inMeshへの入力(コンストラクションヒストリ)がある場合。

        Note:
            今と同じ位置の頂点は書き込まない(``getPoints()`` の結果を一部だけ変えて戻すと、
            変えた頂点だけを書き込む)。書き込む頂点ごとに ``cmds.xform`` を呼ぶので(``setCvPositions`` と同じ)、
            多くの頂点を動かすと、頂点数に比例して時間がかかる(目安は1頂点あたり約1ms)。
            ``fast=True`` は全頂点をまとめて書くので、頂点数が多いほど差が大きくなる。
        """
        ...
    def mirror(self, axis: str | int = ..., worldSpace: bool = ..., pivot: Iterable[float] = ..., indices: Iterable[int] | None = ..., *, fast: bool = ..., ws: bool = ...) -> Mesh:
        """頂点の座標を、pivotを中心に反転する。

        反転後の座標は ``2 * pivot - 今の座標`` になる。

        - Transformとトポロジー(頂点番号・面のつながりと頂点の順)は変えない。
        - Shapeを共有しているインスタンスすべてに影響する。
        - 複製・結合・片側からの対称化・法線の反転はしない(1軸や3軸で反転すると、面の向きが裏返る)。

        入力をすべて確かめてから書き込む。通常は ``cmds.xform`` を頂点ごとに呼び、1回のUndoにまとめる
        (目安は1頂点あたり約0.2ms)。``fast=True`` なら ``MFnMesh.setPoints`` で全頂点を1回で書く。
        :meth:`Vertices.mirror <mlib.components.pointComponent.PointComponents.mirror>` と同じ処理。

        Args:
            axis (str | int): 反転する軸かミラー面。既定は ``"x"``。軸は ``"x"``・``"y"``・``"z"``、
                面は ``"YZ"``・``"XZ"``・``"XY"`` (xはYZ、yはXZ、zはXYと同じ。文字の順や大文字・小文字は問わない)、
                番号なら0・1・2。
            worldSpace (bool): Trueなら、このオブジェクトが持つDAGパスのワールド空間、Falseならシェイプの
                オブジェクト空間で反転する。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            pivot (Iterable[float]): 反転の中心のXYZ(cm)。worldSpaceで選んだ空間の座標で指定する。
                既定は原点で、Transformのピボットとは関係ない。
            indices (Iterable[int] | None): 頂点番号。Noneなら全頂点、空の並びなら何も変えない。同じ番号は1回だけ処理する。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: worldSpace・fastがbool以外の場合、axisが文字列・int以外の場合、番号の型が不正な場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: axisやpivotが不正な場合、またはworldSpace=Trueで変換のマトリクスがほぼ特異な(逆にできない)場合。
            IndexError: 頂点番号が負の数か範囲外の場合。
            RuntimeError: 形状のデータが無いか無効なシェイプの場合、またはロックなどでMayaが書き込みを拒否した場合。
            NotImplementedError: fast=Trueで、inMeshへの入力(コンストラクションヒストリ)がある場合。
        """
        ...
    def getVertexNormals(self, worldSpace: bool = ..., angleWeighted: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """頂点ごとの法線を取得する。

        各頂点に接する面頂点の法線を平均して求める。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間で扱う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            angleWeighted (bool): Trueなら、隣り合う面の角度で重み付けした法線を取得する。既定はFalse。

        Returns:
            list[Vector]: 頂点番号の順に並ぶ、平均した法線。angleWeighted=Falseなら、
                角度による重み付けはしない。MFnMesh.getVertexNormals()を使う。

        Raises:
            TypeError: worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
        """
        ...
    def getVertexAdjacency(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[list[tuple[int, float]]]:
        """頂点ごとに、隣の頂点とエッジの長さを取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間で扱う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[list[tuple[int, float]]]: 頂点番号の順に並ぶ、隣の頂点のリスト。
            各要素は(隣の頂点番号, 距離(cm))で、エッジ番号の順に並ぶ。
            どこにもつながっていない頂点は空リスト。同じ2頂点を結ぶエッジが複数あれば、別々に入る。

        Raises:
            TypeError: worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
        """
        ...
    def getShells(self) -> list[Vertices]:
        """エッジでつながった頂点のまとまり(シェル)を取得する。

        Returns:
            list[Vertices]: シェルごとの頂点(番号の小さい順)。シェルは、それぞれのいちばん小さい頂点番号の順に並ぶ。
                どこにもつながっていない頂点は、1頂点だけのシェルになる。
        """
        ...
    def getUVShells(self, uvSet: str | None = ...) -> list[list[int]]:
        """UVでつながったUVのまとまり(UVシェル)を取得する。

        ``MFnMesh.getUvShellsIds`` を使う。形状のシェル(:meth:`getShells`)と違い、UVの切れ目で分かれる。

        Args:
            uvSet (str | None): UVセットの名前。Noneなら今のUVセットを使う。

        Returns:
            list[list[int]]: シェルごとのUV番号(小さい順)。シェルは、それぞれのいちばん小さいUV番号の順に並ぶ。
                UVが無ければ空リスト。番号は指定したUVセットのもの
                (:class:`~mlib.components.uv.UVs` は今のUVセットを指すので、別のUVセットの番号はintのlistで返す)。

        Raises:
            TypeError: uvSetが文字列・None以外の場合。
            ValueError: 名前が空の場合、そのUVセットが無い場合、またはメッシュにUVセットが無い場合。
        """
        ...
    def getTriangles(self) -> list[tuple[int, int, int]]:
        """ポリゴンを三角形に分けたときの、頂点の組を取得する。

        分け方はMayaの三角形分割に従う。

        Returns:
            list[tuple[int, int, int]]: 三角形ごとの頂点番号。フェース番号の順に並び、各フェースの中はMayaが分けた順。
        """
        ...
    def getMirrorVertexMap(self, axis: str | int = ..., tolerance: float = ..., worldSpace: bool = ..., *, ws: bool = ...) -> dict[int, int]:
        """頂点ごとに、位置を軸で反転した反対側の頂点を取得する。

        反転した位置から ``tolerance`` 以内で、いちばん近い頂点を反対側とする。トポロジーは見ない。

        Args:
            axis (str | int): 反転する軸 ``"x"``・``"y"``・``"z"``、ミラー面 ``"YZ"``・``"XZ"``・``"XY"``、または0・1・2。既定は ``"x"``。
            tolerance (float): 反転した位置と頂点の距離が、どこまでなら同じとみなすか(cm)。正の有限な数値。既定は0.01。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間で扱う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            dict[int, int]: {頂点番号: 反対側の頂点番号}。反対側が見つからない頂点は含まない。
                軸の上にある頂点は、自身に対応する(キーと値が同じ)。

        Raises:
            TypeError: axisが文字列・int以外の場合、toleranceが実数以外の場合、worldSpaceがbool以外の場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: axisが不正な場合、またはtoleranceが正の有限な数値でない場合。
        """
        ...
    def getClosestVertex(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, ws: bool = ...) -> Vertex:
        """指定した位置にいちばん近い頂点を取得する。

        頂点の位置だけで比べる(面の上でいちばん近い点ではない)。たくさんの点を調べるなら :meth:`getClosestVertices` を使う。

        Args:
            point (Sequence[float] | om2.MPoint | om2.MVector): 位置(cm)。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間で扱う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vertex: いちばん近い頂点。

        Raises:
            TypeError: 点の型や成分が不正な場合、worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 成分の数が3でないか有限でない場合、またはメッシュに頂点が無い場合。
            RuntimeError: 形状のデータを持たない空のシェイプ(``mlib.createNode("mesh")`` の直後など)の場合。
        """
        ...
    def getClosestVertices(self, points: Iterable[Sequence[float] | om2.MPoint | om2.MVector], worldSpace: bool = ..., *, ws: bool = ...) -> list[int]:
        """点ごとに、いちばん近い頂点の番号を取得する。

        頂点の位置に等間隔の格子を作って探す(面の上でいちばん近い点ではない)。

        Args:
            points (Iterable[Sequence[float] | om2.MPoint | om2.MVector]): 位置(cm)の並び。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間で扱う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[int]: いちばん近い頂点の番号。pointsと同じ順に並ぶ。

        Raises:
            TypeError: 点の並び・点の型・成分が不正な場合、worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 成分の数が3でないか有限でない場合、またはメッシュに頂点が無い場合。
            RuntimeError: 形状のデータを持たない空のシェイプ(``mlib.createNode("mesh")`` の直後など)の場合。
        """
        ...
    def getEdge(self, index: int) -> Edge:
        """番号からエッジを1つ取得する。

        Args:
            index (int): 0から始まる番号。

        Returns:
            Edge: シーンのエッジを指すオブジェクト。
        """
        ...
    def getEdges(self, indices: Iterable[int] | None = ...) -> Edges:
        """指定したエッジをまとめて取得する。

        Args:
            indices (Iterable[int] | None): 番号の並び。Noneなら今あるすべてのエッジ。

        Returns:
            Edges: エッジのコレクション。同じ番号は1回だけ含む。
        """
        ...
    def getFace(self, index: int) -> Face:
        """番号からフェースを1つ取得する。

        Args:
            index (int): 0から始まる番号。

        Returns:
            Face: シーンのフェースを指すオブジェクト。
        """
        ...
    def getFaces(self, indices: Iterable[int] | None = ...) -> Faces:
        """指定したフェースをまとめて取得する。

        Args:
            indices (Iterable[int] | None): 番号の並び。Noneなら今あるすべてのフェース。

        Returns:
            Faces: フェースのコレクション。同じ番号は1回だけ含む。
        """
        ...
    def getUV(self, index: int) -> UV:
        """番号からUVを1つ取得する。

        Args:
            index (int): 0から始まる番号。

        Returns:
            UV: シーンのUVを指すオブジェクト。
        """
        ...
    def getUVs(self, indices: Iterable[int] | None = ...) -> UVs:
        """指定したUVをまとめて取得する。

        Args:
            indices (Iterable[int] | None): 番号の並び。Noneなら今あるすべてのUV。

        Returns:
            UVs: UVのコレクション。同じ番号は1回だけ含む。
        """
        ...
    def getNumUVs(self) -> int:
        """今のUVセットのUVの数を取得する。

        Returns:
            int: UVの数。
        """
        ...
    def getClosestPoint(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, ws: bool = ...) -> tuple[Vector, int]:
        """指定した位置にいちばん近い、メッシュの面の上の点を取得する。

        ``MFnMesh.getClosestPoint`` を使う。頂点だけを比べる :meth:`getClosestVertex` と違い、
        面の内部・エッジの上の点も返す。

        Args:
            point (Sequence[float] | om2.MPoint | om2.MVector): 位置(cm)。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。入力と戻り値の両方に使う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            tuple[Vector, int]: 面の上でいちばん近い点(cm)と、その点を含む面の番号。

        Raises:
            TypeError: 点の型や成分が不正な場合、worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 成分の数が3でないか有限でない場合、またはメッシュに面が無い場合。
            RuntimeError: 形状のデータを持たない空のシェイプ(``mlib.createNode("mesh")`` の直後など)の場合。
        """
        ...
    def getClosestNormal(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
        """指定した位置にいちばん近い面の上の点で、補間した法線を取得する。

        いちばん近い点を含む三角形の、3つの面頂点の法線(ハードエッジ・ソフトエッジを反映した、表示に使う法線)を、
        その点の重心座標で補間して長さ1にする。``MFnMesh.getClosestNormal`` が返す面の法線ではない。
        ハードエッジだけのメッシュ(立方体など)では、面の法線と同じ向きになる。

        Args:
            point (Sequence[float] | om2.MPoint | om2.MVector): 位置(cm)。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。入力と戻り値の両方に使う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 長さ1の法線。ワールド空間では、オブジェクト空間の法線をマトリクスの逆転置で変換する。

        Raises:
            TypeError: 点の型や成分が不正な場合、worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 成分の数が3でないか有限でない場合、またはメッシュに面が無い場合。
            RuntimeError: 形状のデータを持たない空のシェイプ(``mlib.createNode("mesh")`` の直後など)の場合。

        Note:
            いちばん近い点はオブジェクト空間で探す(``MMeshIntersector``)。XYZで違うスケールが掛かった
            メッシュをワールド空間で調べると、:meth:`getClosestPoint` と違う面の点になることがある。
        """
        ...
    def intersect(self, origin: Sequence[float] | om2.MPoint | om2.MVector, direction: Sequence[float] | om2.MVector, *, maxDistance: float | None = ..., worldSpace: bool = ..., ws: bool = ...) -> list[tuple[Vector, int, float]]:
        """半直線とメッシュが交わる点を、近い順に取得する。

        ``MFnMesh.allIntersections`` を使い、``origin`` から ``direction`` の向きにだけ調べる(逆向きは調べない)。
        面の向き(法線)に関係なく、表からでも裏からでも当たる(両面)。

        Args:
            origin (Sequence[float] | om2.MPoint | om2.MVector): 半直線の始点(cm)。
            direction (Sequence[float] | om2.MVector): 向き。長さは問わない(中で長さ1にする)。
            maxDistance (float | None): 始点からどこまで調べるか(cm)。正の有限な数値。Noneなら制限しない。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。入力と戻り値の両方に使う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[tuple[Vector, int, float]]: (交点, 面の番号, 始点からの距離(cm))。距離の近い順に並ぶ。
                当たらなければ空リスト。1つの面を三角形の境目で2回当てた結果は、1つにまとめる。
                面と面の境目のエッジに当たった場合は、それぞれの面を別の要素で返す。

        Raises:
            TypeError: 点や向きの型・成分が不正な場合、maxDistanceが数値・None以外の場合、worldSpaceがbool以外の場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: 有限でない成分がある場合、directionの長さが0の場合、またはmaxDistanceが正の有限な数値でない場合。

        Note:
            Mayaの交差の判定は単精度(float)で計算するので、交点と距離には1e-5くらいの誤差がある。
        """
        ...
    def getUVAtPoint(self, point: Sequence[float] | om2.MPoint | om2.MVector, uvSet: str | None = ..., worldSpace: bool = ..., *, ws: bool = ...) -> tuple[float, float]:
        """指定した位置にいちばん近い、面の上の点のUVを取得する。

        位置が面の上に無ければ、いちばん近い面の上の点のUVになる。
        いちばん近い点を含む三角形の、3つの面頂点のUVを、その点の重心座標で補間する
        (``closestPointOnMesh`` ノードの ``parameterU/V`` と同じ値)。
        ``MFnMesh.getUVAtPoint`` は、面の境目の近くで隣の面のUVを返すことがあるので使わない。

        Args:
            point (Sequence[float] | om2.MPoint | om2.MVector): 位置(cm)。
            uvSet (str | None): UVセットの名前。Noneなら今のUVセットを使う。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間で扱う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            tuple[float, float]: (u, v)。

        Raises:
            TypeError: 点の型や成分が不正な場合、uvSetが文字列・None以外の場合、worldSpaceがbool以外の場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: 有限でない成分がある場合、UVセットが無い場合、またはメッシュに面が無い場合。
            RuntimeError: いちばん近い面にUVが割り当てられていない場合。

        Note:
            いちばん近い点は、:meth:`getClosestNormal` と同じくオブジェクト空間で探す。
        """
        ...
    def getPointAtUV(self, u: float, v: float, uvSet: str | None = ..., worldSpace: bool = ..., *, ws: bool = ...) -> Vector | None:
        """UVの位置に対応する、面の上の点を取得する。

        面番号の順に、UVの範囲に (u, v) を含む面を ``MFnMesh.getPointAtUV`` で調べ、最初に見つかった面の点を返す。
        UVが重なっていて複数の面に当たる場合も、番号がいちばん小さい面の点になる。

        Args:
            u (float): U座標。
            v (float): V座標。
            uvSet (str | None): UVセットの名前。Noneなら今のUVセットを使う。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間で扱う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector | None: 面の上の点(cm)。どの面のUVにも含まれない位置ならNone。

        Raises:
            TypeError: u・vが数値以外の場合、uvSetが文字列・None以外の場合、worldSpaceがbool以外の場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: u・vが有限でない場合、またはUVセットが無い場合。
        """
        ...
    def getVertexColors(self, colorSet: str | None = ...) -> list[tuple[float, float, float, float] | None]:
        """頂点ごとの色を取得する。

        ``MFnMesh.getVertexColors`` を使う。面ごとに違う色を持つ頂点(面頂点の色)は、それらの平均になる。

        Args:
            colorSet (str | None): カラーセットの名前。Noneなら今のカラーセットを使う。

        Returns:
            list[tuple[float, float, float, float] | None]: 頂点番号の順に並ぶ(R, G, B, A)。
                色の無い頂点はNone。colorSetにNoneを指定し、カラーセットが1つも無い場合はすべてNone。

        Raises:
            TypeError: colorSetが文字列・None以外の場合。
            ValueError: 指定した名前のカラーセットが無い場合。
        """
        ...
    def setVertexColors(self, colors: Iterable[Sequence[float] | om2.MColor], vertices: Component | Components | Iterable[int] | None = ..., *, colorSet: str | None = ..., fast: bool = ...) -> Mesh:
        """頂点ごとの色を設定し、自身を返す。

        頂点のすべての面頂点を同じ色にする。
        通常は ``cmds.polyColorPerVertex`` で、同じ色の頂点をまとめて色ごとに1回ずつ書き、1回のUndoにまとめる。
        色の種類が多いと時間がかかる(目安は1色あたり約1ms)。
        ``fast=True`` なら ``MFnMesh.setVertexColors`` で1回で書き、Undoには記録しない。

        Args:
            colors (Iterable[Sequence[float] | om2.MColor]): 頂点の色。各色は (R, G, B) か (R, G, B, A) の
                有限な数値(Aを省略すると1.0)。verticesと同じ数だけ渡す(verticesがNoneなら頂点数だけ)。
            vertices (Component | Components | Iterable[int] | None): 書き込む頂点の番号。Noneなら全頂点。
                同じ番号を2回指定できない。指定した順にcolorsと対応する。
            colorSet (str | None): カラーセットの名前。Noneなら今のカラーセットを使う(無ければMayaが
                ``colorSet1`` を作る)。名前を指定する場合は、そのカラーセットがすでにある必要がある。
                今のカラーセットは変えない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: fastがbool以外の場合、colorSetが文字列・None以外の場合、または色や頂点の型が不正な場合。
            ValueError: 色の数が頂点の数と合わない場合、成分の数が3・4以外か有限でない場合、頂点が重なっている場合、
                別のメッシュの頂点を渡した場合、またはカラーセットが無い場合。
            IndexError: 頂点番号が範囲外の場合。
            RuntimeError: シェイプのロックなどでMayaが書き込みを拒否した場合。
            NotImplementedError: fast=Trueで、inMeshへの入力(コンストラクションヒストリ)がある場合。

        Note:
            通常の処理では、コンストラクションヒストリのあるメッシュに ``polyColorPerVertex`` ノードをヒストリとして足す。
        """
        ...
    def getUVSetNames(self) -> list[str]:
        """UVセットの名前を取得する。

        Returns:
            list[str]: UVセットの名前。Mayaが返す順に並び、先頭が既定のUVセット(``uvSet[0]``)。
        """
        ...
    def getCurrentUVSet(self) -> str:
        """今のUVセットの名前を取得する。

        Returns:
            str: 今のUVセットの名前。
        """
        ...
    def setCurrentUVSet(self, name: str) -> Mesh:
        """今のUVセットを切り替え、自身を返す。

        ``cmds.polyUVSet(currentUVSet=True)`` で設定する。1回のUndoで戻せる。

        Args:
            name (str): すでにあるUVセットの名前。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: nameが文字列以外の場合。
            ValueError: nameが空、またはそのUVセットが無い場合。
        """
        ...
    def createUVSet(self, name: str) -> Mesh:
        """空のUVセットを作り、自身を返す。

        ``cmds.polyUVSet(create=True)`` で作る。1回のUndoで戻せる。現在のUVセットは変えない。
        コンストラクションヒストリのあるメッシュでは ``createUVSet`` ノードを履歴へ足す。

        Args:
            name (str): 新しいUVセットの名前。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: nameが文字列以外の場合。
            ValueError: nameが空、または同じ名前のUVセットがすでにある場合。
        """
        ...
    def copyUVSet(self, source: str, target: str) -> Mesh:
        """UVセットを新しい名前へ複製し、自身を返す。

        ``cmds.polyUVSet(copy=True)`` で複製する。1回のUndoで戻せる。現在のUVセットは変えない。

        Args:
            source (str): 複製元のUVセットの名前。
            target (str): 新しいUVセットの名前。すでにある名前は不可(上書きしない)。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: source・targetが文字列以外の場合。
            ValueError: 名前が空、sourceが無い、またはtargetがすでにある場合。
        """
        ...
    def renameUVSet(self, name: str, newName: str) -> Mesh:
        """UVセットの名前を変え、自身を返す。

        ``cmds.polyUVSet(rename=True)`` で変える。1回のUndoで戻せる。現在のUVセットの名前を変えた場合は、
        新しい名前が現在のUVセットになる。

        Args:
            name (str): すでにあるUVセットの名前。
            newName (str): 新しい名前。すでにある名前は不可。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: name・newNameが文字列以外の場合。
            ValueError: 名前が空、nameが無い、またはnewNameがすでにある場合。
        """
        ...
    def deleteUVSet(self, name: str) -> Mesh:
        """UVセットを削除し、自身を返す。

        ``cmds.polyUVSet(delete=True)`` で削除する。1回のUndoで戻せる。現在のUVセットを削除すると、
        Mayaは既定のUVセット(:meth:`getUVSetNames` の先頭)を現在のUVセットにする。

        Args:
            name (str): すでにあるUVセットの名前。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: nameが文字列以外の場合。
            ValueError: nameが空、そのUVセットが無い、または既定のUVセット(``uvSet[0]``。通常 ``map1``)の場合。
                Mayaは既定のUVセットを削除できない(名前が ``map1`` でなくても同じ)。
        """
        ...
    def getColorSetNames(self) -> list[str]:
        """カラーセットの名前を取得する。

        Returns:
            list[str]: カラーセットの名前。Mayaが返す順に並ぶ。無ければ空リスト。
        """
        ...
    def getCurrentColorSet(self) -> str | None:
        """今のカラーセットの名前を取得する。

        Returns:
            str | None: 今のカラーセットの名前。カラーセットが無ければNone。
        """
        ...
    def setCurrentColorSet(self, name: str) -> Mesh:
        """今のカラーセットを切り替え、自身を返す。

        ``cmds.polyColorSet(currentColorSet=True)`` で設定する。1回のUndoで戻せる。

        Args:
            name (str): すでにあるカラーセットの名前。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: nameが文字列以外の場合。
            ValueError: nameが空、またはそのカラーセットが無い場合。
        """
        ...
    def createColorSet(self, name: str) -> Mesh:
        """空のRGBAのカラーセットを作り、自身を返す。

        ``cmds.polyColorSet(create=True)`` で作る。1回のUndoで戻せる。:meth:`createUVSet` と違い、
        Mayaの動作どおり作ったカラーセットが現在のカラーセットになる。
        コンストラクションヒストリのあるメッシュでは ``createColorSet`` ノードを履歴へ足す。

        Args:
            name (str): 新しいカラーセットの名前。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: nameが文字列以外の場合。
            ValueError: nameが空、または同じ名前のカラーセットがすでにある場合。
        """
        ...
    def copyColorSet(self, source: str, target: str) -> Mesh:
        """カラーセットを新しい名前へ複製し、自身を返す。

        ``cmds.polyColorSet(copy=True)`` で複製する。1回のUndoで戻せる。現在のカラーセットは変えない。

        Args:
            source (str): 複製元のカラーセットの名前。
            target (str): 新しいカラーセットの名前。すでにある名前は不可(上書きしない)。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: source・targetが文字列以外の場合。
            ValueError: 名前が空、sourceが無い、またはtargetがすでにある場合。
        """
        ...
    def renameColorSet(self, name: str, newName: str) -> Mesh:
        """カラーセットの名前を変え、自身を返す。

        ``cmds.polyColorSet(rename=True)`` で変える。1回のUndoで戻せる。現在のカラーセットの名前を変えた場合は、
        新しい名前が現在のカラーセットになる。

        Args:
            name (str): すでにあるカラーセットの名前。
            newName (str): 新しい名前。すでにある名前は不可。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: name・newNameが文字列以外の場合。
            ValueError: 名前が空、nameが無い、またはnewNameがすでにある場合。
        """
        ...
    def deleteColorSet(self, name: str) -> Mesh:
        """カラーセットを削除し、自身を返す。

        ``cmds.polyColorSet(delete=True)`` で削除する。1回のUndoで戻せる。現在のカラーセットを削除すると、
        Mayaは残りの先頭のカラーセットを現在のカラーセットにする(残りが無ければ現在のカラーセットは無くなる)。

        Args:
            name (str): すでにあるカラーセットの名前。

        Returns:
            Mesh: 自身。

        Raises:
            TypeError: nameが文字列以外の場合。
            ValueError: nameが空、またはそのカラーセットが無い場合。
        """
        ...
    def getBorderEdges(self) -> Edges:
        """メッシュの縁のエッジを取得する。

        縁のエッジとは、接している面が1つだけのエッジのこと。
        3つ以上の面が接している(非多様体の)エッジと、面に接していないエッジは含まない。

        Returns:
            Edges: 番号の小さい順のエッジ。縁が無ければ空。
        """
        ...
    def getBorderVertices(self) -> Vertices:
        """メッシュの縁のエッジ(:meth:`getBorderEdges`)の、両端の頂点を取得する。

        Returns:
            Vertices: 番号の小さい順の頂点。縁が無ければ空。
        """
        ...
    def _raw_points(self, worldSpace: bool) -> om2.MPointArray:
        """全頂点の位置を om2 の点列で返す(Vector へ変換しない照会用)。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間で扱う。

        Returns:
            om2.MPointArray: 頂点番号順の位置。
        """
        ...
    @staticmethod
    def _position_vertex_mapping(source, target, tolerance, world_space):
        """指定空間で許容距離内の一意な頂点対応を空間セルから求める。"""
        ...
    @staticmethod
    def _uv_vertex_mapping(source, target, uv_set, tolerance):
        """面頂点UV群が一意に一致する旧対象番号→基準番号を求める。"""
        ...
    @staticmethod
    def _face_cycles(counts, connects):
        """面の開始頂点に依存せず、面の向きと頂点接続を比較する。"""
        ...
    def _require_reorder_supported(self, fn, *, fast=...):
        """番号依存の外部接続や未対応のメッシュデータを変更前に拒否する。"""
        ...
    @staticmethod
    def _reordered_mesh_data(fn, counts, remapped, mapping):
        """シーン外のメッシュデータを作り、面順・UVと法線を移す。"""
        ...
    @staticmethod
    def _copy_reorder_details(fn, rebuilt, counts, remapped, mapping):
        """一時メッシュへ全UVセット・エッジの硬軟・固定法線を移す。"""
        ...
    @staticmethod
    def _resolve_query_point(point: Sequence[float] | om2.MPoint | om2.MVector, name: str = ...) -> om2.MPoint:
        """照会に使う位置を検証し、``om2.MPoint`` にする。

        Args:
            point (Sequence[float] | om2.MPoint | om2.MVector): 位置(cm)。
            name (str): 例外メッセージに使う引数名。

        Returns:
            om2.MPoint: XYZを写した点(wは1)。

        Raises:
            TypeError: 点の型・成分が不正な場合。
            ValueError: 成分の数が3でない、または有限でない場合。
        """
        ...
    def _require_faces(self) -> om2.MFnMesh:
        """面のあるメッシュの ``om2.MFnMesh`` を返す。

        Returns:
            om2.MFnMesh: この mesh の function set。

        Raises:
            ValueError: メッシュに面が無い場合。
        """
        ...
    def _closest_triangle(self, point: om2.MPoint, worldSpace: bool) -> tuple[om2.MFnMesh, int, list[tuple[int, float]]]:
        """最も近い面の上の点を含む三角形と、その点の重心座標を返す。

        ``MMeshIntersector`` でオブジェクト空間の最近点を探す。

        Args:
            point (om2.MPoint): 位置(cm)。
            worldSpace (bool): Trueは point をワールド空間とみなし、オブジェクト空間へ変換して探す。

        Returns:
            tuple[om2.MFnMesh, int, list[tuple[int, float]]]: function set・面の番号・三角形の
                (頂点番号, 重心座標のウェイト)の3組。

        Raises:
            ValueError: メッシュに面が無い場合。
        """
        ...
    def _resolve_uv_set(self, uvSet: str | None) -> str:
        """UVセットの指定を、実在する名前にする。

        Args:
            uvSet (str | None): UVセットの名前。Noneなら今のUVセットを使う。

        Returns:
            str: UVセットの名前。

        Raises:
            TypeError: uvSetが文字列・None以外の場合。
            ValueError: 名前が空、そのUVセットが無い、またはメッシュにUVセットが無い場合。
        """
        ...
    def _require_uv_set(self, name: str, label: str, *, exists: bool) -> None:
        """UVセットの名前の型と、その有無を検証する。

        Args:
            name (str): UVセットの名前。
            label (str): 例外メッセージに使う引数名。
            exists (bool): Trueはすでにあること、Falseはまだ無いことを求める。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: nameが文字列以外の場合。
            ValueError: nameが空、または有無が求める状態と違う場合。
        """
        ...
    def _default_uv_set(self) -> str:
        """既定のUVセット(``uvSet[0]``)の名前を返す。

        Returns:
            str: 既定のUVセットの名前。
        """
        ...
    def _resolve_color_set(self, colorSet: str | None, fn: om2.MFnMesh) -> str | None:
        """カラーセットの指定を、実在する名前にする。

        Args:
            colorSet (str | None): カラーセットの名前。Noneは現在のカラーセット。
            fn (om2.MFnMesh): この mesh の function set。

        Returns:
            str | None: カラーセットの名前。Noneを指定してカラーセットが無ければNone。

        Raises:
            TypeError: colorSetが文字列・None以外の場合。
            ValueError: 名前が空、またはそのカラーセットが無い場合。
        """
        ...
    def _require_color_set(self, name: str, label: str, *, exists: bool) -> None:
        """カラーセットの名前の型と、その有無を検証する。

        Args:
            name (str): カラーセットの名前。
            label (str): 例外メッセージに使う引数名。
            exists (bool): Trueはすでにあること、Falseはまだ無いことを求める。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: nameが文字列以外の場合。
            ValueError: nameが空、または有無が求める状態と違う場合。
        """
        ...
    def _resolve_vertex_indices(self, vertices: Component | Components | Iterable[int], count: int) -> list[int]:
        """頂点の指定を、範囲内で重複の無い番号の list にする。

        Args:
            vertices (Component | Components | Iterable[int]): 頂点の参照または番号。
            count (int): 頂点の数。

        Returns:
            list[int]: 指定順の番号。

        Raises:
            TypeError: 番号に変換できない型の場合。
            ValueError: 番号が重複している、または別のメッシュの頂点の場合。
            IndexError: 番号が範囲外の場合。
        """
        ...
    @staticmethod
    def _resolve_colors(colors: Iterable[Sequence[float] | om2.MColor], count: int) -> list[tuple[float, float, float, float]]:
        """色の列を検証し、(R, G, B, A) の float tuple の list にする。

        Args:
            colors (Iterable[Sequence[float] | om2.MColor]): 色の列。
            count (int): 必要な数。

        Returns:
            list[tuple[float, float, float, float]]: 色。Aを省略した色は1.0を補う。

        Raises:
            TypeError: 色の列・色・成分の型が不正な場合。
            ValueError: 数が合わない、成分の数が3・4以外、または有限でない場合。
        """
        ...
    def _set_vertex_colors_cmds(self, color_set: str | None, indices: list[int], values: list[tuple[float, float, float, float]]) -> None:
        """同じ色の頂点をまとめて ``cmds.polyColorPerVertex`` で書く。

        カラーセットを指定した場合は、書く間だけ現在のカラーセットを切り替えて戻す
        (``polyColorPerVertex`` は現在のカラーセットへ書くため)。

        Args:
            color_set (str | None): 書き込むカラーセット。Noneは現在のカラーセット。
            indices (list[int]): 頂点番号。
            values (list[tuple[float, float, float, float]]): indices と同じ順の色。

        Returns:
            None: 値を返さない。
        """
        ...
    def _set_vertex_colors_fast(self, fn: om2.MFnMesh, color_set: str | None, indices: list[int], values: list[tuple[float, float, float, float]]) -> None:
        """``MFnMesh.setVertexColors`` で色をまとめて書く。Undoに記録しない。

        Args:
            fn (om2.MFnMesh): この mesh の function set。
            color_set (str | None): 書き込むカラーセット。Noneは現在のカラーセット(無ければ ``colorSet1`` を作る)。
            indices (list[int]): 頂点番号。
            values (list[tuple[float, float, float, float]]): indices と同じ順の色。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: シェイプがロックされている場合。
            NotImplementedError: inMeshへの入力(コンストラクションヒストリ)がある場合。
        """
        ...
    def _mirror_plan(self, axis: str | int, ws: bool, pivot: Iterable[float], indices: Iterable[int] | None, fast: bool) -> tuple | None:
        """頂点を反転した座標を求め、書込みの計画を返す。シーンは変更しない。

        :meth:`Transform.mirrorGeometry <mlib.nodes.transform.Transform.mirrorGeometry>` が
        全Shapeを検証してから書き込むために使う。

        Args:
            axis (str | int): 反転する軸またはミラー面。
            ws (bool): Trueならワールド空間。検証済み。
            pivot (Iterable[float]): 指定空間の反転中心XYZ(cm)。
            indices (Iterable[int] | None): 頂点番号。Noneは全頂点。
            fast (bool): TrueならOpenMayaで直接書けるかも確かめる。

        Returns:
            tuple | None: ``(shape, indices, rows, ws)``。対象が無ければNone。
        """
        ...
    def _geometry_fn(self) -> om2.MFnMesh:
        """形状データを要する照会用に ``om2.MFnMesh`` を返す。

        Returns:
            om2.MFnMesh: この mesh の function set。

        Raises:
            RuntimeError: 保持する DAG パスが無効、または形状データを持たない空のシェイプの場合。
        """
        ...
