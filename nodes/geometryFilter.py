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

#: :meth:`GeometryFilter.dumpDeformerWeights` が書くファイルの形式の版。
_DEFORMER_WEIGHTS_VERSION = 1


class GeometryFilter(Node):
    """デフォーマー(cluster・deltaMush・softMod・skinClusterなど)に共通する操作を持つクラス。

    Mayaの抽象型 ``geometryFilter`` に対応する。頂点ごとの効き具合(デフォーマーのウェイト)を
    読み書きできる。デフォーマーのウェイトは ``weightList[形状の番号].weights`` に入っている。

    skinClusterでは、同じアトリビュートにインフルエンスのウェイトが入る。そのため、
    :meth:`getDeformerWeights` などは使えない。
    代わりに :meth:`SkinCluster.getWeights <mlib.nodes.skinCluster.SkinCluster.getWeights>` を使う。
    """

    def getDeformerTools(self):
        """デフォーマーを操作するMayaのツールオブジェクトを取得する。

        汎用deformerコマンドのdeformerToolsを使う。clusterではハンドルShape、
        skinClusterではJointなど、ノード型によって対象が異なる。Mayaの返却順を保持する。

        Returns:
            Nodes: 操作用ノード。存在しなければ空。

        Raises:
            RuntimeError: デフォーマーが無効、またはMayaが照会を拒否した場合。
        """
        self._require_valid("ツールの取得")
        return Nodes(cmds.deformer(self._full_name(), query=True, deformerTools=True) or [])

    def getGeometry(self, *, input=False, geometryIndex=None, all=False):
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
        _require_bool(input, "input")
        _require_bool(all, "all")
        if all:
            if geometryIndex is not None:
                raise TypeError("allとgeometryIndexは同時に指定できません")
            self._require_valid("形状の取得")
            fn = oma2.MFnGeometryFilter(self.mnode())
            return Nodes._wrap([Node(mobject) for mobject in (fn.getInputGeometry() if input else fn.getOutputGeometry())])
        fn = self._deformer_fn()
        if geometryIndex is None and not fn.numOutputConnections():
            return None
        geometryIndex = self._resolve_geometry_index(fn, geometryIndex)
        if not input:
            return Node._wrap_dag_path(fn.getPathAtIndex(geometryIndex))
        shape = fn.inputShapeAtIndex(geometryIndex)
        return None if shape.isNull() else Node(shape)

    def getGeometryIndices(self, geometry=None):
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
        fn = self._deformer_fn()
        if geometry is None:
            return [fn.indexForOutputConnection(index) for index in range(fn.numOutputConnections())]
        node = geometry if isinstance(geometry, Node) else Node(geometry)
        node._require_valid("ジオメトリの取得")
        if not node.mnode().hasFn(om2.MFn.kDagNode):
            raise TypeError("geometryはShapeかTransformで指定してください")
        outputs = fn.getOutputGeometry()
        candidates = list(node.getShape(all=True)) if node.mnode().hasFn(om2.MFn.kTransform) else [node]
        matches = [candidate for candidate in candidates if any(candidate.mnode() == output for output in outputs)]
        if len(matches) != 1:
            raise ValueError(f"変形対象のShapeを1つ指定してください: {node._full_name()}")
        return fn.indexForOutputShape(matches[0].mnode())

    def getGeometryComponents(self, *, geometryIndex=None):
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
        # Selectionはnodesを読み込むため、循環importを避けて使用時に読み込む。
        from ..common.selection import Selection

        fn = self._deformer_fn()
        geometryIndex = self._resolve_geometry_index(fn, geometryIndex)
        component = fn.getComponentAtIndex(geometryIndex)
        if component.isNull():
            return []
        selection = om2.MSelectionList()
        selection.add((fn.getPathAtIndex(geometryIndex), component))
        return Selection(selection).getComponents()

    def getDeformerSet(self):
        """このデフォーマーの所属を保持するobjectSetを取得する。

        Returns:
            ObjectSet | None: 所属セット。コンポーネントタグ方式などでセットを持たない場合はNone。

        Raises:
            RuntimeError: デフォーマーが無効な場合。
        """
        fn = self._deformer_fn()
        try:
            node = fn.deformerSet
        except RuntimeError:
            # コンポーネントタグ方式では、セット不在をMayaがRuntimeErrorで通知する。
            return None
        return None if node.isNull() else Node(node)

    def getDeformerWeights(self, *, geometryIndex=None):
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
        plug, count = self._deformer_weight_plug(self._default_geometry_index(geometryIndex))
        values = [1.0] * count
        for index in plug.getExistingArrayAttributeIndices():
            if index < count:
                values[index] = plug.elementByLogicalIndex(index).asFloat()
        return values

    def setDeformerWeights(self, weights, *, vertices=None, geometryIndex=None, fast=False, check=False):
        """頂点ごとのデフォーマーのウェイトを設定する。

        通常は ``cmds.setAttr`` で書き込む。番号が1ずつ続く頂点は、範囲を指定した1回のsetAttrにまとめる。

        Args:
            weights (Iterable[float]): 書き込む値。有限な数値を、verticesと同じ数だけ渡す。
                verticesがNoneなら、形状の点の数だけ渡す。
            vertices (Component | Components | Iterable[int] | None): 書き込む頂点(点)の番号。Noneなら全頂点。
                同じ番号を2回指定できない。指定した順にweightsと対応する。
            geometryIndex (int | None): 変形する形状の番号(``input``・``weightList`` の論理番号)。既定はNone(先頭の形状)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

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
        _require_bool(check, "check")
        with _edit_context("mlibGeometryFilterSetDeformerWeights", fast):
            geometryIndex = self._default_geometry_index(geometryIndex)
            plug, count = self._deformer_weight_plug(geometryIndex)
            if vertices is None:
                indices = list(range(count))
            else:
                shape = oma2.MFnGeometryFilter(self.mnode()).outputShapeAtIndex(geometryIndex)
                indices = self._resolve_point_indices(vertices, count, shape)
            values = self._resolve_weight_values(weights, len(indices))
            if fast:
                self._set_deformer_weights_fast(plug, indices, values, check)
            else:
                if check:
                    # 範囲ごとに分けて書くので、途中で止まらないよう書く前に全部の要素を確かめる。
                    for index in indices:
                        require_writable(plug.elementByLogicalIndex(index))
                self._set_deformer_weights_cmds(geometryIndex, indices, values)

    def dumpDeformerWeights(self, path, *, geometryIndex=None, all=False):
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
        # 循環参照の回避: mlib.json はnodesを読み込むため、使う時点で読み込む。
        from ..json.file import _require_path

        destination = _require_path(path)
        _require_bool(all, "all")
        if all:
            if geometryIndex is not None:
                raise TypeError("allとgeometryIndexは同時に指定できません")
            indices = self._geometry_indices()
        else:
            indices = [self._default_geometry_index(geometryIndex)]
        geometries = []
        for index in indices:
            values = self.getDeformerWeights(geometryIndex=index)
            geometries.append({"index": index, "numVertices": len(values), "weights": values})
        payload = {"version": _DEFORMER_WEIGHTS_VERSION, "deformer": self.getName(), "geometries": geometries}
        destination.write_text(json.dumps(payload), encoding="utf-8")

    def loadDeformerWeights(self, path, *, fast=False, check=False):
        """JSONファイルからデフォーマーのウェイトを読み込んで設定する。

        :meth:`dumpDeformerWeights` が書き出したファイルを読む。
        ファイルの各形状は、形状の番号(``weightList`` の論理番号)と頂点数が合うかを確かめてから書き込む。
        デフォーマー名は比べないので、別のデフォーマーへも読み込める。

        書き込む前に全部の形状を確かめ、合わないものがあれば何も変えずにValueErrorにする。
        通常は、全部の形状の書き込みを1回のUndoにまとめる。

        Args:
            path (str | os.PathLike): 読み込むファイルパス。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、全部の形状の要素へ書き込めるか(ロック・入力の接続が無いか)を確かめて、
                問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

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
        # 循環参照の回避: mlib.json はnodesを読み込むため、使う時点で読み込む。
        from ..json.file import _require_path

        _require_bool(check, "check")
        with _edit_context("mlibGeometryFilterLoadDeformerWeights", fast):
            source = _require_path(path)
            self._geometry_indices()
            try:
                payload = json.loads(source.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}をJSONとして読み込めません: {error}") from error
            if not isinstance(payload, dict) or payload.get("version") != _DEFORMER_WEIGHTS_VERSION:
                raise ValueError(f"対応していないデフォーマーのウェイトのファイルです: {path}")
            geometries = payload.get("geometries")
            if not isinstance(geometries, list):
                raise ValueError(f"デフォーマーのウェイトのファイルにジオメトリがありません: {path}")
            plans = []
            for entry in geometries:
                index = entry.get("index") if isinstance(entry, dict) else None
                if isinstance(index, bool) or not isinstance(index, int):
                    raise ValueError(f"{path}のジオメトリの項目が不正です")
                try:
                    plug, count = self._deformer_weight_plug(index)
                except IndexError:
                    raise ValueError(f"番号{index}のジオメトリはありません: {self._full_name()}") from None
                values = entry.get("weights")
                if entry.get("numVertices") != count or not isinstance(values, list) or len(values) != count:
                    raise ValueError(f"保存された頂点数({entry.get('numVertices')})がジオメトリ{index}の頂点数({count})と合っていません")
                plans.append((index, plug, self._resolve_weight_values(values, count)))
            if check:
                # 形状ごとに分けて書くので、途中で止まって一部だけ書き換わらないよう、全部を先に確かめる。
                for _, plug, values in plans:
                    for vertex in range(len(values)):
                        require_writable(plug.elementByLogicalIndex(vertex))
            for index, _, values in plans:
                self.setDeformerWeights(values, geometryIndex=index, fast=fast)

    def copyDeformerWeightsTo(self, other, *, geometryIndex=None, otherGeometryIndex=None, fast=False, check=False):
        """デフォーマーのウェイトを別のデフォーマーへ写す。

        写す先は、頂点数が同じ別のデフォーマーか、同じデフォーマーの別の形状。
        頂点番号どうしで対応させ、位置では合わせない。通常は1回のUndoで戻せる。

        Args:
            other (GeometryFilter | str): 写す先のデフォーマー。
            geometryIndex (int | None): 写す元(自身)の形状の番号。既定はNone(先頭の形状)。
            otherGeometryIndex (int | None): 写す先の形状の番号。既定はNone(先頭の形状)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。:meth:`setDeformerWeights` の ``check`` と同じ。

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
        _require_bool(check, "check")
        with _edit_context("mlibGeometryFilterCopyDeformerWeightsTo", fast):
            target = other if isinstance(other, GeometryFilter) else Node(Object._input_name(other))
            if not isinstance(target, GeometryFilter):
                raise TypeError(f"otherはデフォーマーで指定してください: {target.getType()}: {target._full_name()}")
            values = self.getDeformerWeights(geometryIndex=geometryIndex)
            otherGeometryIndex = target._default_geometry_index(otherGeometryIndex)
            _, count = target._deformer_weight_plug(otherGeometryIndex)
            if count != len(values):
                raise ValueError(f"頂点数が違います: {len(values)}と{count}")
            target.setDeformerWeights(values, geometryIndex=otherGeometryIndex, fast=fast, check=check)
            return target

    def _deformer_fn(self):
        """有効性を確かめてデフォーマーのfunction setを取得する。

        Returns:
            oma2.MFnGeometryFilter: このノードのfunction set。
        """
        self._require_valid("ジオメトリの取得")
        return oma2.MFnGeometryFilter(self.mnode())

    @staticmethod
    def _require_geometry_index(fn, geometry_index):
        """出力に実在する論理番号かを確かめる。

        Args:
            fn (oma2.MFnGeometryFilter): 有効なデフォーマー。
            geometry_index (int): 出力の論理番号。
        """
        if isinstance(geometry_index, bool) or not isinstance(geometry_index, int):
            raise TypeError("geometryIndexはintで指定してください")
        indices = [fn.indexForOutputConnection(i) for i in range(fn.numOutputConnections())]
        if geometry_index not in indices:
            raise IndexError(f"指定した論理番号のジオメトリがありません: {geometry_index}")

    @classmethod
    def _resolve_geometry_index(cls, fn, geometry_index):
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
        if geometry_index is None:
            if not fn.numOutputConnections():
                raise IndexError("変形する形状がありません")
            return fn.indexForOutputConnection(0)
        cls._require_geometry_index(fn, geometry_index)
        return geometry_index

    def _default_geometry_index(self, geometry_index):
        """geometryIndexの既定(None)を先頭の形状の論理番号にする。int・それ以外の値はそのまま返す(呼び出し側で確かめる)。

        Args:
            geometry_index (int | None): 形状の番号の指定。

        Returns:
            int | object: Noneなら先頭の形状の論理番号、それ以外はそのままの値。

        Raises:
            IndexError: Noneで、形状が1つも無い場合。
        """
        if geometry_index is not None:
            return geometry_index
        return self._resolve_geometry_index(self._deformer_fn(), None)

    def _geometry_indices(self):
        """変形する形状の番号(``input``・``weightList`` の論理番号)を昇順で返す。

        Returns:
            list[int]: 番号。

        Raises:
            TypeError: デフォーマーのウェイトを持たない型の場合。
        """
        if self.isType("skinCluster") or not self.hasAttr("weightList"):
            raise TypeError(f"{self.getType()}にデフォーマーのウェイトはありません: {self._full_name()}")
        fn = oma2.MFnGeometryFilter(self.mnode())
        return sorted(fn.indexForOutputShape(shape) for shape in fn.getOutputGeometry())

    def _deformer_weight_plug(self, geometry_index):
        """``weightList[geometry_index].weights`` の Plug と、形状の点の数を返す。

        Args:
            geometry_index (int): 変形する形状の番号。

        Returns:
            tuple[om2.MPlug, int]: weights のマルチアトリビュートの Plug と点の数。

        Raises:
            TypeError: geometry_index が int でない、またはデフォーマーのウェイトを持たない型の場合。
            IndexError: 形状が無い場合。
        """
        if isinstance(geometry_index, bool) or not isinstance(geometry_index, int):
            raise TypeError(f"geometryIndexはintで指定してください: {type(geometry_index).__name__}")
        if self.isType("skinCluster") or not self.hasAttr("weightList"):
            raise TypeError(f"{self.getType()}にデフォーマーのウェイトはありません: {self._full_name()}")
        try:
            shape = oma2.MFnGeometryFilter(self.mnode()).outputShapeAtIndex(geometry_index)
        except RuntimeError:
            raise IndexError(f"番号{geometry_index}のジオメトリはありません: {self._full_name()}") from None
        count = om2.MItGeometry(om2.MDagPath.getAPathTo(shape)).exactCount()
        weight_list = self._dependency_fn().findPlug("weightList", False)
        return weight_list.elementByLogicalIndex(geometry_index).child(0), count

    @staticmethod
    def _resolve_point_indices(vertices, count, shape):
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
        owners = [vertices] if hasattr(vertices, "shape") else [item for item in vertices if hasattr(item, "shape")]
        for owner in owners:
            if owner.shape.mnode() != shape:
                raise ValueError(f"verticesは変形する形状のものを指定してください: {owner.shape.getName()}")
        if hasattr(vertices, "indices"):
            vertices = vertices.indices
        elif isinstance(getattr(vertices, "index", None), int):
            vertices = [vertices.index]
        indices = []
        for item in vertices:
            value = item
            if not isinstance(item, int) and isinstance(getattr(item, "index", None), int):
                value = item.index
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"vertexはintで指定してください: {type(value).__name__}")
            if not 0 <= value < count:
                raise IndexError(f"頂点番号が範囲外です: {value}")
            indices.append(value)
        if len(set(indices)) != len(indices):
            raise ValueError("verticesに重複は指定できません")
        return indices

    @staticmethod
    def _resolve_weight_values(weights, count):
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
        values = []
        for value in weights:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"weightは数値で指定してください: {type(value).__name__}")
            if not math.isfinite(value):
                raise ValueError(f"weightは有限な数値で指定してください: {value}")
            values.append(float(value))
        if len(values) != count:
            raise ValueError(f"ウェイトを{count}個指定してください: {len(values)}個")
        return values

    def _set_deformer_weights_fast(self, plug, indices, values, check=False):
        """全要素の範囲(check=Trueなら書込み可否も)を先に調べてから、OpenMaya で書き込む。

        Args:
            plug (om2.MPlug): ``weightList[g].weights`` の Plug。
            indices (list[int]): 頂点番号。
            values (list[float]): 値。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

        Returns:
            None: 値を返さない。
        """
        edits = []
        for index, value in zip(indices, values):
            element = plug.elementByLogicalIndex(index)
            if check:
                require_writable(element)
            require_range(element, value)
            edits.append((element, value))
        for element, value in edits:
            element.setFloat(value)

    def _set_deformer_weights_cmds(self, geometry_index, indices, values):
        """番号が1ずつ増える頂点を範囲にまとめ、cmds で書き込む。

        Args:
            geometry_index (int): 変形する形状の番号。
            indices (list[int]): 頂点番号。
            values (list[float]): 値。

        Returns:
            None: 値を返さない。
        """
        prefix = f"{self._full_name()}.weightList[{geometry_index}].weights"
        start = 0
        while start < len(indices):
            end = start + 1
            while end < len(indices) and indices[end] == indices[end - 1] + 1:
                end += 1
            if end - start == 1:
                set_attr(f"{prefix}[{indices[start]}]", values[start])
            else:
                set_attr(f"{prefix}[{indices[start]}:{indices[end - 1]}]", *values[start:end])
            start = end
