"""点(頂点・CV)を持つシェイプ(mesh・nurbsCurve・nurbsSurface)に共通する基底クラス。"""

from ..components.pointComponent import _mirror_plan, _write_points
from ..core import geometryEdit
from ..decorator import _pick_alias, _require_bool
from ..maths.vector import _vectors_of_points
from ..util import _UNSET, _world_space
from .shape import Shape


class _ControlPointShape(Shape):
    """点の位置を読み書きできるシェイプの基底クラス。

    Mayaの ``controlPoint`` 型から派生するシェイプのうち、手書きのクラスがあるもの(メッシュ・NURBSカーブ・NURBSサーフェス)が派生する。
    点の種類ごとの違い(頂点かCVか、番号の数、書き込みの手順)は、派生クラスの先頭が ``_`` のメソッドが持つ。
    """

    #: :meth:`mirror` のUndoチャンク名。派生クラスが決める。
    _mirror_chunk = ""

    def getPoints(self, worldSpace=_UNSET, *, ws=_UNSET):
        """すべての点(メッシュは頂点、NURBSはCV)の位置を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル(オブジェクト)空間で扱う。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[Vector]: 点の番号の順に並ぶ位置(:class:`~mlib.maths.vector.Vector`)。距離はMaya APIの内部単位(cm)。
                メッシュは頂点番号の順、カーブはCVの順、サーフェスは ``u * V方向のCV数 + v`` の順。
                NURBSのウェイト(w)は含まず、wで割らないXYZを返す。そのまま :meth:`setPoints` へ渡せる。

        Raises:
            TypeError: worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: 形状のデータを持たない空のシェイプの場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return _vectors_of_points(self._raw_points(worldSpace))

    def setPoints(self, points, worldSpace=_UNSET, *, fast=False, check=False, ws=_UNSET):
        """すべての点(メッシュは頂点、NURBSはCV)の位置をまとめて書き込む。

        :meth:`getPoints` と同じ並び・単位(内部単位のcm)の点の並びを受け取る。

        - 通常: ``cmds.xform`` で書き込み、1回のUndoにまとめる。点ごとにコマンドを呼ぶので、
          点の数に比例して時間がかかる(目安は1点あたり約1ms)。
        - ``fast=True``: OpenMaya(``MFnMesh.setPoints``・``setCVPositions``)で全部の点を1回で書き込む。Undoには記録しない。

        点の数・トポロジー・UV・次数・ノット・ウェイトは変えない。

        - メッシュ: 今と同じ位置の頂点は書き込まない(``getPoints()`` の結果を一部だけ変えて戻すと、変えた頂点だけを書く)。
        - 周期カーブ: 重なっていないCVの数(CV数 - 次数)か、末尾の重なったCVも含むCV数の点を受け付ける。
          重なったCVには、対応する先頭のCVと同じ位置を渡す。
        - 周期サーフェス: 重なっているCVには、対応する先頭のCVと同じ位置を渡す(違う位置を渡すと、後に書いた値になる)。

        Args:
            points (Iterable[Sequence[float] | om2.MPoint | om2.MVector]): 点の番号の順の位置。
                :meth:`getPoints` の結果(list[Vector])・3つの数値のtupleの並び・``om2.MPointArray`` をそのまま渡せる。
                各点は3つの有限な数値。MPointはwで割らずにXYZを使う。
            worldSpace (bool): Trueならワールド空間、Falseならローカル(オブジェクト)空間で書き込む。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: worldSpace・fastがbool以外の場合、点の型や成分が不正な場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 点の数が合わない場合、有限でない成分がある場合、周期カーブの重なったCVが先頭のCVと一致しない場合、
                またはworldSpace=Trueで、NURBSの場合かメッシュをfastで書く場合に、トランスフォームのマトリクスが特異な場合。
            RuntimeError: 形状のデータが無いか無効なシェイプの場合、またはロックなどでMayaが書き込みを拒否した場合。
            NotImplementedError: fast=Trueで、入力(コンストラクションヒストリ)がある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        self._set_points(geometryEdit.point_list(points), ws, fast, check)

    def mirror(self, axis="x", worldSpace=_UNSET, pivot=(0.0, 0.0, 0.0), indices=None, *, fast=False, check=False, ws=_UNSET):
        """点(メッシュは頂点、NURBSはCV)の座標を、pivotを中心に反転する。

        反転後の座標は ``2 * pivot - 今の座標`` になる。

        - Transform・トポロジー(点の番号・面のつながりと頂点の順)・次数・ノット・ウェイト(w)は変えない。
        - Shapeを共有しているインスタンスすべてに影響する。
        - 複製・結合・片側からの対称化・法線やパラメーターの向きの反転はしない(メッシュを1軸や3軸で反転すると、面の向きが裏返る)。
        - 全部の点の座標を先に読んでから書くので、周期カーブ・周期サーフェスの末尾の重なったCVを二重に反転しない。

        入力をすべて確かめてから書き込む。通常は ``cmds.xform`` を点ごとに呼び、1回のUndoにまとめる。
        ``fast=True`` ならOpenMayaで全部の点を1回で書く。
        点のコレクションの :meth:`~mlib.components.pointComponent.PointComponents.mirror` と同じ処理。

        Args:
            axis (str | int): 反転する軸かミラー面。既定は ``"x"``。軸は ``"x"``・``"y"``・``"z"``、
                面は ``"YZ"``・``"XZ"``・``"XY"`` (xはYZ、yはXZ、zはXYと同じ。文字の順や大文字・小文字は問わない)、
                番号なら0・1・2。
            worldSpace (bool): Trueなら、このオブジェクトが持つDAGパスのワールド空間、Falseならシェイプの
                オブジェクト空間で反転する。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            pivot (Iterable[float]): 反転の中心のXYZ(cm)。worldSpaceで選んだ空間の座標で指定する。
                既定は原点で、Transformのピボットとは関係ない。
            indices (Iterable[int] | None): 点の番号(サーフェスは通し番号か ``(u, v)``)。Noneなら全部の点、空の並びなら何も変えない。
                同じ番号は1回だけ処理する。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: worldSpace・fastがbool以外の場合、axisが文字列・int以外の場合、番号の型が不正な場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: axisやpivotが不正な場合、またはworldSpace=Trueで変換のマトリクスがほぼ特異な(逆にできない)場合。
            IndexError: 点の番号が負の数か範囲外の場合。
            RuntimeError: 形状のデータが無いか無効なシェイプの場合、またはロックなどでMayaが書き込みを拒否した場合。
            NotImplementedError: fast=Trueで、入力(コンストラクションヒストリ)がある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        self._geometry_fn()
        _write_points([_mirror_plan(self._point_components(indices), axis, ws, pivot, fast, check)], fast, self._mirror_chunk, check)

    def _raw_points(self, worldSpace):
        """すべての点の位置を om2 の点列で返す(派生クラスが実装する)。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間で扱う。

        Returns:
            om2.MPointArray: 点の番号の順の位置。
        """
        raise NotImplementedError

    def _set_points(self, values, ws, fast, check):
        """確かめてある点の並びを書き込む(派生クラスが実装する)。

        Args:
            values (list[tuple[float, float, float]]): 点の番号の順のXYZ(cm)。
            ws (bool): Trueならワールド空間。
            fast (bool): TrueはUndoなしのOpenMaya更新。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

        Returns:
            None: 値を返さない。
        """
        raise NotImplementedError

    def _point_components(self, indices):
        """点のコレクション(Vertices・CVs・SurfaceCVs)を返す(派生クラスが実装する)。

        Args:
            indices (Iterable[int] | None): 点の番号。Noneなら全部の点。

        Returns:
            PointComponents: 点のコレクション。
        """
        raise NotImplementedError

    def _geometry_fn(self):
        """形状のデータを要する照会用のfunction setを返す(派生クラスが実装する)。

        Returns:
            om2.MFnBase: このシェイプのfunction set。
        """
        raise NotImplementedError
