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

#: :meth:`Mesh.intersect` で maxDistance=None のときに Maya へ渡す最大距離(単精度で表せる大きな値)。
_NO_DISTANCE_LIMIT = 1.0e30
#: :meth:`Mesh.intersect` で同じ面の交点を1つにまとめる距離の差(cm。単精度の誤差を見込む)。
_INTERSECT_MERGE = 1.0e-4
#: 色の無い頂点を表す、``MFnMesh.getVertexColors`` の既定の色の成分。
_UNSET_COLOR_VALUES = (-1.0, -1.0, -1.0, -1.0)
#: 色の無い頂点に ``MFnMesh.getVertexColors`` が返す色。
_UNSET_COLOR = om2.MColor(_UNSET_COLOR_VALUES)


def _normal_of(value, check):
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
    if check:
        return Vector(_finite_vector(value, 3, "normal"))
    if not isinstance(value, (om2.MVector, om2.MFloatVector)):
        try:
            count = len(value)
        except TypeError:
            raise TypeError("normalは3個の数値の並びで指定してください") from None
        if count != 3:
            raise ValueError("normalは3個の成分で指定してください")
    return Vector(value)


class Mesh(_ControlPointShape):
    """Mayaのmeshシェイプノードを扱うクラス。"""

    _mirror_chunk = "mlibMeshMirror"

    def reorderVertices(self, reference, worldSpace=_UNSET, *, method="uv", uvSet=None, tolerance=1e-06, fast=False, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        # nodes の初期化順に依存しないよう、使う時点で読み込む。
        from .node import Node

        _require_choice(method, "method", ("uv", "position"))
        _require_bool(worldSpace, "worldSpace")
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError("toleranceは0以上の有限な数値で指定してください")
        if uvSet is not None and not isinstance(uvSet, str):
            raise TypeError(f"uvSetは文字列かNoneで指定してください: {type(uvSet).__name__}")
        if method == "uv" and uvSet is not None and not uvSet:
            raise ValueError("uvSetは空でない名前で指定してください")
        reference = Node(Node._input_name(reference))
        if reference.hasFn(om2.MFn.kTransform):
            shapes = reference.getShape(all=True)
            if len(shapes) != 1:
                raise ValueError("参照するトランスフォームにはシェイプが1つだけ必要です")
            reference = shapes[0]
        if not isinstance(reference, Mesh):
            raise TypeError("referenceはメッシュで指定してください")
        source, target = reference._geometry_fn(), self._geometry_fn()
        if source.numVertices != target.numVertices or source.numPolygons != target.numPolygons:
            raise ValueError("メッシュの頂点数とフェース数を同じにしてください")
        if not target.numPolygons:
            raise ValueError("メッシュにはポリゴンのフェースが必要です")
        mapping = (
            self._uv_vertex_mapping(source, target, uvSet, tolerance)
            if method == "uv"
            else self._position_vertex_mapping(source, target, tolerance, worldSpace)
        )
        counts, connects = target.getVertices()
        remapped = [mapping[v] for v in connects]
        if self._face_cycles(*source.getVertices()) != self._face_cycles(counts, remapped):
            raise ValueError("頂点の対応が、フェースのトポロジーと巻き方向を保っていません")
        if all(old == new for old, new in enumerate(mapping)):
            return
        self._require_reorder_supported(target, fast=fast)
        data = self._reordered_mesh_data(target, counts, remapped, mapping)
        materials = self.getShadingEngines(perFace=True)
        current_uv = target.currentUVSetName()
        if fast:
            points = self.getPlug("pnts").mplug()
            for i in points.getExistingArrayAttributeIndices():
                point = points.elementByLogicalIndex(i)
                for j in range(point.numChildren()):
                    point.child(j).setFloat(0)
            target.copyInPlace(data)
        else:
            if not cmds.undoInfo(query=True, state=True):
                raise RuntimeError("reorderVerticesにはUndoを有効にするか、fast=Trueを指定してください")
            with undoTransaction("mlibMeshReorderVertices"):
                # APIで作るのは一時形状のみ。対象への反映と履歴のベイクは標準コマンドでUndoに記録する。
                temporary = cmds.createNode("mesh", skipSelect=True)
                temp_node = Node(temporary)
                parent = cmds.listRelatives(temporary, parent=True, fullPath=True)[0]
                uv_names = om2.MFnMesh(data).getUVSetNames()
                for i, uv_set_name in enumerate(uv_names):
                    cmds.setAttr(temp_node._full_name() + f".uvSet[{i}].uvSetName", uv_set_name, type="string")
                temp_node.getPlug("cachedInMesh").mplug().setMObject(data)
                # 元のキャッシュをsetAttrのUndoへ保存する。接続のUndoだけではデータは復元されない。
                cmds.setAttr(self._full_name() + ".outMesh", "v", 0, "vn", 0, "e", 0, type="mesh")
                for uv_set_name in uv_names:
                    if uv_set_name not in (cmds.polyUVSet(self._full_name(), query=True, allUVSets=True) or []):
                        cmds.polyUVSet(self._full_name(), create=True, uvSet=uv_set_name)
                cmds.connectAttr(temp_node._full_name() + ".outMesh", self._full_name() + ".inMesh")
                cmds.delete(self._full_name(), constructionHistory=True)
                cmds.delete(parent)
                cmds.polyUVSet(self._full_name(), currentUVSet=True, uvSet=current_uv)
                groups = defaultdict(list)
                for face, material in enumerate(materials):
                    if material is not None:
                        groups[material._full_name()].append(f"{self._full_name()}.f[{face}]")
                for material, faces in groups.items():
                    cmds.sets(faces, edit=True, forceElement=material)

    def getVertices(self, indices=None):
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
        return _component_of(Vertex, Vertices, self, indices)

    def getVertexFaces(self, indices=None):
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
        return VertexFaces(self, indices)

    def getShadingEngines(self, *, perFace=False):
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
        # nodes の初期化順に依存しないよう、使う時点で読み込む。
        from .node import Nodes
        from .shadingEngine import ShadingEngine

        _require_bool(perFace, "perFace")
        groups, indices = self._geometry_fn().getConnectedShaders(self.mpath().instanceNumber())
        if perFace:
            wrapped = [ShadingEngine(group) for group in groups]
            return [wrapped[i] if i >= 0 else None for i in indices]
        return Nodes._wrap([ShadingEngine(groups[i]) for i in sorted(set(indices)) if i >= 0])

    def mfn(self):
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
        path = self.mpath()
        try:
            fn = om2.MFnMesh(path)
            # 版により作成は通り照会で失敗するため、形状データの有無を作成直後に確かめる。
            fn.typeId  # noqa: B018
        except (RuntimeError, ValueError):
            return om2.MFnDagNode(path)
        return fn

    def getNumVertices(self):
        """頂点数を取得する。

        Returns:
            int: メッシュの頂点数。
        """
        return self._geometry_fn().numVertices

    def getNumPolygons(self):
        """ポリゴン数を取得する。

        Returns:
            int: メッシュのポリゴン数。
        """
        return self._geometry_fn().numPolygons

    def getNumEdges(self):
        """エッジ数を取得する。

        Returns:
            int: メッシュのエッジ数。
        """
        return self._geometry_fn().numEdges

    def getVertexNormals(self, worldSpace=_UNSET, *, angleWeighted=False, perFace=False, faceVertices=None, lockedOnly=False, ws=_UNSET):
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
        _require_bool(angleWeighted, "angleWeighted")
        _require_bool(perFace, "perFace")
        _require_bool(lockedOnly, "lockedOnly")
        if not perFace:
            if faceVertices is not None or lockedOnly:
                raise TypeError("faceVertices・lockedOnlyはperFace=Trueのときだけ指定できます")
            worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
            space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
            # MFloatVectorはom2の多重定義の解決を通さず、成分を写して同じ値のVectorにする。
            return [_vector_of(Vector, value) for value in self._geometry_fn().getVertexNormals(angleWeighted, space)]
        if angleWeighted:
            raise TypeError("angleWeightedはperFace=Falseのときだけ指定できます")
        if lockedOnly:
            if worldSpace is not _UNSET or ws is not _UNSET:
                raise TypeError("lockedOnly=TrueとworldSpace(ws)は同時に指定できません")
            components = self._resolve_face_vertices(faceVertices)
            fn = self._geometry_fn()
            normal_ids = fn.getNormalIds()[1]
            return [fn.isNormalLocked(normal_ids[index]) for index in components.indices]
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        components = self._resolve_face_vertices(faceVertices)
        fn = self._geometry_fn()
        values = fn.getNormals(space)
        normal_ids = fn.getNormalIds()[1]
        return [_vector_of(Vector, values[normal_ids[index]]).normal() for index in components.indices]

    def setNormals(self, normals, worldSpace=_UNSET, *, ws=_UNSET, fast=False, check=False):
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
        _require_bool(fast, "fast")
        _require_bool(check, "check")
        if not fast:
            raise NotImplementedError("setNormalsはfast=True専用です")
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        values = [om2.MVector(_finite_vector(value, 3, "normals")) for value in normals]
        fn = self._geometry_fn()
        if len(values) != fn.numNormals or any(value.length() == 0 for value in values):
            raise ValueError("normalsは現在と同数のゼロでない法線で指定してください")
        self._require_face_vertex_edit("setNormals", True)
        if check:
            require_writable(self.getPlug("inMesh").mplug())
        # setNormalsのworld指定が反映されない版があるため、法線を明示的に変換する。
        if space == om2.MSpace.kWorld:
            matrix = self.mpath().inclusiveMatrix()
            if matrix.isSingular():
                raise ValueError("特異なマトリクスではワールド空間の法線を設定できません")
            transform = matrix.transpose()
            values = [value * transform for value in values]
        # 未ロック法線への設定は既存値と混ざるため、先に法線を固定する。
        fn.lockVertexNormals(range(fn.numVertices))
        fn.setNormals(values, om2.MSpace.kObject)

    def getNormalData(self, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        fn = self._geometry_fn()
        normals = [_vector_of(Vector, value) for value in fn.getNormals(space)]
        counts, indices = fn.getNormalIds()
        return normals, list(counts), list(indices)

    def setFaceVertexNormals(self, normals=None, worldSpace=_UNSET, *, locked=None, fast=False, check=False, faceVertices=None, ws=_UNSET):
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
        _require_bool(fast, "fast")
        _require_bool(check, "check")
        if locked is not None:
            _require_bool(locked, "locked")
        if normals is None:
            if locked is None:
                raise TypeError("normalsかlockedのどちらかを指定してください")
            if worldSpace is not _UNSET or ws is not _UNSET or check:
                raise TypeError("worldSpace(ws)・checkはnormalsを指定したときだけ指定できます")
            components = self._resolve_face_vertices(faceVertices)
            self._require_face_vertex_edit("setFaceVertexNormals", fast)
            if not components:
                return
            if fast:
                self._set_face_vertex_normals_locked_fast(components, locked)
            elif locked:
                cmds.polyNormalPerVertex(components.getNames(full=True), freezeNormal=True)
            else:
                cmds.polyNormalPerVertex(components.getNames(full=True), unFreezeNormal=True)
            return
        if locked is False:
            raise TypeError("normalsとlocked=Falseは同時に指定できません(ロックを外すと、設定した法線は計算し直されます)")
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        worldSpace = _world_space(worldSpace)
        components = self._resolve_face_vertices(faceVertices)
        values = [_normal_of(value, check) for value in normals]
        if len(values) != len(components):
            raise ValueError("normalsは面頂点と同じ数で指定してください")
        if any(value.length() == 0 for value in values):
            raise ValueError("normalは長さが0でない値で指定してください")
        if worldSpace:
            matrix = self.mpath().inclusiveMatrix()
            if matrix.isSingular():
                raise ValueError("ワールド法線の設定には反転可能なマトリクスが必要です")
            # 法線は点・接線と異なり逆転置で変換する。world→objectでは元マトリクスの転置になる。
            values = [value * matrix.transpose() for value in values]
        values = [value.normal() for value in values]
        self._require_face_vertex_edit("setFaceVertexNormals", fast)
        if not values:
            return
        if fast:
            self._set_face_vertex_normals_fast(components, values)
        else:
            cmds.polyNormalPerVertex(components.getNames(full=True), normalXYZ=[tuple(value) for value in values])

    def getTangentData(self, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        fn = self._geometry_fn()
        name = fn.currentUVSetName()
        counts, vertices = fn.getVertices()
        uv_counts, _ = fn.getAssignedUVs(name)
        if list(uv_counts) != list(counts):
            raise RuntimeError("全フェースにUVが割り当てられている必要があります")
        tangents = [_vector_of(Vector, value) for value in fn.getTangents(space, name)]
        binormals = [_vector_of(Vector, value) for value in fn.getBinormals(space, name)]
        indices = []
        offset = 0
        for face, count in enumerate(counts):
            indices.extend(fn.getTangentId(face, vertices[offset + corner]) for corner in range(count))
            offset += count
        return {
            "uvSet": name,
            "tangents": tangents,
            "binormals": binormals,
            "counts": list(counts),
            "indices": indices,
            "rightHanded": [fn.isRightHandedTangent(index, name) for index in range(len(tangents))],
        }

    def getFaceVertexTangents(self, worldSpace=_UNSET, *, binormal=False, uvSet=None, faceVertices=None, ws=_UNSET):
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
        _require_bool(binormal, "binormal")
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self._face_vertex_directions(faceVertices, worldSpace, uvSet, binormal)

    def getVertexAdjacency(self, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        mesh_fn = self._geometry_fn()
        # 距離だけを求めるため、Vector へ変換せずに om2 の点列を読む。
        points = mesh_fn.getPoints(om2.MSpace.kWorld if ws else om2.MSpace.kObject)
        adjacency = [[] for _ in points]
        for index in range(mesh_fn.numEdges):
            first, second = mesh_fn.getEdgeVertices(index)
            delta = points[first] - points[second]
            length = (delta.x * delta.x + delta.y * delta.y + delta.z * delta.z) ** 0.5
            adjacency[first].append((second, length))
            adjacency[second].append((first, length))
        return adjacency

    def getShells(self, *, uv=False, uvSet=None):
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
        _require_bool(uv, "uv")
        if uv:
            name = self._resolve_uv_set(uvSet)
            _count, ids = self._geometry_fn().getUvShellsIds(name)
            shells = {}
            for index, shell in enumerate(ids):
                shells.setdefault(shell, []).append(index)
            return sorted(shells.values(), key=lambda items: items[0])
        if uvSet is not None:
            raise TypeError("uvSetはuv=Trueのときだけ指定できます")
        fn = self._geometry_fn()
        neighbors = [[] for _ in range(fn.numVertices)]
        for edge in range(fn.numEdges):
            first, second = fn.getEdgeVertices(edge)
            neighbors[first].append(second)
            neighbors[second].append(first)
        seen = [False] * len(neighbors)
        shells = []
        for start in range(len(neighbors)):
            if seen[start]:
                continue
            seen[start] = True
            shell = []
            stack = [start]
            # 再帰を使わず、大きなシェルでも深さの上限に当たらないようにする。
            while stack:
                vertex = stack.pop()
                shell.append(vertex)
                for neighbor in neighbors[vertex]:
                    if not seen[neighbor]:
                        seen[neighbor] = True
                        stack.append(neighbor)
            shells.append(Vertices(self, sorted(shell)))
        return shells

    def getTriangles(self):
        """ポリゴンを三角形に分けたときの、頂点の組を取得する。

        分け方はMayaの三角形分割に従う。

        Returns:
            list[tuple[int, int, int]]: 三角形ごとの頂点番号。フェース番号の順に並び、各フェースの中はMayaが分けた順。
        """
        _counts, vertices = self._geometry_fn().getTriangles()
        return [(vertices[index], vertices[index + 1], vertices[index + 2]) for index in range(0, len(vertices), 3)]

    def getTopology(self):
        """フェースごとの頂点の数と、頂点番号の並びを取得する。

        ``om2.MFnMesh.getVertices()`` と同じ値。メッシュを作り直す(``MFnMesh.create`` など)ときの
        polygonCounts・polygonConnectsに当たる。

        Returns:
            tuple[list[int], list[int]]: (フェース番号の順の各フェースの頂点の数, それらをつなげた頂点番号の並び)。
        """
        counts, vertices = self._geometry_fn().getVertices()
        return list(counts), list(vertices)

    def getMirrorVertexMap(self, axis="x", worldSpace=_UNSET, *, tolerance=0.01, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        component = _mirror_axis(axis)
        limit = _checked_tolerance(tolerance, positive=True)
        points = [(point.x, point.y, point.z) for point in self._raw_points(worldSpace)]
        if not points:
            return {}
        grid = _PointGrid(points)
        result = {}
        for index, point in enumerate(points):
            mirrored = list(point)
            mirrored[component] = -mirrored[component]
            found, _ = grid.nearest(mirrored, maxDistance=limit)
            if found is not None:
                result[index] = found
        return result

    def getClosestVertices(self, points, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        values = geometryEdit.point_list(points)
        vertices = [(point.x, point.y, point.z) for point in self._raw_points(worldSpace)]
        if not vertices:
            raise ValueError(f"メッシュに頂点がありません: {self._full_name()}")
        grid = _PointGrid(vertices)
        return [grid.nearest(value)[0] for value in values]

    def getEdges(self, indices=None):
        """エッジを取得する。番号を1つ渡すとエッジ1つ、番号の並びを渡すとエッジのコレクションを返す。

        Args:
            indices (int | Iterable[int] | None): 0から始まる番号1つ、または番号の並び。Noneなら今あるすべてのエッジ。

        Returns:
            Edge | Edges: 番号1つなら、シーンのエッジを指すオブジェクト。並び・Noneならエッジのコレクション(同じ番号は1回だけ含む)。

        Raises:
            TypeError: 番号の型が不正な場合(boolを含む)。
            IndexError: 番号が範囲外の場合。
        """
        return _component_of(Edge, Edges, self, indices)

    def getFaces(self, indices=None):
        """フェースを取得する。番号を1つ渡すとフェース1つ、番号の並びを渡すとフェースのコレクションを返す。

        Args:
            indices (int | Iterable[int] | None): 0から始まる番号1つ、または番号の並び。Noneなら今あるすべてのフェース。

        Returns:
            Face | Faces: 番号1つなら、シーンのフェースを指すオブジェクト。並び・Noneならフェースのコレクション(同じ番号は1回だけ含む)。

        Raises:
            TypeError: 番号の型が不正な場合(boolを含む)。
            IndexError: 番号が範囲外の場合。
        """
        return _component_of(Face, Faces, self, indices)

    def getUVs(self, indices=None):
        """UVを取得する。番号を1つ渡すとUV1つ、番号の並びを渡すとUVのコレクションを返す。

        Args:
            indices (int | Iterable[int] | None): 0から始まる番号1つ、または番号の並び。Noneなら今あるすべてのUV。

        Returns:
            UV | UVs: 番号1つなら、シーンのUVを指すオブジェクト。並び・NoneならUVのコレクション(同じ番号は1回だけ含む)。

        Raises:
            TypeError: 番号の型が不正な場合(boolを含む)。
            IndexError: 番号が範囲外の場合。
        """
        return _component_of(UV, UVs, self, indices)

    def getUVData(self, *, uvSet=None):
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
        name = self._resolve_uv_set(uvSet)
        fn = self._geometry_fn()
        us, vs = fn.getUVs(name)
        counts, indices = fn.getAssignedUVs(name)
        return list(zip(us, vs)), list(counts), list(indices)

    def setUVData(self, uvs, counts, indices, *, fast=False, uvSet=None):
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
        _require_bool(fast, "fast")
        name = self._resolve_uv_set(uvSet)
        values, counts, indices = self._resolve_uv_data(uvs, counts, indices)
        self._require_face_vertex_edit("setUVData", fast)
        fn = self._geometry_fn()
        if any(fn.isUVSetPerInstance(item) for item in fn.getUVSetNames()):
            raise ValueError("setUVDataはインスタンス別のUVセットに対応していません")
        if fast:
            self._set_uv_data_fast(fn, name, values, counts, indices)
        else:
            self._set_uv_data_cmds(name, values, counts, indices)

    def getNumUVs(self):
        """今のUVセットのUVの数を取得する。

        Returns:
            int: UVの数。
        """
        return self._geometry_fn().numUVs()

    def getClosestPoint(self, point, worldSpace=_UNSET, *, what="point", uvSet=None, ws=_UNSET):
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
        what = _require_choice(what, "what", ("point", "normal", "uv"))
        if uvSet is not None and what != "uv":
            raise TypeError('uvSetはwhat="uv"のときだけ指定できます')
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        value = self._resolve_query_point(point)
        if what == "point":
            fn = self._require_faces()
            closest, face = fn.getClosestPoint(value, om2.MSpace.kWorld if ws else om2.MSpace.kObject)
            return _vector_of(Vector, closest), face
        if what == "normal":
            fn, face, corners = self._closest_triangle(value, ws)
            normal = om2.MVector()
            for vertex, weight in corners:
                normal += om2.MVector(fn.getFaceVertexNormal(face, vertex, om2.MSpace.kObject)) * weight
            if normal.length() < 1e-12:
                # 補間で打ち消し合う退化した場合は面法線を使う。
                normal = fn.getPolygonNormal(face, om2.MSpace.kObject)
            if ws:
                normal = normal * self.mpath().inclusiveMatrixInverse().transpose()
            return _vector_of(Vector, normal.normal())
        name = self._resolve_uv_set(uvSet)
        fn, face, corners = self._closest_triangle(value, ws)
        local = list(fn.getPolygonVertices(face))
        u = v = 0.0
        for vertex, weight in corners:
            try:
                corner_u, corner_v = fn.getUV(fn.getPolygonUVid(face, local.index(vertex), name), name)
            except RuntimeError:
                raise RuntimeError(f"最も近いフェースには{name}のUVがありません: {self._full_name()}") from None
            u += corner_u * weight
            v += corner_v * weight
        return u, v

    def intersect(self, origin, direction, worldSpace=_UNSET, *, maxDistance=None, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        source = self._resolve_query_point(origin, "origin")
        vector = om2.MVector(*geometryEdit.point_list([direction])[0])
        if vector.length() == 0:
            raise ValueError("directionは長さが0でないベクトルで指定してください")
        if maxDistance is None:
            limit = _NO_DISTANCE_LIMIT
        else:
            if isinstance(maxDistance, bool) or not isinstance(maxDistance, (int, float)):
                raise TypeError("maxDistanceは数値かNoneで指定してください")
            if not math.isfinite(maxDistance) or maxDistance <= 0:
                raise ValueError("maxDistanceは正の有限な数値で指定してください")
            limit = float(maxDistance)
        fn = self._geometry_fn()
        if not fn.numPolygons:
            return []
        vector.normalize()
        found = fn.allIntersections(
            om2.MFloatPoint(source.x, source.y, source.z),
            om2.MFloatVector(vector.x, vector.y, vector.z),
            om2.MSpace.kWorld if ws else om2.MSpace.kObject,
            limit,
            False,
            sortHits=True,
        )
        if found is None:
            return []
        points, distances, faces = found[0], found[1], found[2]
        result = []
        for distance, face, index in sorted(zip(distances, faces, range(len(faces)))):
            # 四角形などの面を分けた三角形の境目に当たると、同じ面・同じ距離の交点が2つ返る。
            if any(face == other and abs(distance - previous) <= _INTERSECT_MERGE for _point, other, previous in result):
                continue
            hit = points[index]
            result.append((_vector_of(Vector, (hit.x, hit.y, hit.z)), face, float(distance)))
        return result

    def getPointsAtUV(self, u, v, worldSpace=_UNSET, *, uvSet=None, tolerance=1e-6, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        u, v = _finite_vector((u, v), 2, "uv")
        tolerance = _checked_tolerance(tolerance)
        name = self._resolve_uv_set(uvSet)
        fn = self._geometry_fn()
        counts, ids = fn.getAssignedUVs(name)
        us, vs = fn.getUVs(name)
        result = []
        offset = 0
        for face, count in enumerate(counts):
            face_ids = ids[offset : offset + count]
            offset += count
            if not count:
                continue
            if not (min(us[i] for i in face_ids) - tolerance <= u <= max(us[i] for i in face_ids) + tolerance):
                continue
            if not (min(vs[i] for i in face_ids) - tolerance <= v <= max(vs[i] for i in face_ids) + tolerance):
                continue
            try:
                point = fn.getPointAtUV(face, u, v, space, name, tolerance)
            except RuntimeError:
                # 外接矩形内でも、面のUV外や縮退した面では点を求められない。
                continue
            result.append((face, _vector_of(Vector, point)))
        return result

    def removeFaceVertexColors(self, *, fast=False, colorSet=None, faceVertices=None):
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
        _require_bool(fast, "fast")
        components = self._resolve_face_vertices(faceVertices)
        fn = self._geometry_fn()
        name = self._resolve_color_set(colorSet, fn)
        self._require_face_vertex_edit("removeFaceVertexColors", fast)
        if name is None or not components:
            return
        if not fast:
            self._require_color_removal_history(name)
        current = fn.currentColorSetName()
        with _edit_context("mlibMeshRemoveFaceVertexColors", fast, single=current == name):
            if fast:
                self._remove_face_vertex_colors_fast(fn, name, components)
            else:
                self._remove_face_vertex_colors_cmds(name, components)

    def getVertexColors(self, *, perFace=False, colorSet=None, faceVertices=None):
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
        _require_bool(perFace, "perFace")
        if perFace:
            components = self._resolve_face_vertices(faceVertices)
            fn = self._geometry_fn()
            name = self._resolve_color_set(colorSet, fn)
            if name is None:
                return [None] * len(components)
            colors = fn.getColors(name)
            result = []
            for index in components.indices:
                face, local_vertex = fn.getFaceAndVertexIndices(index, True)
                color_index = fn.getColorIndex(face, local_vertex, name)
                # 生の一括取得は、同じ頂点の別コーナーに色があると未設定を黒で返すため、割り当て番号で区別する。
                result.append(None if color_index < 0 else tuple(colors[color_index]))
            return result
        if faceVertices is not None:
            raise TypeError("faceVerticesはperFace=Trueのときだけ指定できます")
        fn = self._geometry_fn()
        name = self._resolve_color_set(colorSet, fn)
        if name is None:
            return [None] * fn.numVertices
        result = []
        for color in fn.getVertexColors(name, _UNSET_COLOR):
            value = (color.r, color.g, color.b, color.a)
            result.append(None if value == _UNSET_COLOR_VALUES else value)
        return result

    def setVertexColors(self, colors, *, perFace=False, vertices=None, faceVertices=None, colorSet=None, fast=False, check=False):
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
        _require_bool(fast, "fast")
        _require_bool(check, "check")
        _require_bool(perFace, "perFace")
        if perFace:
            if vertices is not None:
                raise TypeError("verticesはperFace=Falseのときだけ指定できます(perFace=TrueではfaceVerticesを使います)")
            components = self._resolve_face_vertices(faceVertices)
            fn = self._geometry_fn()
            name = self._resolve_color_set(colorSet, fn)
            values = self._resolve_colors(colors, len(components))
            self._require_face_vertex_edit("setVertexColors", fast)
            if not components:
                return
            if check:
                self._require_color_set_writable(name)
            with _edit_context("mlibMeshSetFaceVertexColors", fast):
                if fast:
                    self._set_face_vertex_colors_fast(fn, name, components, values)
                else:
                    self._set_face_vertex_colors_cmds(name, components, values)
            return
        if faceVertices is not None:
            raise TypeError("faceVerticesはperFace=Trueのときだけ指定できます(perFace=Falseではverticesを使います)")
        require_editable(self.mnode())
        with _edit_context("mlibMeshSetVertexColors", fast):
            fn = self._geometry_fn()
            name = self._resolve_color_set(colorSet, fn)
            indices = list(range(fn.numVertices)) if vertices is None else self._resolve_vertex_indices(vertices, fn.numVertices)
            values = self._resolve_colors(colors, len(indices))
            if check:
                self._require_color_set_writable(name)
            if fast:
                self._set_vertex_colors_fast(fn, name, indices, values)
            else:
                self._set_vertex_colors_cmds(name, indices, values)

    def getSetNames(self, *, kind="uv"):
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
        color = self._color_kind(kind)
        fn = self._geometry_fn()
        return list(fn.getColorSetNames() if color else fn.getUVSetNames())

    def getCurrentSet(self, *, kind="uv"):
        """今のUVセットの名前を取得する。``kind="color"`` なら、今のカラーセットの名前を取得する。

        Args:
            kind (str): 扱うセットの種類。``"uv"`` (既定)はUVセット、``"color"`` はカラーセット。

        Returns:
            str | None: 今のセットの名前。UVセットは必ず名前を返す。カラーセットが無ければNone。

        Raises:
            TypeError: kindが文字列でない場合。
            ValueError: kindが ``"uv"``・``"color"`` のどちらでもない場合。
        """
        color = self._color_kind(kind)
        fn = self._geometry_fn()
        if not color:
            return fn.currentUVSetName()
        if not fn.numColorSets:
            return None
        return fn.currentColorSetName() or None

    def setCurrentSet(self, name, *, kind="uv"):
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
        color = self._color_kind(kind)
        self._require_set(name, "name", color, exists=True)
        if color:
            with undoChunk("mlibMeshSetCurrentColorSet"):
                cmds.polyColorSet(self._full_name(), currentColorSet=True, colorSet=name)
            return
        with undoChunk("mlibMeshSetCurrentUVSet"):
            cmds.polyUVSet(self._full_name(), currentUVSet=True, uvSet=name)

    def createSet(self, name, *, kind="uv"):
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
        color = self._color_kind(kind)
        self._require_set(name, "name", color, exists=False)
        if color:
            with undoChunk("mlibMeshCreateColorSet"):
                cmds.polyColorSet(self._full_name(), create=True, colorSet=name, representation="RGBA")
            return
        with undoChunk("mlibMeshCreateUVSet"):
            cmds.polyUVSet(self._full_name(), create=True, uvSet=name)

    def copySet(self, source, target, *, kind="uv", overwrite=False):
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
        color = self._color_kind(kind)
        _require_bool(overwrite, "overwrite")
        if color:
            if overwrite:
                raise TypeError('overwriteはUVセット(kind="uv")のときだけ指定できます')
            self._require_set(source, "source", True, exists=True)
            self._require_set(target, "target", True, exists=False)
            with undoChunk("mlibMeshCopyColorSet"):
                cmds.polyColorSet(self._full_name(), copy=True, colorSet=source, newColorSet=target)
            return
        self._require_set(source, "source", False, exists=True)
        if overwrite and source == target:
            raise ValueError(f"sourceとtargetに同じUVセットは指定できません: {source}")
        if overwrite and target in self.getSetNames():
            # polyCopyUVはフェースを選ぶので、選択を戻すまでを1回のUndoにまとめる。
            with undoChunk("mlibMeshCopyUVSet"), preservedSelection():
                cmds.polyCopyUV(self._full_name(), uvSetNameInput=source, uvSetName=target, constructionHistory=False)
            return
        self._require_set(target, "target", False, exists=False)
        with undoChunk("mlibMeshCopyUVSet"):
            cmds.polyUVSet(self._full_name(), copy=True, uvSet=source, newUVSet=target)

    def renameSet(self, name, newName, *, kind="uv"):
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
        color = self._color_kind(kind)
        self._require_set(name, "name", color, exists=True)
        self._require_set(newName, "newName", color, exists=False)
        if color:
            with undoChunk("mlibMeshRenameColorSet"):
                cmds.polyColorSet(self._full_name(), rename=True, colorSet=name, newColorSet=newName)
            return
        with undoChunk("mlibMeshRenameUVSet"):
            cmds.polyUVSet(self._full_name(), rename=True, uvSet=name, newUVSet=newName)

    def deleteSet(self, name, *, kind="uv"):
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
        color = self._color_kind(kind)
        self._require_set(name, "name", color, exists=True)
        if color:
            with undoChunk("mlibMeshDeleteColorSet"):
                cmds.polyColorSet(self._full_name(), delete=True, colorSet=name)
            return
        if name == self._default_uv_set():
            raise ValueError(f"既定のUVセットは削除できません: {name}")
        with undoChunk("mlibMeshDeleteUVSet"):
            cmds.polyUVSet(self._full_name(), delete=True, uvSet=name)

    def getBorder(self, *, type="edge"):
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
        type = _require_choice(type, "type", ("edge", "vertex"))
        iterator = om2.MItMeshEdge(self.mpath())
        found = []
        while not iterator.isDone():
            if iterator.numConnectedFaces() == 1:
                found.append(iterator.index())
            iterator.next()
        if type == "edge":
            return Edges(self, found)
        fn = self._geometry_fn()
        vertices = set()
        for edge in found:
            vertices.update(fn.getEdgeVertices(edge))
        return Vertices(self, sorted(vertices))

    def getHoles(self):
        """フェース内部の穴を構成する頂点列を取得する。

        メッシュの外周や欠損面、polyHoleで非表示にした面は対象にしない。

        Returns:
            list[tuple[int, list[int]]]: (フェース番号, 内周の頂点番号列)。頂点はメッシュ全体の番号で、
                穴と頂点の並びはOpenMayaの順を保つ。穴が無ければ空のリスト。すべて独立した値。

        Raises:
            RuntimeError: 形状データが無いか無効なメッシュの場合。
        """
        return [(face, list(vertices)) for face, vertices in self._geometry_fn().getHoles()]

    @staticmethod
    def _color_kind(kind):
        """セット操作のkindを確かめ、カラーセットかを返す。

        Args:
            kind (str): ``"uv"`` か ``"color"``。

        Returns:
            bool: カラーセットならTrue、UVセットならFalse。

        Raises:
            TypeError: kindが文字列でない場合。
            ValueError: kindが ``"uv"``・``"color"`` のどちらでもない場合。
        """
        return _require_choice(kind, "kind", ("uv", "color")) == "color"

    def _resolve_face_vertices(self, values):
        """面頂点の指定を、同じメッシュのVertexFacesへ解決する。

        Args:
            values (VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None): 対象。

        Returns:
            VertexFaces: 指定順の面頂点。重複はComponentsの規則どおり除く。
        """
        if isinstance(values, (VertexFace, VertexFaces)):
            if values.shape != self:
                raise ValueError("faceVerticesは同じメッシュのコンポーネントで指定してください")
            values._require_valid()
            values = values.indices if isinstance(values, VertexFaces) else [values.index]
        components = VertexFaces(self, values)
        components._require_valid()
        return components

    def _require_face_vertex_edit(self, method, fast):
        """面頂点データの書き込み先と、fastのヒストリ制限を確認する。

        Args:
            method (str): エラーに示す公開メソッド名。
            fast (bool): OpenMayaで直接書くか。

        Returns:
            None: 値を返さない。
        """
        dependency = self._dependency_fn()
        if dependency.isLocked:
            raise RuntimeError(f"メッシュがロックされています: {self._full_name()}")
        if dependency.isFromReferencedFile:
            raise RuntimeError(f"メッシュがリファレンスです: {self._full_name()}")
        if fast and self.getPlug("inMesh").mplug().isDestination:
            raise NotImplementedError(f"fastの{method}は入力ヒストリのあるメッシュに対応していません")

    def _set_face_vertex_normals_fast(self, components, values):
        """面頂点の法線をOpenMayaで直接書く。

        Args:
            components (VertexFaces): 確認済みの対象。
            values (list[Vector]): オブジェクト空間の法線。

        Returns:
            None: 値を返さない。
        """
        pairs = VertexFace._multi_indices(self, components.indices)
        self._geometry_fn().setFaceVertexNormals(values, [face for _, face in pairs], [vertex for vertex, _ in pairs])

    def _set_face_vertex_normals_locked_fast(self, components, state):
        """面頂点法線のロックをOpenMayaで切り替える。

        Args:
            components (VertexFaces): 確認済みの対象。
            state (bool): ロックするか。

        Returns:
            None: 値を返さない。
        """
        pairs = VertexFace._multi_indices(self, components.indices)
        faces = [face for _, face in pairs]
        vertices = [vertex for vertex, _ in pairs]
        fn = self._geometry_fn()
        if state:
            fn.lockFaceVertexNormals(faces, vertices)
        else:
            fn.unlockFaceVertexNormals(faces, vertices)

    def _face_vertex_directions(self, faceVertices, worldSpace, uvSet, binormal):
        """UVの対応を確認し、面頂点の接線または従法線を返す。

        Args:
            faceVertices (VertexFace | VertexFaces | Iterable[int | tuple[int, int]] | None): 対象。
            worldSpace (bool): ワールド空間で求めるか。
            uvSet (str | None): UVセット。
            binormal (bool): Trueは従法線、Falseは接線。

        Returns:
            list[Vector]: 指定順の正規化した方向。
        """
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        name = self._resolve_uv_set(uvSet)
        components = self._resolve_face_vertices(faceVertices)
        fn = self._geometry_fn()
        iterator = om2.MItMeshPolygon(self.mpath())
        result = []
        for vertex, face in VertexFace._multi_indices(self, components.indices):
            iterator.setIndex(face)
            if not iterator.hasUVs(name) or iterator.getUVArea(name) == 0:
                raise RuntimeError(f"接線を求める面のUVが未割当か縮退しています: {self._full_name()}.f[{face}]")
            value = fn.getFaceVertexBinormal(face, vertex, space, name) if binormal else fn.getFaceVertexTangent(face, vertex, space, name)
            if not all(math.isfinite(component) for component in value) or value.length() == 0:
                raise RuntimeError(f"面頂点の方向を求められません: {self._full_name()}.vtxFace[{vertex}][{face}]")
            result.append(Vector(value).normal())
        return result

    def _resolve_uv_data(self, uvs, counts, indices):
        """UVの座標数と、面ごとの割り当て数・番号を検証する。

        Args:
            uvs (Iterable[Sequence[float]]): UV座標。
            counts (Iterable[int]): 面ごとのUV数。
            indices (Iterable[int]): コーナーに割り当てるUV番号。

        Returns:
            tuple[list[tuple[float, float]], list[int], list[int]]: 確認済みの値。
        """
        values = [_finite_vector(value, 2, "uv") for value in uvs]
        counts = list(counts)
        indices = list(indices)
        face_counts = self._geometry_fn().getVertices()[0]
        if len(counts) != len(face_counts):
            raise ValueError("countsはフェース数と同じ長さで指定してください")
        for count, expected in zip(counts, face_counts):
            if isinstance(count, bool) or not isinstance(count, int):
                raise TypeError("countsはintの並びで指定してください")
            if count not in (0, expected):
                raise ValueError("各フェースのUV数は0か頂点数で指定してください")
        if sum(counts) != len(indices):
            raise ValueError("indicesはcountsの合計と同じ長さで指定してください")
        for index in indices:
            if isinstance(index, bool) or not isinstance(index, int):
                raise TypeError("indicesはintの並びで指定してください")
            if not 0 <= index < len(values):
                raise ValueError("indicesはUV座標の範囲内で指定してください")
        return values, counts, indices

    @staticmethod
    def _set_uv_data_fast(fn, name, values, counts, indices):
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
        fn.clearUVs(name)
        if values:
            fn.setUVs([value[0] for value in values], [value[1] for value in values], name)
        fn.assignUVs(counts, indices, name)

    def _set_uv_data_cmds(self, name, values, counts, indices):
        """一時形状に用意したUVを標準コマンドで転送し、Undoに記録する。

        Args:
            name (str): UVセット名。
            values (list[tuple[float, float]]): UV座標。
            counts (list[int]): 面ごとのUV数。
            indices (list[int]): UV番号。

        Returns:
            None: 値を返さない。
        """
        # NodeはShapeの基底なので、循環importを避けて呼び出し時に読む。
        from .node import Node

        fn = self._geometry_fn()
        current = fn.currentUVSetName()
        data = om2.MFnMeshData().create()
        om2.MFnMesh().copy(self.mnode(), data)
        with undoChunk("mlibMeshSetUVData"):
            temporary = Node._from_name(cmds.createNode("mesh", skipSelect=True))
            parent = temporary.getParent()
            try:
                # 書き込み先は作業用の形状だけ。対象への反映はpolyTransferがUndoへ記録する。
                for index, uv_set in enumerate(fn.getUVSetNames()):
                    cmds.setAttr(f"{temporary._full_name()}.uvSet[{index}].uvSetName", uv_set, type="string")
                temporary.getPlug("cachedInMesh").mplug().setMObject(data)
                self._set_uv_data_fast(temporary._geometry_fn(), name, values, counts, indices)
                cmds.polyTransfer(
                    self._full_name(), alternateObject=temporary._full_name(), uvSets=True, vertices=False, vertexColor=False, constructionHistory=False
                )
                if self._geometry_fn().currentUVSetName() != current:
                    cmds.polyUVSet(self._full_name(), currentUVSet=True, uvSet=current)
            finally:
                cmds.delete(parent._full_name())

    def _require_color_removal_history(self, color_set):
        """カラー解除を確認したヒストリの連鎖か検証する。

        Args:
            color_set (str): 解除するカラーセット。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 入力に指定セットのカラー編集が無いか、途中に未対応ノードがある場合。
        """
        source = self.getPlug("inMesh").getConnections(input=True)
        if source is None:
            return
        visited = set()
        while source is not None:
            node = source.getNode()
            if node in visited:
                break
            visited.add(node)
            kind = node.getType()
            if kind == "polyColorPerVertex":
                if node.getPlug("colorSetName").get() == color_set:
                    return
                break
            if kind != "polyMoveVertex":
                break
            source = node.getPlug("inputPolymesh").getConnections(input=True)
        raise RuntimeError(f"removeFaceVertexColorsに対応していない入力ヒストリです: {self._full_name()}")

    def _remove_face_vertex_colors_cmds(self, color_set, components):
        """現在のカラーセットを復元しながら、標準コマンドで色の割り当てを解除する。

        Args:
            color_set (str): 解除するカラーセット。
            components (VertexFaces): 対象。

        Returns:
            None: 値を返さない。
        """
        name = self._full_name()
        current = self._geometry_fn().currentColorSetName()
        if current != color_set:
            cmds.polyColorSet(name, currentColorSet=True, colorSet=color_set)
        try:
            cmds.polyColorPerVertex(components.getNames(full=True), remove=True)
        finally:
            if current != color_set:
                cmds.polyColorSet(name, currentColorSet=True, colorSet=current)

    def _remove_face_vertex_colors_fast(self, fn, color_set, components):
        """現在のカラーセットを復元しながら、OpenMayaで色の割り当てを解除する。

        Args:
            fn (om2.MFnMesh): 対象メッシュ。
            color_set (str): 解除するカラーセット。
            components (VertexFaces): 対象。

        Returns:
            None: 値を返さない。
        """
        current = fn.currentColorSetName()
        if current != color_set:
            fn.setCurrentColorSetName(color_set)
        try:
            pairs = VertexFace._multi_indices(self, components.indices)
            fn.removeFaceVertexColors([face for _, face in pairs], [vertex for vertex, _ in pairs])
        finally:
            if current != color_set:
                fn.setCurrentColorSetName(current)

    def _set_face_vertex_colors_cmds(self, color_set, components, values):
        """現在のカラーセットを一時的に選び、面頂点の色を標準コマンドで設定する。

        Args:
            color_set (str | None): カラーセット。
            components (VertexFaces): 対象。
            values (list[tuple[float, float, float, float]]): RGBA値。

        Returns:
            None: 値を返さない。
        """
        name = self._full_name()
        current = self._geometry_fn().currentColorSetName() or None
        if color_set is not None and current != color_set:
            cmds.polyColorSet(name, currentColorSet=True, colorSet=color_set)
        try:
            groups = defaultdict(list)
            for component, value in zip(components.getNames(full=True), values):
                groups[value].append(component)
            for value, targets in groups.items():
                cmds.polyColorPerVertex(targets, rgb=value[:3], alpha=value[3])
        finally:
            if current is not None and color_set is not None and current != color_set:
                cmds.polyColorSet(name, currentColorSet=True, colorSet=current)

    def _set_face_vertex_colors_fast(self, fn, color_set, components, values):
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
        if not fn.numColorSets:
            color_set = fn.createColorSet("colorSet1", False)
            fn.setCurrentColorSetName(color_set)
        if color_set is None:
            color_set = fn.currentColorSetName()
        colors = fn.getColors(color_set)
        start = len(colors)
        for value in values:
            colors.append(om2.MColor(value))
        fn.setColors(colors, color_set)
        face_vertices = {}
        for offset, (vertex, face) in enumerate(VertexFace._multi_indices(self, components.indices)):
            if face not in face_vertices:
                face_vertices[face] = list(fn.getPolygonVertices(face))
            fn.assignColor(face, face_vertices[face].index(vertex), start + offset, color_set)

    def _raw_points(self, worldSpace):
        """全頂点の位置を om2 の点列で返す(Vector へ変換しない照会用)。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間で扱う。

        Returns:
            om2.MPointArray: 頂点番号順の位置。
        """
        ws = _world_space(worldSpace)
        return self._geometry_fn().getPoints(om2.MSpace.kWorld if ws else om2.MSpace.kObject)

    def _set_points(self, values, ws, fast, check):
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
        fn = self._geometry_fn()
        count = fn.numVertices
        if len(values) != count:
            raise ValueError(f"点を{count}個指定してください: {len(values)}個")
        current = fn.getPoints(om2.MSpace.kWorld if ws else om2.MSpace.kObject)
        changed = [index for index, (value, point) in enumerate(zip(values, current)) if value != (point.x, point.y, point.z)]
        with _edit_context("mlibMeshSetPoints", fast, transaction=True):
            geometryEdit.set_positions(self, changed, [values[index] for index in changed], ws, fast=fast, check=check)

    def _point_components(self, indices):
        """頂点のコレクションを返す。

        Args:
            indices (Iterable[int] | None): 頂点番号。Noneは全頂点。

        Returns:
            Vertices: 頂点のコレクション。
        """
        return Vertices(self, indices)

    @staticmethod
    def _position_vertex_mapping(source, target, tolerance, world_space):
        """指定空間で許容距離内の一意な頂点対応を空間セルから求める。"""
        space = om2.MSpace.kWorld if world_space else om2.MSpace.kObject
        source_points, target_points = source.getPoints(space), target.getPoints(space)
        buckets = defaultdict(list)

        def key(point):
            values = (point.x, point.y, point.z)
            if not all(math.isfinite(v) for v in values):
                raise ValueError("頂点の位置は有限な数値にしてください")
            return tuple(math.floor(v / tolerance) for v in values) if tolerance else values

        for index, point in enumerate(source_points):
            buckets[key(point)].append(index)
        mapping = []
        for point in target_points:
            cell = key(point)
            cells = [(cell[0] + x, cell[1] + y, cell[2] + z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)] if tolerance else [cell]
            candidates = [index for neighbor in cells for index in buckets.get(neighbor, ()) if (point - source_points[index]).length() <= tolerance]
            if len(candidates) != 1:
                raise ValueError("位置の対応が見つからないか、許容誤差の範囲で決められません")
            mapping.append(candidates[0])
        if len(set(mapping)) != len(mapping):
            raise ValueError("位置の対応が1対1になっていません")
        return mapping

    @staticmethod
    def _uv_vertex_mapping(source, target, uv_set, tolerance):
        """面頂点UV群が一意に一致する旧対象番号→基準番号を求める。uv_setがNoneなら、それぞれのメッシュの今のUVセットを使う。"""

        def signatures(fn):
            name = fn.currentUVSetName() if uv_set is None else uv_set
            if name not in fn.getUVSetNames():
                raise ValueError(f"UVセットが存在しません: {name}")
            counts, connects = fn.getVertices()
            uv_counts, uv_ids = fn.getAssignedUVs(name)
            if list(counts) != list(uv_counts):
                raise ValueError("すべてのフェース頂点にUVが必要です")
            u, v = fn.getUVs(name)
            values = [[] for _ in range(fn.numVertices)]
            for vertex, uv in zip(connects, uv_ids):
                value = (u[uv], v[uv])
                if not all(math.isfinite(x) for x in value):
                    raise ValueError("UV座標は有限な数値にしてください")
                values[vertex].append(value)
            if any(not row for row in values):
                raise ValueError("孤立した頂点はUVでは対応付けられません")
            return [sorted(row) for row in values]

        source_rows, target_rows = signatures(source), signatures(target)
        buckets = defaultdict(list)

        def key(value):
            return tuple(math.floor(x / tolerance) for x in value) if tolerance else value

        for i, row in enumerate(source_rows):
            buckets[(len(row), key(row[0]))].append(i)
        mapping = []
        for row in target_rows:
            anchor = key(row[0])
            keys = [(anchor[0] + x, anchor[1] + y) for x in (-1, 0, 1) for y in (-1, 0, 1)] if tolerance else [anchor]
            candidates = [
                i
                for cell in keys
                for i in buckets.get((len(row), cell), ())
                if all(abs(a - b) <= tolerance for pair, other in zip(row, source_rows[i]) for a, b in zip(pair, other))
            ]
            if len(candidates) != 1:
                raise ValueError("UVによる頂点の対応が見つからないか、決められません")
            mapping.append(candidates[0])
        if len(set(mapping)) != len(mapping):
            raise ValueError("UVの対応が1対1になっていません")
        return mapping

    @staticmethod
    def _face_cycles(counts, connects):
        """面の開始頂点に依存せず、面の向きと頂点接続を比較する。"""
        result, offset = [], 0
        for count in counts:
            row = list(connects[offset : offset + count])
            pivot = row.index(min(row))
            result.append(tuple(row[pivot:] + row[:pivot]))
            offset += count
        return Counter(result)

    def _require_reorder_supported(self, fn, *, fast=False):
        """番号依存の外部接続や未対応のメッシュデータを変更前に拒否する。"""
        if self.mpath().isInstanced() or self._dependency_fn().isFromReferencedFile:
            raise ValueError("インスタンスやリファレンスのターゲットには対応していません")
        if self._dependency_fn().isLocked:
            raise RuntimeError("メッシュがロックされています")
        if self.getPlug("outMesh").mplug().isLocked:
            raise RuntimeError("メッシュの出力がロックされています")
        sets, members = fn.getConnectedSetsAndMembers(self.mpath().instanceNumber(), False)
        if any(not member.isNull() and not group.hasFn(om2.MFn.kShadingEngine) for group, member in zip(sets, members)):
            raise ValueError("シェーディングの割り当て以外のコンポーネントのセットには対応していません")
        if self.getPlug("inMesh").mplug().isDestination:
            raise ValueError("ターゲットには入力ヒストリがない状態にしてください")
        for name in ("outMesh", "worldMesh"):
            plug = self.getPlug(name).mplug()
            plugs = [plug.elementByLogicalIndex(i) for i in plug.getExistingArrayAttributeIndices()] if plug.isArray else [plug]
            if any(p.isSource for p in plugs):
                raise ValueError("ターゲットは下流のジオメトリを駆動していない状態にしてください")
        creased = False
        for getter in (fn.getCreaseEdges, fn.getCreaseVertices):
            # クリースデータ自体がない通常メッシュではMayaがkFailureを返す。
            with contextlib.suppress(RuntimeError):
                creased = creased or bool(getter()[0])
        if fn.getColorSetNames() or creased or fn.getHoles():
            raise ValueError("カラーセット・クリース・ポリゴンの穴には対応していません")
        if any(fn.hasBlindData(kind) for kind in (om2.MFn.kMeshVertComponent, om2.MFn.kMeshEdgeComponent, om2.MFn.kMeshPolygonComponent)):
            raise ValueError("メッシュのブラインドデータには対応していません")
        for name in ("inMesh", "cachedInMesh", "pnts"):
            plug = self.getPlug(name).mplug()
            require_writable(plug)
            if plug.isArray:
                for i in plug.getExistingArrayAttributeIndices():
                    item = plug.elementByLogicalIndex(i)
                    require_writable(item)
                    for j in range(item.numChildren()):
                        require_writable(item.child(j))
                        if not fast and item.child(j).asFloat() != 0:
                            raise NotImplementedError("通常の並べ替えは頂点のtweakに対応していません。コピーに対してfast=Trueを使います")

    @staticmethod
    def _reordered_mesh_data(fn, counts, remapped, mapping):
        """シーン外のメッシュデータを作り、面順・UVと法線を移す。"""
        points = fn.getPoints()
        reordered = om2.MPointArray(points)
        for old, new in enumerate(mapping):
            reordered[new] = points[old]
        data = om2.MFnMeshData().create()
        rebuilt = om2.MFnMesh()
        rebuilt.create(reordered, counts, remapped, parent=data)
        # UVセットの追加はmesh dataではなくmeshノードに対してのみ使用できる。
        # 一時ノードで全セットを構築し、コピー後に必ず破棄する。Undo履歴には残さない。
        modifier = om2.MDagModifier()
        parent = modifier.createNode("transform")
        temporary = modifier.createNode("mesh", parent)
        modifier.doIt()
        try:
            om2.MFnDependencyNode(temporary).findPlug("cachedInMesh", False).setMObject(data)
            rebuilt = om2.MFnMesh(temporary)
            Mesh._copy_reorder_details(fn, rebuilt, counts, remapped, mapping)
            result = om2.MFnMeshData().create()
            om2.MFnMesh().copy(temporary, result)
            return result
        finally:
            modifier.undoIt()

    @staticmethod
    def _copy_reorder_details(fn, rebuilt, counts, remapped, mapping):
        """一時メッシュへ全UVセット・エッジの硬軟・固定法線を移す。"""
        if "map1" not in fn.getUVSetNames():
            rebuilt.renameUVSet("map1", fn.getUVSetNames()[0])
        for uv_set in fn.getUVSetNames():
            if uv_set not in rebuilt.getUVSetNames():
                rebuilt.createUVSet(uv_set)
            rebuilt.setUVs(*fn.getUVs(uv_set), uvSet=uv_set)
            rebuilt.assignUVs(*fn.getAssignedUVs(uv_set), uvSet=uv_set)
        rebuilt.setCurrentUVSetName(fn.currentUVSetName())
        smooth = {tuple(sorted(mapping[v] for v in fn.getEdgeVertices(i))): fn.isEdgeSmooth(i) for i in range(fn.numEdges)}
        for i in range(rebuilt.numEdges):
            rebuilt.setEdgeSmoothing(i, smooth[tuple(sorted(rebuilt.getEdgeVertices(i)))])
        rebuilt.cleanupEdgeSmoothing()
        normals = fn.getNormals()
        _, normal_ids = fn.getNormalIds()
        faces = [i for i, count in enumerate(counts) for _ in range(count)]
        locked = [i for i, normal in enumerate(normal_ids) if fn.isNormalLocked(normal)]
        if locked:
            rebuilt.setFaceVertexNormals([om2.MVector(normals[normal_ids[i]]) for i in locked], [faces[i] for i in locked], [remapped[i] for i in locked])
            rebuilt.lockFaceVertexNormals([faces[i] for i in locked], [remapped[i] for i in locked])

    @staticmethod
    def _resolve_query_point(point, name="point"):
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
        if isinstance(point, (str, bytes)):
            raise TypeError(f"{name}は3つの数値の並びで指定してください")
        return om2.MPoint(*geometryEdit.point_list([point])[0])

    def _require_faces(self):
        """面のあるメッシュの ``om2.MFnMesh`` を返す。

        Returns:
            om2.MFnMesh: この mesh の function set。

        Raises:
            ValueError: メッシュに面が無い場合。
        """
        fn = self._geometry_fn()
        if not fn.numPolygons:
            raise ValueError(f"メッシュにフェースがありません: {self._full_name()}")
        return fn

    def _closest_triangle(self, point, worldSpace):
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
        fn = self._require_faces()
        path = self.mpath()
        if worldSpace:
            point = point * path.inclusiveMatrixInverse()
        intersector = om2.MMeshIntersector()
        intersector.create(path.node(), om2.MMatrix())
        found = intersector.getClosestPoint(point)
        first, second = found.barycentricCoords
        vertices = fn.getPolygonTriangleVertices(found.face, found.triangle)
        return fn, found.face, list(zip(vertices, (first, second, 1.0 - first - second)))

    def _resolve_uv_set(self, uvSet):
        """UVセットの指定を、実在する名前にする。

        Args:
            uvSet (str | None): UVセットの名前。Noneなら今のUVセットを使う。

        Returns:
            str: UVセットの名前。

        Raises:
            TypeError: uvSetが文字列・None以外の場合。
            ValueError: 名前が空、そのUVセットが無い、またはメッシュにUVセットが無い場合。
        """
        if uvSet is None:
            name = self._geometry_fn().currentUVSetName()
            if not name:
                raise ValueError(f"メッシュにUVセットがありません: {self._full_name()}")
            return name
        self._require_set(uvSet, "uvSet", False, exists=True)
        return uvSet

    def _require_set(self, name, label, color, *, exists):
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
        if not isinstance(name, str):
            raise TypeError(f"{label}はstrで指定してください")
        if not name:
            raise ValueError(f"{label}は空でない文字列で指定してください")
        fn = self._geometry_fn()
        found = name in (fn.getColorSetNames() if color else fn.getUVSetNames())
        kind = "カラーセット" if color else "UVセット"
        if exists and not found:
            raise ValueError(f"{kind}が存在しません: {name}")
        if not exists and found:
            raise ValueError(f"{kind}はすでに存在します: {name}")

    def _default_uv_set(self):
        """既定のUVセット(``uvSet[0]``)の名前を返す。

        Returns:
            str: 既定のUVセットの名前。
        """
        plug = self._dependency_fn().findPlug("uvSet", False)
        return plug.elementByLogicalIndex(0).child(0).asString()

    def _require_color_set_writable(self, name):
        """カラーセットの値のアトリビュート(``colorSet[].colorSetPoints``)へ書き込めるかを確かめる。

        Args:
            name (str | None): カラーセットの名前。Noneなら確かめない(まだカラーセットが無い)。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ロック・入力の接続などで書き込めない場合。
        """
        if name is None:
            return
        dependency = self._dependency_fn()
        sets = dependency.findPlug("colorSet", False)
        name_attribute = dependency.attribute("colorName")
        points_attribute = dependency.attribute("colorSetPoints")
        for index in sets.getExistingArrayAttributeIndices():
            element = sets.elementByLogicalIndex(index)
            if element.child(name_attribute).asString() == name:
                require_writable(element.child(points_attribute))
                return

    def _resolve_color_set(self, colorSet, fn):
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
        if colorSet is None:
            if not fn.numColorSets:
                return None
            return fn.currentColorSetName() or None
        if not isinstance(colorSet, str):
            raise TypeError("colorSetはstrかNoneで指定してください")
        if not colorSet:
            raise ValueError("colorSetは空でない文字列で指定してください")
        if colorSet not in fn.getColorSetNames():
            raise ValueError(f"カラーセットが存在しません: {colorSet}")
        return colorSet

    def _resolve_vertex_indices(self, vertices, count):
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
        shape = getattr(vertices, "shape", None)
        if shape is not None and shape != self:
            raise ValueError(f"verticesが別のメッシュのものです: {shape._full_name()}")
        if hasattr(vertices, "indices"):
            vertices = vertices.indices
        elif isinstance(getattr(vertices, "index", None), int):
            vertices = [vertices.index]
        if isinstance(vertices, (str, bytes)):
            raise TypeError("verticesはintの並びで指定してください")
        try:
            items = list(vertices)
        except TypeError:
            raise TypeError("verticesはintの並びで指定してください") from None
        indices = []
        for value in items:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"vertexはintで指定してください: {type(value).__name__}")
            if not 0 <= value < count:
                raise IndexError(f"頂点番号が範囲外です: {value}")
            indices.append(value)
        if len(set(indices)) != len(indices):
            raise ValueError("verticesに重複は指定できません")
        return indices

    @staticmethod
    def _resolve_colors(colors, count):
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
        if isinstance(colors, (str, bytes, om2.MColor)):
            raise TypeError("colorsは色の並びで指定してください")
        try:
            items = list(colors)
        except TypeError:
            raise TypeError("colorsは色の並びで指定してください") from None
        if len(items) != count:
            raise ValueError(f"色を{count}個指定してください: {len(items)}個")
        result = []
        for color in items:
            item = color
            if isinstance(color, om2.MColor):
                item = (color.r, color.g, color.b, color.a)
            elif isinstance(color, (str, bytes)):
                raise TypeError("各色は3つか4つの数値の並びで指定してください")
            try:
                values = tuple(item)
            except TypeError:
                raise TypeError("各色は3つか4つの数値の並びで指定してください") from None
            if len(values) not in (3, 4):
                raise ValueError("各色は3つか4つの成分で指定してください")
            if len(values) == 3:
                values += (1.0,)
            result.append(_finite_vector(values, 4, "color"))
        return result

    def _set_vertex_colors_cmds(self, color_set, indices, values):
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
        if not indices:
            return
        name = self._full_name()
        current = None
        if color_set is not None:
            current = (cmds.polyColorSet(name, query=True, currentColorSet=True) or [None])[0]
            if current != color_set:
                cmds.polyColorSet(name, currentColorSet=True, colorSet=color_set)
        groups = defaultdict(list)
        for index, value in zip(indices, values):
            groups[value].append(index)
        for (red, green, blue, alpha), group in groups.items():
            cmds.polyColorPerVertex([f"{name}.vtx[{index}]" for index in group], rgb=(red, green, blue), alpha=alpha)
        if current is not None and current != color_set:
            cmds.polyColorSet(name, currentColorSet=True, colorSet=current)

    def _set_vertex_colors_fast(self, fn, color_set, indices, values):
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
        if self.getPlug("inMesh").mplug().isDestination:
            raise NotImplementedError("fastのsetVertexColorsは入力ヒストリのあるメッシュに対応していません")
        if self._dependency_fn().isLocked:
            raise RuntimeError(f"メッシュがロックされています: {self._full_name()}")
        if not indices:
            return
        if color_set is None:
            if not fn.numColorSets:
                fn.setCurrentColorSetName(fn.createColorSet("colorSet1", False))
            color_set = fn.currentColorSetName()
        current = fn.currentColorSetName()
        if current != color_set:
            fn.setCurrentColorSetName(color_set)
        try:
            fn.setVertexColors(om2.MColorArray([om2.MColor(value) for value in values]), indices)
        finally:
            if current and current != color_set:
                fn.setCurrentColorSetName(current)

    def _mirror_plan(self, axis, ws, pivot, indices, fast, check=False):
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
        self._geometry_fn()
        return _mirror_plan(Vertices(self, indices), axis, ws, pivot, fast, check)

    def _geometry_fn(self):
        """形状データを要する照会用に ``om2.MFnMesh`` を返す。

        Returns:
            om2.MFnMesh: この mesh の function set。

        Raises:
            RuntimeError: 保持する DAG パスが無効、または形状データを持たない空のシェイプの場合。
        """
        fn = self.mfn()
        if not isinstance(fn, om2.MFnMesh):
            raise RuntimeError(f"メッシュにジオメトリのデータがありません: {self._full_name()}")
        return fn
