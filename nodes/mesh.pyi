# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya のメッシュシェイプを扱う。"""

import contextlib
import math
from collections import Counter, defaultdict
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..components.component import _component_of
from ..components.edge import Edge, Edges
from ..components.face import Face, Faces
from ..components.pointComponent import _mirror_plan
from ..components.uv import UV, UVs
from ..components.vertex import Vertex, Vertices
from ..components.vertexFace import VertexFace, VertexFaces
from ..core import geometryEdit
from ..core.fastWrite import require_writable
from ..core.nodeEdit import require_editable
from ..decorator import _edit_context, _pick_alias, _require_bool, preservedSelection, undoChunk, undoTransaction
from ..maths.vector import Vector, _vector_of
from ..util import _UNSET, _checked_tolerance, _finite_vector, _mirror_axis, _PointGrid, _require_choice, _world_space
from .controlPointShape import _ControlPointShape
from typing import Any, Iterable, Literal, Sequence
from mlib.components.component import Component
from mlib.components.component import Components
from mlib.nodes.node import Node
from mlib.nodes.node import Nodes
from mlib.nodes.shadingEngine import ShadingEngine
from typing import overload

_NO_DISTANCE_LIMIT: float
_INTERSECT_MERGE: float
_UNSET_COLOR_VALUES: tuple
_UNSET_COLOR: Any

def _normal_of(value: Sequence[float] | Vector, check: bool) -> Vector:
    """面頂点の法線の1つを確かめてVectorにする。

    成分の数は常に、成分が有限な数値かはcheck=Trueのときだけ確かめる。

    Args:
        value (Sequence[float] | Vector): 法線。
        check (bool): 成分が有限な数値かも確かめるか。

    Returns:
        Vector: 法線のベクトル(正規化はしない)。

    Raises:
        TypeError: 並びでない場合、またはcheck=Trueで成分に数値でないものがある場合。
        ValueError: 成分の数が3つでない場合、またはcheck=Trueで有限でない成分がある場合。
    """
    ...


class Mesh(_ControlPointShape):
    """Mayaのmeshシェイプノードを扱うクラス。"""
    def reorderVertices(self, reference: Mesh | Node | str, worldSpace: bool = ..., *, method: str = ..., uvSet: str | None = ..., tolerance: float = ..., fast: bool = ..., ws: bool = ...) -> None:
        """頂点番号の並びを、基準のメッシュに合わせる。

        UVか頂点の位置で、基準のメッシュの頂点と1対1に対応させ、その番号へ並べ替える。

        - 頂点の位置・面の順と向き・UV・法線・面のマテリアルは変わらない。エッジの番号は変わることがある。
        - スキンなど、頂点番号に頼るデータは移し替えない。すでに取得したComponentは、処理の後に取り直す。
        - UVの切れ目(シーム)は、頂点ごとの面頂点のUVの組で照らし合わせる。対応があいまいなら、何も変えずにエラーにする。

        Args:
            reference (Mesh | Node | str): 基準のMesh、またはメッシュを1つだけ持つTransform。
            uvSet (str | None): UVで照らし合わせるときのUVセットの名前(両方のメッシュで同じ名前を使う)。Noneなら、それぞれのメッシュの今のUVセット。既定はNone。
                位置で照らし合わせるときは使わない。
            tolerance (float): 許す誤差。0以上の有限な数値。UVでは成分の差、位置ではcmの距離。既定は1e-6。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。Trueなら、0でないtweakを今の位置へベイクしてから作り直す。
                FalseならUndoが有効である必要があり、0でないtweakには対応しない。
            method (str): 照らし合わせ方。``"uv"`` (既定)か ``"position"``。
            worldSpace (bool): 位置で照らし合わせるとき、Trueならワールド空間、Falseなら各Shapeのオブジェクト空間で比べる。
                既定はFalse。UVで照らし合わせるときは使わない。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            None: 値を返さない。番号の対応がすでに同じなら、作り直さずにそのまま返す(作り直すための制限の確認もしない)。

        Raises:
            TypeError: 入力の型やfast・worldSpace・methodが不正な場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: methodが ``"uv"``・``"position"`` のどちらでもない場合、対応があいまいか足りない場合、トポロジーや面の向きが合わない場合、
                または作り直すときに、入出力のヒストリ・インスタンス・リファレンス・カラーセット・クリースなどがある場合。
            RuntimeError: 作り直すときにロックされている場合、または通常の処理でUndoが無効な場合。
            NotImplementedError: 通常の処理で、頂点のtweakがあるメッシュの法線を並べ替える場合。
        """
        ...
    @overload
    def getVertices(self, indices: int) -> Vertex: ...
    @overload
    def getVertices(self, indices: Iterable[int] | None = ...) -> Vertices: ...
    @overload
    def getVertices(self, indices: int | Iterable[int] | None = ...) -> Vertex | Vertices:
        """頂点を取得する。番号を1つ渡すと頂点1つ、番号の並びを渡すと頂点のコレクションを返す。

        Args:
            indices (int | Iterable[int] | None): 0から始まる頂点番号1つ、または頂点番号の並び。Noneなら今あるすべての頂点。

        Returns:
            Vertex | Vertices: 番号1つなら、シーンの頂点を指すオブジェクト。
                並び・Noneなら頂点のコレクション(番号の順はそのままで、同じ番号は1回だけ含む)。

        Raises:
            TypeError: 番号の型が不正な場合(boolを含む)。
            IndexError: 頂点番号が範囲外の場合。
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
            TypeError: 番号の型が不正な場合(boolを含む)。
            IndexError: 頂点がそのフェースに含まれない場合、または番号が範囲外の場合。
        """
        ...
    @overload
    def getShadingEngines(self, *, perFace: Literal[True]) -> list[ShadingEngine | None]: ...
    @overload
    def getShadingEngines(self, *, perFace: Literal[False] = ...) -> Nodes[ShadingEngine]: ...
    @overload
    def getShadingEngines(self, *, perFace: bool = ...) -> Nodes[ShadingEngine] | list[ShadingEngine | None]:
        """フェースに割り当てられているShadingEngineを取得する。

        このオブジェクトが持つDAGパス(インスタンス)での割り当てを調べる。

        Args:
            perFace (bool): Trueなら、フェースごとの割り当てを、フェース番号の順のlistで返す。既定はFalse。

        Returns:
            Nodes[ShadingEngine] | list[ShadingEngine | None]: 既定では、使われているShadingEngine
                (何も割り当てられていないフェースの分は含まない)。``perFace=True`` なら、すべてのフェースの割り当て
                (何も割り当てられていないフェースはNone)。

        Raises:
            TypeError: perFaceがboolでない場合。
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
    @overload
    def getVertexNormals(self, worldSpace: bool = ..., *, angleWeighted: bool = ..., perFace: Literal[True], faceVertices: VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None = ..., lockedOnly: Literal[True], ws: bool = ...) -> list[bool]: ...
    @overload
    def getVertexNormals(self, worldSpace: bool = ..., *, angleWeighted: bool = ..., perFace: bool = ..., faceVertices: VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None = ..., lockedOnly: Literal[False] = ..., ws: bool = ...) -> list[Vector]: ...
    @overload
    def getVertexNormals(self, worldSpace: bool = ..., *, angleWeighted: bool = ..., perFace: bool = ..., faceVertices: VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None = ..., lockedOnly: bool = ..., ws: bool = ...) -> list[Vector] | list[bool]:
        """頂点ごとの法線を取得する。``perFace=True`` なら、面頂点(フェースごとの頂点)の法線を取得する。

        - 既定: 各頂点に接する面頂点の法線を平均した、頂点ごとの法線(``MFnMesh.getVertexNormals``)。
        - ``perFace=True``: 平均しない、面頂点ごとの法線。``faceVertices`` で対象を絞れる。
        - ``perFace=True, lockedOnly=True``: 法線の値でなく、面頂点の法線がロックされているかだけを返す。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間で扱う。既定はFalse。``lockedOnly=True`` では指定できない。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            angleWeighted (bool): Trueなら、隣り合う面の角度で重み付けした法線を取得する。既定はFalse。頂点ごとの法線だけに使える。
            perFace (bool): Trueなら、面頂点ごとに取得する。既定はFalse。
            faceVertices (VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None): ``perFace=True`` のときの対象。
                通し番号または(頂点, フェース)。Noneは全件。
            lockedOnly (bool): Trueなら、``perFace=True`` のとき、法線の値でなくロック状態だけを返す。既定はFalse。

        Returns:
            list[Vector] | list[bool]: 既定では、頂点番号の順に並ぶ、平均した法線。
                ``perFace=True`` なら指定順の独立した法線(全件ではフェース番号順、その面の頂点順)。
                ``lockedOnly=True`` なら同じ並びのロック状態。

        Raises:
            TypeError: worldSpace・angleWeighted・perFace・lockedOnlyがbool以外の場合、worldSpaceとwsを同時に指定した場合、番号の型が不正な場合、
                perFace=FalseでfaceVertices・lockedOnlyを指定した場合、perFace=TrueでangleWeightedを指定した場合、
                またはlockedOnly=TrueでworldSpace(ws)を指定した場合。
            ValueError: 別のメッシュのコンポーネントの場合。
            IndexError: 番号が範囲外の場合。
        """
        ...
    def setNormals(self, normals: Iterable[Iterable[float]], worldSpace: bool = ..., *, ws: bool = ..., fast: bool = ..., check: bool = ...) -> None:
        """共有法線番号を保ったままメッシュの法線リストを更新する。

        getNormalDataの先頭のリストと同じ法線番号順で指定する。割当番号は維持し、設定した法線はMayaによりロックされる。
        fast=True専用。通常Undoへは記録せず、Undo設定も変更しない。入力ヒストリ・ノードのロック・参照は、checkに関係なく拒否する。

        Args:
            normals (Iterable[Iterable[float]]): 現在の法線数と同数の3成分ベクトル。
            worldSpace (bool): Trueはワールド空間。既定False。
            ws (bool): worldSpaceの短縮名。同時指定はできない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、``inMesh`` が書き込めるか(アトリビュートのロックが無いか)を確かめて、
                問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 引数の型、または長短名の指定が不正な場合(fast・checkがbool以外の場合を含む)。
            ValueError: 法線数が違う、非有限値、ゼロベクトル、またはワールド変換が特異な場合。
            RuntimeError: メッシュが無効、ロック、または参照の場合。check=Trueで ``inMesh`` が書き込めない場合。
            NotImplementedError: fast=False、または入力ヒストリがある場合。
        """
        ...
    def getNormalData(self, worldSpace: bool = ..., *, ws: bool = ...) -> tuple[list[Vector], list[int], list[int]]:
        """法線の値と、各面頂点が参照する法線番号を取得する。

        同じ値の法線も番号が異なれば分けて保持する。法線番号は頂点番号とは別で、形状の編集後も維持されるIDではない。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            tuple[list[Vector], list[int], list[int]]: 法線番号順のVector、フェースごとの面頂点数、
                フェース番号順・各面の頂点順に連結した法線番号。すべて独立した値。法線の値はOpenMayaの取得値を保つ。

        Raises:
            TypeError: worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: 形状データが無いか無効なメッシュの場合。
        """
        ...
    def setFaceVertexNormals(self, normals: Iterable[Sequence[float] | Vector] | None = ..., worldSpace: bool = ..., *, locked: bool | None = ..., fast: bool = ..., check: bool = ..., faceVertices: VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None = ..., ws: bool = ...) -> None:
        """フェースごとの頂点の法線を設定し、ロックする。または、法線のロックだけを切り替える。

        - ``normals`` を渡すと、法線を設定してロックする(``locked`` はNoneかTrue)。
        - ``normals`` を省いて ``locked=True`` / ``locked=False`` を渡すと、法線の値は書かずに、ロックだけを掛ける/外す。
          外した後は、Mayaが形状とエッジの硬軟から法線を計算し直す。
        - ``normals`` と ``locked=False`` は同時に指定できない(外すとMayaが法線を計算し直し、設定した値が消えるため)。

        通常はpolyNormalPerVertexで設定し、Undoに記録する。fastは入力ヒストリの無いメッシュへ直接書く。
        ワールド空間の値は、保持するDAGパスを使ってオブジェクト空間へ変換する。

        Args:
            normals (Iterable[Sequence[float] | Vector] | None): 指定した面頂点と同じ数の、長さが0でないXYZ。正規化して書く。
                Noneなら値は書かない。既定はNone。
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。``normals`` を渡したときだけ指定できる。
            locked (bool | None): Trueはロック、Falseは解除。Noneは ``normals`` を渡したときのロック(Trueと同じ)。既定はNone。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、全法線が有限な数値か書き込み前に確認する。既定FalseはMayaの受理に任せる
                (成分の数はcheckに関係なく確かめる)。``normals`` を渡したときだけ指定できる。
            faceVertices (VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None): 通し番号または(頂点, フェース)。Noneは全件。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fast・check・lockedがbool以外の場合、空間・番号・法線の型が不正な場合、normalsとlockedをどちらも指定しない場合、
                normalsとlocked=Falseを同時に指定した場合、またはnormalsを渡さずにworldSpace(ws)・checkを指定した場合。
            ValueError: 法線の数や成分が不正、長さ0、ワールド変換が特異、または別のメッシュのコンポーネントの場合。
            IndexError: 番号が範囲外の場合。
            RuntimeError: メッシュがロックされているか、Mayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        ...
    def getTangentData(self, worldSpace: bool = ..., *, ws: bool = ...) -> dict[str, Any]:
        """現在のUVセットの接線のリストと、面頂点から接線番号への対応を取得する。

        UVセットは変更しない。番号は頂点番号やUV番号とは別で、編集後の維持は保証しない。
        全フェースへUVが割り当てられたメッシュを対象にする。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            ws (bool): worldSpaceの短縮名。長名と同時指定できない。

        Returns:
            dict[str, Any]: uvSet(名前)、tangents・binormals(Vectorのリスト)、counts(面ごとの頂点数)、
                indices(面の頂点順の接線番号)、rightHanded(接線番号順の右手系判定)。すべて独立した値。

        Raises:
            TypeError: 空間指定がbool以外、または長短名を同時指定した場合。
            RuntimeError: UVが未割当、形状が無効、またはMayaが接線を取得できない場合。
        """
        ...
    def getFaceVertexTangents(self, worldSpace: bool = ..., *, binormal: bool = ..., uvSet: str | None = ..., faceVertices: VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None = ..., ws: bool = ...) -> list[Vector]:
        """UVのU方向に沿う面頂点の接線を取得する。``binormal=True`` なら、UVに基づく従法線を取得する。

        従法線はMayaのgetFaceVertexBinormalを使い、UVの向きと法線から定まる方向を返す。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            binormal (bool): Trueなら、接線でなく従法線を返す。既定はFalse。
            uvSet (str | None): UVセット。Noneは現在のセット。
            faceVertices (VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None): 対象。Noneは全件。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            list[Vector]: 指定順の正規化した接線(``binormal=True`` なら従法線)。全件ではフェース番号順、その面の頂点順。

        Raises:
            TypeError: binormalがboolでない場合、または空間・UVセット・番号の型が不正な場合。
            ValueError: UVセットが無い場合、または別のメッシュのコンポーネントの場合。
            IndexError: 番号が範囲外の場合。
            RuntimeError: UVが未割当・縮退しているか、接線(従法線)を求められない場合。
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
    @overload
    def getShells(self, *, uv: Literal[True], uvSet: str | None = ...) -> list[list[int]]: ...
    @overload
    def getShells(self, *, uv: Literal[False] = ..., uvSet: str | None = ...) -> list[Vertices]: ...
    @overload
    def getShells(self, *, uv: bool = ..., uvSet: str | None = ...) -> list[Vertices] | list[list[int]]:
        """エッジでつながった頂点のまとまり(シェル)を取得する。``uv=True`` なら、UVでつながったUVのまとまり(UVシェル)を取得する。

        UVシェルは ``MFnMesh.getUvShellsIds`` を使う。形状のシェルと違い、UVの切れ目で分かれる。

        Args:
            uv (bool): Trueなら、UVシェルを返す。既定はFalse。
            uvSet (str | None): ``uv=True`` のときのUVセットの名前。Noneなら今のUVセットを使う。

        Returns:
            list[Vertices] | list[list[int]]: 既定では、シェルごとの頂点(番号の小さい順)。シェルは、それぞれのいちばん小さい頂点番号の順に並ぶ。
                どこにもつながっていない頂点は、1頂点だけのシェルになる。
                ``uv=True`` なら、シェルごとのUV番号(小さい順)。シェルは、それぞれのいちばん小さいUV番号の順に並ぶ。
                UVが無ければ空リスト。番号は指定したUVセットのもの
                (:class:`~mlib.components.uv.UVs` は今のUVセットを指すので、別のUVセットの番号はintのlistで返す)。

        Raises:
            TypeError: uvがboolでない場合、uvSetが文字列・None以外の場合、またはuv=FalseでuvSetを指定した場合。
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
    def getTopology(self) -> tuple[list[int], list[int]]:
        """フェースごとの頂点の数と、頂点番号の並びを取得する。

        ``om2.MFnMesh.getVertices()`` と同じ値。メッシュを作り直す(``MFnMesh.create`` など)ときの
        polygonCounts・polygonConnectsに当たる。

        Returns:
            tuple[list[int], list[int]]: (フェース番号の順の各フェースの頂点の数, それらをつなげた頂点番号の並び)。
        """
        ...
    def getMirrorVertexMap(self, axis: str | int = ..., worldSpace: bool = ..., *, tolerance: float = ..., ws: bool = ...) -> dict[int, int]:
        """頂点ごとに、位置を軸で反転した反対側の頂点を取得する。

        反転した位置から ``tolerance`` 以内で、いちばん近い頂点を反対側とする。トポロジーは見ない。

        Args:
            axis (str | int): 反転する軸 ``"x"``・``"y"``・``"z"``、ミラー面 ``"YZ"``・``"XZ"``・``"XY"``、または0・1・2。既定は ``"x"``。
                面の文字の順や大文字・小文字は問わない(:meth:`mirror` と同じ)。
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
    def getClosestVertices(self, points: Iterable[Sequence[float] | om2.MPoint | om2.MVector], worldSpace: bool = ..., *, ws: bool = ...) -> list[int]:
        """点ごとに、いちばん近い頂点の番号を取得する。

        頂点の位置に等間隔の格子を作って探す(面の上でいちばん近い点ではない)。
        点1つの頂点は ``mesh.getVertices(mesh.getClosestVertices([point])[0])`` で取得できる。

        Args:
            points (Iterable[Sequence[float] | om2.MPoint | om2.MVector]): 位置(cm)の並び。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間で扱う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[int]: いちばん近い頂点の番号。pointsと同じ順に並ぶ(別の点が同じ頂点になることがあるので、
                重なりを除く :class:`~mlib.components.vertex.Vertices` でなく番号のlistで返す)。

        Raises:
            TypeError: 点の並び・点の型・成分が不正な場合、worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 成分の数が3でないか有限でない場合、またはメッシュに頂点が無い場合。
            RuntimeError: 形状のデータを持たない空のシェイプ(``mlib.createNode("mesh")`` の直後など)の場合。
        """
        ...
    @overload
    def getEdges(self, indices: int) -> Edge: ...
    @overload
    def getEdges(self, indices: Iterable[int] | None = ...) -> Edges: ...
    @overload
    def getEdges(self, indices: int | Iterable[int] | None = ...) -> Edge | Edges:
        """エッジを取得する。番号を1つ渡すとエッジ1つ、番号の並びを渡すとエッジのコレクションを返す。

        Args:
            indices (int | Iterable[int] | None): 0から始まる番号1つ、または番号の並び。Noneなら今あるすべてのエッジ。

        Returns:
            Edge | Edges: 番号1つなら、シーンのエッジを指すオブジェクト。並び・Noneならエッジのコレクション(同じ番号は1回だけ含む)。

        Raises:
            TypeError: 番号の型が不正な場合(boolを含む)。
            IndexError: 番号が範囲外の場合。
        """
        ...
    @overload
    def getFaces(self, indices: int) -> Face: ...
    @overload
    def getFaces(self, indices: Iterable[int] | None = ...) -> Faces: ...
    @overload
    def getFaces(self, indices: int | Iterable[int] | None = ...) -> Face | Faces:
        """フェースを取得する。番号を1つ渡すとフェース1つ、番号の並びを渡すとフェースのコレクションを返す。

        Args:
            indices (int | Iterable[int] | None): 0から始まる番号1つ、または番号の並び。Noneなら今あるすべてのフェース。

        Returns:
            Face | Faces: 番号1つなら、シーンのフェースを指すオブジェクト。並び・Noneならフェースのコレクション(同じ番号は1回だけ含む)。

        Raises:
            TypeError: 番号の型が不正な場合(boolを含む)。
            IndexError: 番号が範囲外の場合。
        """
        ...
    @overload
    def getUVs(self, indices: int) -> UV: ...
    @overload
    def getUVs(self, indices: Iterable[int] | None = ...) -> UVs: ...
    @overload
    def getUVs(self, indices: int | Iterable[int] | None = ...) -> UV | UVs:
        """UVを取得する。番号を1つ渡すとUV1つ、番号の並びを渡すとUVのコレクションを返す。

        Args:
            indices (int | Iterable[int] | None): 0から始まる番号1つ、または番号の並び。Noneなら今あるすべてのUV。

        Returns:
            UV | UVs: 番号1つなら、シーンのUVを指すオブジェクト。並び・NoneならUVのコレクション(同じ番号は1回だけ含む)。

        Raises:
            TypeError: 番号の型が不正な場合(boolを含む)。
            IndexError: 番号が範囲外の場合。
        """
        ...
    def getUVData(self, *, uvSet: str | None = ...) -> tuple[list[tuple[float, float]], list[int], list[int]]:
        """UV座標と、フェースの各コーナーに割り当てられたUV番号を取得する。

        Args:
            uvSet (str | None): UVセット。Noneは現在のセット。

        Returns:
            tuple[list[tuple[float, float]], list[int], list[int]]: UV番号順の(U, V)、フェースごとのUV数、
                フェースの頂点順に連結したUV番号。未割当面の数は0。未使用のUVも座標列に含む。すべて独立した値。

        Raises:
            TypeError: uvSetが文字列・None以外の場合。
            ValueError: UVセットが無い場合。
        """
        ...
    def setUVData(self, uvs: Iterable[Sequence[float]], counts: Iterable[int], indices: Iterable[int], *, fast: bool = ..., uvSet: str | None = ...) -> None:
        """UVセットの全座標と、フェースの各コーナーへの割り当てを置き換える。

        UV番号は渡した座標の順になる。通常は一時形状からpolyTransferでUVを転送し、Undoに記録する。
        入力ヒストリがある場合はpolyTransferノードを追加する。他のUVセットは内容を保ち、位置・法線・色・マテリアルは転送しない。
        全UVセットの実行時の内容を転送するため、その後の上流ヒストリでのUV変更は反映しなくなる。
        fastは入力ヒストリの無いメッシュに限る。頂点/面の番号は変えないが、取得済みUVの番号の意味は変わり得る。

        Args:
            uvs (Iterable[Sequence[float]]): UV番号順の(U, V)。有限な数値。未使用のUVも指定できる。
            counts (Iterable[int]): フェース番号順のUV数。各値は0(未割当)、またはその面の頂点数。
            indices (Iterable[int]): フェースの頂点順に連結したUV番号。長さはcountsの合計。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            uvSet (str | None): 既存のUVセット。Noneは現在のセット。現在のセットは変更しない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合、または値・番号・UVセットの型が不正な場合。
            ValueError: 数・範囲・座標が不正、UVセットが無い、またはインスタンス別UVセットの場合。
            RuntimeError: メッシュがロックされている、リファレンスである、またはMayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        ...
    def getNumUVs(self) -> int:
        """今のUVセットのUVの数を取得する。

        Returns:
            int: UVの数。
        """
        ...
    @overload
    def getClosestPoint(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, what: Literal["point"] = ..., uvSet: str | None = ..., ws: bool = ...) -> tuple[Vector, int]: ...
    @overload
    def getClosestPoint(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, what: Literal["normal"], uvSet: str | None = ..., ws: bool = ...) -> Vector: ...
    @overload
    def getClosestPoint(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, what: Literal["uv"], uvSet: str | None = ..., ws: bool = ...) -> tuple[float, float]: ...
    @overload
    def getClosestPoint(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, what: str = ..., uvSet: str | None = ..., ws: bool = ...) -> tuple[Vector, int] | Vector | tuple[float, float]:
        """指定した位置にいちばん近い、メッシュの面の上の点を取得する。``what`` で、その点の法線かUVを選べる。

        - ``"point"`` (既定): ``MFnMesh.getClosestPoint`` を使う。頂点だけを比べる :meth:`getClosestVertices` と違い、
          面の内部・エッジの上の点も返す。
        - ``"normal"``: いちばん近い点を含む三角形の、3つの面頂点の法線(ハードエッジ・ソフトエッジを反映した、表示に使う法線)を、
          その点の重心座標で補間して長さ1にする。``MFnMesh.getClosestNormal`` が返す面の法線ではない。
          ハードエッジだけのメッシュ(立方体など)では、面の法線と同じ向きになる。
        - ``"uv"``: いちばん近い点を含む三角形の、3つの面頂点のUVを、その点の重心座標で補間する
          (``closestPointOnMesh`` ノードの ``parameterU/V`` と同じ値)。
          ``MFnMesh.getUVAtPoint`` は、面の境目の近くで隣の面のUVを返すことがあるので使わない。

        Args:
            point (Sequence[float] | om2.MPoint | om2.MVector): 位置(cm)。
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。入力と戻り値の両方に使う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            what (str): 取得するもの。``"point"``・``"normal"``・``"uv"``。既定は ``"point"``。
            uvSet (str | None): ``what="uv"`` のときのUVセットの名前。Noneなら今のUVセットを使う。

        Returns:
            tuple[Vector, int] | Vector | tuple[float, float]: ``"point"`` は面の上でいちばん近い点(cm)と、その点を含む面の番号。
                ``"normal"`` は長さ1の法線(ワールド空間では、オブジェクト空間の法線をマトリクスの逆転置で変換する)。
                ``"uv"`` は (u, v)。

        Raises:
            TypeError: 点の型や成分が不正な場合、whatが文字列でない場合、uvSetが文字列・None以外の場合、
                what="uv"以外でuvSetを指定した場合、worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 成分の数が3でないか有限でない場合、whatが対応していない名前の場合、UVセットが無い場合、またはメッシュに面が無い場合。
            RuntimeError: 形状のデータを持たない空のシェイプ(``mlib.createNode("mesh")`` の直後など)の場合、
                またはwhat="uv"で、いちばん近い面にUVが割り当てられていない場合。

        Note:
            ``"normal"``・``"uv"`` のいちばん近い点は、オブジェクト空間で探す(``MMeshIntersector``)。XYZで違うスケールが掛かった
            メッシュをワールド空間で調べると、``"point"`` と違う面の点になることがある。
        """
        ...
    def intersect(self, origin: Sequence[float] | om2.MPoint | om2.MVector, direction: Sequence[float] | om2.MVector, worldSpace: bool = ..., *, maxDistance: float | None = ..., ws: bool = ...) -> list[tuple[Vector, int, float]]:
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
    def getPointsAtUV(self, u: float, v: float, worldSpace: bool = ..., *, uvSet: str | None = ..., tolerance: float = ..., ws: bool = ...) -> list[tuple[int, Vector]]:
        """UV座標に対応する全フェースの3D位置を取得する。

        UVが重なる面も含め、1フェースにつき最大1点を返す。境界上で同じ位置になっても、別の面の結果は除かない。

        Args:
            u (float): U座標。
            v (float): V座標。
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            uvSet (str | None): UVセット。Noneは現在のセット。
            tolerance (float): UV座標の許容誤差。0以上の有限値。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            list[tuple[int, Vector]]: (フェース番号, 位置(cm))。フェース番号の昇順。該当面が無ければ空。

        Raises:
            TypeError: 座標・許容誤差・空間・UVセットの型が不正な場合。
            ValueError: 座標・許容誤差が不正か、UVセットが無い場合。
        """
        ...
    def removeFaceVertexColors(self, *, fast: bool = ..., colorSet: str | None = ..., faceVertices: VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None = ...) -> None:
        """指定した面頂点のカラー割り当てを解除する。

        黒や透明を設定せず、getVertexColors(perFace=True)でNoneになる状態へ戻す。カラーセットと他のコーナーの色は残す。
        通常はUndoに記録する。入力ヒストリがある場合は、指定セットのpolyColorPerVertexから
        メッシュまでがpolyMoveVertexだけの連鎖に限る。fastは入力ヒストリの無いメッシュに限る。
        現在のカラーセットは復元する。colorSet=Noneでセットが無い場合や対象が空の場合は何もしない。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            colorSet (str | None): 既存のカラーセット。Noneは現在のセット。
            faceVertices (VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None): 通し番号または(頂点, フェース)。Noneは全件。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合、またはセット・番号の型が不正な場合。
            ValueError: 指定セットが無いか、別のメッシュのコンポーネントの場合。
            IndexError: 番号が範囲外の場合。
            RuntimeError: メッシュがロック・リファレンス、通常経路で未対応のヒストリ、またはMayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        ...
    def getVertexColors(self, *, perFace: bool = ..., colorSet: str | None = ..., faceVertices: VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None = ...) -> list[tuple[float, float, float, float] | None]:
        """頂点ごとの色を取得する。``perFace=True`` なら、面頂点(フェースごとの頂点)の色を平均せずに取得する。

        既定では ``MFnMesh.getVertexColors`` を使う。面ごとに違う色を持つ頂点(面頂点の色)は、それらの平均になる。

        Args:
            perFace (bool): Trueなら、面頂点ごとに取得する。既定はFalse。
            colorSet (str | None): カラーセットの名前。Noneなら今のカラーセットを使う。
            faceVertices (VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None): ``perFace=True`` のときの対象。Noneは全件。

        Returns:
            list[tuple[float, float, float, float] | None]: (R, G, B, A)。色の無い要素はNone。
                既定では頂点番号の順。``perFace=True`` なら指定順(全件ではフェース番号順、その面の頂点順)。
                colorSetにNoneを指定し、カラーセットが1つも無い場合はすべてNone。

        Raises:
            TypeError: perFaceがboolでない場合、colorSetが文字列・None以外の場合、番号の型が不正な場合、
                またはperFace=FalseでfaceVerticesを指定した場合。
            ValueError: 指定した名前のカラーセットが無い場合、または別のメッシュのコンポーネントの場合。
            IndexError: 番号が範囲外の場合。
        """
        ...
    def setVertexColors(self, colors: Iterable[Sequence[float] | om2.MColor], *, perFace: bool = ..., vertices: Component | Components | Iterable[int] | None = ..., faceVertices: VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None = ..., colorSet: str | None = ..., fast: bool = ..., check: bool = ...) -> None:
        """頂点ごとの色を設定する。``perFace=True`` なら、面頂点(フェースごとの頂点)の色を設定する。

        - 既定: 頂点のすべての面頂点を同じ色にする。通常は ``cmds.polyColorPerVertex`` で、同じ色の頂点をまとめて
          色ごとに1回ずつ書き、1回のUndoにまとめる。色の種類が多いと時間がかかる(目安は1色あたり約1ms)。
          ``fast=True`` なら ``MFnMesh.setVertexColors`` で1回で書き、Undoには記録しない。
        - ``perFace=True``: ほかの面にある同じ頂点の色は変更しない。通常はpolyColorPerVertexで色ごとに書き、Undoにまとめる。
          通常経路で複数色の更新途中にMayaが失敗した場合、先に設定した色は残る。対象が空なら何もしない。

        Args:
            colors (Iterable[Sequence[float] | om2.MColor]): 色。各色は (R, G, B) か (R, G, B, A) の
                有限な数値(Aを省略すると1.0)。対象と同じ数だけ渡す。
            perFace (bool): Trueなら、面頂点ごとに設定する。既定はFalse。
            vertices (Component | Components | Iterable[int] | None): perFace=Falseのときに書き込む頂点の番号。Noneなら全頂点。
                同じ番号を2回指定できない。指定した順にcolorsと対応する。
            faceVertices (VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None): perFace=Trueのときの対象。Noneは全件。
            colorSet (str | None): カラーセットの名前。Noneなら今のカラーセットを使う(無ければMayaが
                ``colorSet1`` を作る)。名前を指定する場合は、そのカラーセットがすでにある必要がある。
                今のカラーセットは変えない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込むカラーセットの値(``colorSet[].colorSetPoints``)がロック・入力の接続で
                書き込めないかを確かめて、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く。
                カラーセットがまだ無い(Mayaが作る)ときは確かめるものが無い。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: perFace・fast・checkがbool以外の場合、colorSetが文字列・None以外の場合、色や番号の型が不正な場合、
                perFace=Trueでverticesを指定した場合、またはperFace=FalseでfaceVerticesを指定した場合。
            ValueError: 色の数が対象の数と合わない場合、成分の数が3・4以外か有限でない場合、頂点が重なっている場合、
                別のメッシュのコンポーネントを渡した場合、またはカラーセットが無い場合。
            IndexError: 番号が範囲外の場合。
            RuntimeError: シェイプがロックされているかリファレンスの場合(Mayaはロックを見ずに書くため、
                fastに関係なく書く前に確かめる)、check=Trueでカラーセットの値がロック・入力の接続などで書き込めない場合、
                またはMayaが書き込みを拒否した場合。
            NotImplementedError: fast=Trueで、inMeshへの入力(コンストラクションヒストリ)がある場合。

        Note:
            通常の処理では、コンストラクションヒストリのあるメッシュに ``polyColorPerVertex`` ノードをヒストリとして足す。
        """
        ...
    def getSetNames(self, *, kind: str = ...) -> list[str]:
        """UVセットの名前を取得する。``kind="color"`` なら、カラーセットの名前を取得する。

        Args:
            kind (str): 扱うセットの種類。``"uv"`` (既定)はUVセット、``"color"`` はカラーセット。

        Returns:
            list[str]: セットの名前。Mayaが返す順に並ぶ。UVセットは先頭が既定のUVセット(``uvSet[0]``)。
                カラーセットが無ければ空リスト。

        Raises:
            TypeError: kindが文字列でない場合。
            ValueError: kindが ``"uv"``・``"color"`` のどちらでもない場合。
        """
        ...
    def getCurrentSet(self, *, kind: str = ...) -> str | None:
        """今のUVセットの名前を取得する。``kind="color"`` なら、今のカラーセットの名前を取得する。

        Args:
            kind (str): 扱うセットの種類。``"uv"`` (既定)はUVセット、``"color"`` はカラーセット。

        Returns:
            str | None: 今のセットの名前。UVセットは必ず名前を返す。カラーセットが無ければNone。

        Raises:
            TypeError: kindが文字列でない場合。
            ValueError: kindが ``"uv"``・``"color"`` のどちらでもない場合。
        """
        ...
    def setCurrentSet(self, name: str, *, kind: str = ...) -> None:
        """今のUVセットを切り替える。``kind="color"`` なら、今のカラーセットを切り替える。

        ``cmds.polyUVSet(currentUVSet=True)``・``cmds.polyColorSet(currentColorSet=True)`` で設定する。1回のUndoで戻せる。

        Args:
            name (str): すでにあるセットの名前。
            kind (str): 扱うセットの種類。``"uv"`` (既定)はUVセット、``"color"`` はカラーセット。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: nameが文字列以外の場合、またはkindが文字列でない場合。
            ValueError: kindが ``"uv"``・``"color"`` のどちらでもない場合、nameが空、またはそのセットが無い場合。
        """
        ...
    def createSet(self, name: str, *, kind: str = ...) -> None:
        """空のUVセットを作る。``kind="color"`` なら、空のRGBAのカラーセットを作る。

        ``cmds.polyUVSet(create=True)``・``cmds.polyColorSet(create=True)`` で作る。1回のUndoで戻せる。

        - UVセット: 現在のUVセットは変えない。コンストラクションヒストリのあるメッシュでは ``createUVSet`` ノードを履歴へ足す。
        - カラーセット: Mayaの動作どおり、作ったカラーセットが現在のカラーセットになる。
          コンストラクションヒストリのあるメッシュでは ``createColorSet`` ノードを履歴へ足す。

        Args:
            name (str): 新しいセットの名前。
            kind (str): 扱うセットの種類。``"uv"`` (既定)はUVセット、``"color"`` はカラーセット。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: nameが文字列以外の場合、またはkindが文字列でない場合。
            ValueError: kindが ``"uv"``・``"color"`` のどちらでもない場合、nameが空、または同じ名前のセットがすでにある場合。
        """
        ...
    def copySet(self, source: str, target: str, *, kind: str = ..., overwrite: bool = ...) -> None:
        """UVセットを新しい名前へ複製する。``kind="color"`` なら、カラーセットを複製する。

        ``cmds.polyUVSet(copy=True)``・``cmds.polyColorSet(copy=True)`` で複製する。
        UVセットで ``overwrite=True`` のとき、targetがすでにあれば、
        ``cmds.polyCopyUV(uvSetNameInput=source, uvSetName=target, constructionHistory=False)`` で
        targetのUVをsourceの値で置き換える(コンストラクションヒストリは作らない)。
        1回のUndoで戻せる。現在のセットと選択は変えない。fast引数は持たない(Mayaのコマンドの1回で処理するため)。

        Args:
            source (str): 複製元のセットの名前。
            target (str): 複製先のセットの名前。overwrite=Falseなら、すでにある名前は不可(上書きしない)。
            kind (str): 扱うセットの種類。``"uv"`` (既定)はUVセット、``"color"`` はカラーセット。
            overwrite (bool): Trueなら、すでにあるtargetのUVを置き換える。既定はFalse。カラーセットでは指定できない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: source・targetが文字列以外の場合、kindが文字列でない場合、overwriteがboolでない場合、
                またはkind="color"とoverwrite=Trueを同時に指定した場合。
            ValueError: kindが ``"uv"``・``"color"`` のどちらでもない場合、名前が空の場合、sourceが無い場合、sourceとtargetが同じ場合、
                またはoverwrite=Falseでtargetがすでにある場合。
        """
        ...
    def renameSet(self, name: str, newName: str, *, kind: str = ...) -> None:
        """UVセットの名前を変える。``kind="color"`` なら、カラーセットの名前を変える。

        ``cmds.polyUVSet(rename=True)``・``cmds.polyColorSet(rename=True)`` で変える。1回のUndoで戻せる。
        現在のセットの名前を変えた場合は、新しい名前が現在のセットになる。

        Args:
            name (str): すでにあるセットの名前。
            newName (str): 新しい名前。すでにある名前は不可。
            kind (str): 扱うセットの種類。``"uv"`` (既定)はUVセット、``"color"`` はカラーセット。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: name・newNameが文字列以外の場合、またはkindが文字列でない場合。
            ValueError: kindが ``"uv"``・``"color"`` のどちらでもない場合、名前が空、nameが無い、またはnewNameがすでにある場合。

        Note:
            ``kind="color"`` で色を持つカラーセットの名前を変えてUndoすると、名前は戻るが、面頂点の色がすべて未設定になり、
            セットの並びの順も変わる(``cmds.polyColorSet(rename=True)`` のUndoの性質で、cmdsだけでも同じMayaの制限)。
            コピーと削除で代わりに行うと、色の表現(RGB・RGBA・A)が保てないため、この形のままにしている。
        """
        ...
    def deleteSet(self, name: str, *, kind: str = ...) -> None:
        """UVセットを削除する。``kind="color"`` なら、カラーセットを削除する。

        ``cmds.polyUVSet(delete=True)``・``cmds.polyColorSet(delete=True)`` で削除する。1回のUndoで戻せる。

        - UVセット: 現在のUVセットを削除すると、Mayaは既定のUVセット(:meth:`getSetNames` の先頭)を現在のUVセットにする。
          既定のUVセットは削除できない。
        - カラーセット: 現在のカラーセットを削除すると、Mayaは残りの先頭のカラーセットを現在のカラーセットにする
          (残りが無ければ現在のカラーセットは無くなる)。

        Args:
            name (str): すでにあるセットの名前。
            kind (str): 扱うセットの種類。``"uv"`` (既定)はUVセット、``"color"`` はカラーセット。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: nameが文字列以外の場合、またはkindが文字列でない場合。
            ValueError: kindが ``"uv"``・``"color"`` のどちらでもない場合、nameが空、そのセットが無い、または既定のUVセット(``uvSet[0]``。通常 ``map1``)の場合。
                Mayaは既定のUVセットを削除できない(名前が ``map1`` でなくても同じ)。
        """
        ...
    @overload
    def getBorder(self, *, type: Literal["edge"] = ...) -> Edges: ...
    @overload
    def getBorder(self, *, type: Literal["vertex"]) -> Vertices: ...
    @overload
    def getBorder(self, *, type: str = ...) -> Edges | Vertices:
        """メッシュの縁のエッジを取得する。``type="vertex"`` なら、縁のエッジの両端の頂点を取得する。

        縁のエッジとは、接している面が1つだけのエッジのこと。
        3つ以上の面が接している(非多様体の)エッジと、面に接していないエッジは含まない。

        Args:
            type (str): 取得するコンポーネントの種類。``"edge"``・``"vertex"``。既定は ``"edge"``。

        Returns:
            Edges | Vertices: 番号の小さい順のエッジ(``type="vertex"`` なら頂点)。縁が無ければ空。

        Raises:
            TypeError: typeが文字列でない場合。
            ValueError: typeが対応していない名前の場合。
        """
        ...
    def getHoles(self) -> list[tuple[int, list[int]]]:
        """フェース内部の穴を構成する頂点列を取得する。

        メッシュの外周や欠損面、polyHoleで非表示にした面は対象にしない。

        Returns:
            list[tuple[int, list[int]]]: (フェース番号, 内周の頂点番号列)。頂点はメッシュ全体の番号で、
                穴と頂点の並びはOpenMayaの順を保つ。穴が無ければ空のリスト。すべて独立した値。

        Raises:
            RuntimeError: 形状データが無いか無効なメッシュの場合。
        """
        ...
    @staticmethod
    def _color_kind(kind: str) -> bool:
        """セット操作のkindを確かめ、カラーセットかを返す。

        Args:
            kind (str): ``"uv"`` か ``"color"``。

        Returns:
            bool: カラーセットならTrue、UVセットならFalse。

        Raises:
            TypeError: kindが文字列でない場合。
            ValueError: kindが ``"uv"``・``"color"`` のどちらでもない場合。
        """
        ...
    def _resolve_face_vertices(self, values: VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None) -> VertexFaces:
        """面頂点の指定を、同じメッシュのVertexFacesへ解決する。

        Args:
            values (VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None): 対象。

        Returns:
            VertexFaces: 指定順の面頂点。重複はComponentsの規則どおり除く。
        """
        ...
    def _require_face_vertex_edit(self, method: str, fast: bool) -> None:
        """面頂点データの書き込み先と、fastのヒストリ制限を確認する。

        Args:
            method (str): エラーに示す公開メソッド名。
            fast (bool): OpenMayaで直接書くか。

        Returns:
            None: 値を返さない。
        """
        ...
    def _set_face_vertex_normals_fast(self, components: VertexFaces, values: list[Vector]) -> None:
        """面頂点の法線をOpenMayaで直接書く。

        Args:
            components (VertexFaces): 確認済みの対象。
            values (list[Vector]): オブジェクト空間の法線。

        Returns:
            None: 値を返さない。
        """
        ...
    def _set_face_vertex_normals_locked_fast(self, components: VertexFaces, state: bool) -> None:
        """面頂点法線のロックをOpenMayaで切り替える。

        Args:
            components (VertexFaces): 確認済みの対象。
            state (bool): ロックするか。

        Returns:
            None: 値を返さない。
        """
        ...
    def _face_vertex_directions(self, faceVertices: VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None, worldSpace: bool, uvSet: str | None, binormal: bool) -> list[Vector]:
        """UVの対応を確認し、面頂点の接線または従法線を返す。

        Args:
            faceVertices (VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None): 対象。
            worldSpace (bool): ワールド空間で求めるか。
            uvSet (str | None): UVセット。
            binormal (bool): Trueは従法線、Falseは接線。

        Returns:
            list[Vector]: 指定順の正規化した方向。
        """
        ...
    def _resolve_uv_data(self, uvs: Iterable[Sequence[float]], counts: Iterable[int], indices: Iterable[int]) -> tuple[list[tuple[float, float]], list[int], list[int]]:
        """UVの座標数と、面ごとの割り当て数・番号を検証する。

        Args:
            uvs (Iterable[Sequence[float]]): UV座標。
            counts (Iterable[int]): 面ごとのUV数。
            indices (Iterable[int]): コーナーに割り当てるUV番号。

        Returns:
            tuple[list[tuple[float, float]], list[int], list[int]]: 確認済みの値。
        """
        ...
    @staticmethod
    def _set_uv_data_fast(fn: om2.MFnMesh, name: str, values: list[tuple[float, float]], counts: list[int], indices: list[int]) -> None:
        """UVセットの座標と割り当てをOpenMayaで置き換える。

        Args:
            fn (om2.MFnMesh): 対象メッシュ。
            name (str): UVセット名。
            values (list[tuple[float, float]]): UV座標。
            counts (list[int]): 面ごとのUV数。
            indices (list[int]): UV番号。

        Returns:
            None: 値を返さない。
        """
        ...
    def _set_uv_data_cmds(self, name: str, values: list[tuple[float, float]], counts: list[int], indices: list[int]) -> None:
        """一時形状に用意したUVを標準コマンドで転送し、Undoに記録する。

        Args:
            name (str): UVセット名。
            values (list[tuple[float, float]]): UV座標。
            counts (list[int]): 面ごとのUV数。
            indices (list[int]): UV番号。

        Returns:
            None: 値を返さない。
        """
        ...
    def _require_color_removal_history(self, color_set: str) -> None:
        """カラー解除を確認したヒストリの連鎖か検証する。

        Args:
            color_set (str): 解除するカラーセット。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 入力に指定セットのカラー編集が無いか、途中に未対応ノードがある場合。
        """
        ...
    def _remove_face_vertex_colors_cmds(self, color_set: str, components: VertexFaces) -> None:
        """現在のカラーセットを復元しながら、標準コマンドで色の割り当てを解除する。

        Args:
            color_set (str): 解除するカラーセット。
            components (VertexFaces): 対象。

        Returns:
            None: 値を返さない。
        """
        ...
    def _remove_face_vertex_colors_fast(self, fn: om2.MFnMesh, color_set: str, components: VertexFaces) -> None:
        """現在のカラーセットを復元しながら、OpenMayaで色の割り当てを解除する。

        Args:
            fn (om2.MFnMesh): 対象メッシュ。
            color_set (str): 解除するカラーセット。
            components (VertexFaces): 対象。

        Returns:
            None: 値を返さない。
        """
        ...
    def _set_face_vertex_colors_cmds(self, color_set: str | None, components: VertexFaces, values: list[tuple[float, float, float, float]]) -> None:
        """現在のカラーセットを一時的に選び、面頂点の色を標準コマンドで設定する。

        Args:
            color_set (str | None): カラーセット。
            components (VertexFaces): 対象。
            values (list[tuple[float, float, float, float]]): RGBA値。

        Returns:
            None: 値を返さない。
        """
        ...
    def _set_face_vertex_colors_fast(self, fn: om2.MFnMesh, color_set: str | None, components: VertexFaces, values: list[tuple[float, float, float, float]]) -> None:
        """面頂点の色をOpenMayaで設定する。

        ``MFnMesh.setFaceVertexColors`` は、色の無いカラーセットへ書くと、ほかの面頂点へ今のカラーセットの色を写すため使わない。
        カラーセットの色の並びの末尾へ新しい色を足し、対象の面頂点だけをその色に割り当てる(ほかの面頂点の割り当ては変えない)。

        Args:
            fn (om2.MFnMesh): 対象メッシュ。
            color_set (str | None): カラーセット。Noneなら今のカラーセット。
            components (VertexFaces): 対象。
            values (list[tuple[float, float, float, float]]): RGBA値。

        Returns:
            None: 値を返さない。
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
    def _set_points(self, values: list[tuple[float, float, float]], ws: bool, fast: bool, check: bool) -> None:
        """確かめてある点の並びを、今と位置が違う頂点だけ書き込む。

        Args:
            values (list[tuple[float, float, float]]): 頂点番号の順のXYZ(cm)。
            ws (bool): Trueならワールド空間。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: 点の数が頂点数と合わない場合。
        """
        ...
    def _point_components(self, indices: Iterable[int] | None) -> Vertices:
        """頂点のコレクションを返す。

        Args:
            indices (Iterable[int] | None): 頂点番号。Noneは全頂点。

        Returns:
            Vertices: 頂点のコレクション。
        """
        ...
    @staticmethod
    def _position_vertex_mapping(source, target, tolerance, world_space):
        """指定空間で許容距離内の一意な頂点対応を空間セルから求める。"""
        ...
    @staticmethod
    def _uv_vertex_mapping(source, target, uv_set, tolerance):
        """面頂点UV群が一意に一致する旧対象番号→基準番号を求める。uv_setがNoneなら、それぞれのメッシュの今のUVセットを使う。"""
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
    def _require_set(self, name: str, label: str, color: bool, *, exists: bool) -> None:
        """UVセットかカラーセットの名前の型と、その有無を検証する。

        Args:
            name (str): セットの名前。
            label (str): 例外メッセージに使う引数名。
            color (bool): Trueはカラーセット、FalseはUVセット。
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
    def _require_color_set_writable(self, name: str | None) -> None:
        """カラーセットの値のアトリビュート(``colorSet[].colorSetPoints``)へ書き込めるかを確かめる。

        Args:
            name (str | None): カラーセットの名前。Noneなら確かめない(まだカラーセットが無い)。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ロック・入力の接続などで書き込めない場合。
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
    def _mirror_plan(self, axis: str | int, ws: bool, pivot: Iterable[float], indices: Iterable[int] | None, fast: bool, check: bool = ...) -> tuple | None:
        """頂点を反転した座標を求め、書込みの計画を返す。シーンは変更しない。

        :meth:`Transform.mirrorGeometry <mlib.nodes.transform.Transform.mirrorGeometry>` が
        全Shapeを検証してから書き込むために使う。

        Args:
            axis (str | int): 反転する軸またはミラー面。
            ws (bool): Trueならワールド空間。検証済み。
            pivot (Iterable[float]): 指定空間の反転中心XYZ(cm)。
            indices (Iterable[int] | None): 頂点番号。Noneは全頂点。
            fast (bool): TrueならOpenMayaで直接書けるかも確かめる。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

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
