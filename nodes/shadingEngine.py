"""マテリアル接続と形状への割り当てを扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.object import Object
from ..decorator import _edit_context, _require_bool, undoTransaction
from .node import Node
from .objectSet import ObjectSet


class ShadingEngine(ObjectSet):
    """Mayaのレンダー用のセット(shadingEngine)を扱うクラス。

    表面・ボリューム・ディスプレイスメントの3種類のシェーダーを接続して持つ。
    マテリアルを割り当てるには、まず :meth:`setShader` でシェーダーを接続し、
    次に :meth:`assign` で形状やフェースへ割り当てる。

    .. code-block:: python

        import maya.cmds as cmds
        import mlib
        from mlib.nodes import ShadingEngine

        shader = mlib.createNode("lambert", name="red_MAT")
        shader.getPlug("color").set((1, 0, 0))
        engine = ShadingEngine(cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="red_SG"))
        engine.setShader(shader)        # shader.outColor -> red_SG.surfaceShader
        engine.assign(mlib.getNode("pCube1"))  # 形状全体。フェースは Face/Faces や "pCube1.f[0:3]"
    """

    def getShader(self, kind="surface", *, plug=False):
        """接続しているシェーダーのノードを取得する。``plug=True`` なら、シェーダーの出力アトリビュートを取得する。

        Args:
            kind (str): シェーダーの種類。surface・volume・displacementのどれか。既定はsurface。
            plug (bool): Trueなら、ノードの代わりに接続元の出力のPlugを返す。既定はFalse。

        Returns:
            Node | Plug | None: シェーダーのノード。ノード型に合ったクラスのオブジェクトになる。接続されていなければNone。
                plug=Trueなら、接続元の出力のPlug。

        Raises:
            TypeError: plugがboolでない場合。
            ValueError: kindがsurface/volume/displacement以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        _require_bool(plug, "plug")
        source = self.getPlug(self._shader_attribute(kind)).getConnections(input=True)
        if plug or source is None:
            return source
        return source.getNode()

    def setShader(self, shader, kind="surface", output=None, *, fast=False):
        """シェーダーを接続する。

        例えば ``engine.setShader(lambert)`` は、``lambert.outColor`` を ``surfaceShader`` へ接続する。
        すでにある接続は置き換える。同じ接続元がすでに接続されていれば、何も変えない。
        形状への割り当ては :meth:`assign` で行う(クラスの説明の例を参照)。

        Args:
            shader (Node | Plug | str): シェーダーのノード、またはその出力のPlug。
            kind (str): シェーダーの種類。surface・volume・displacementのどれか。既定はsurface。
            output (str | None): shaderにノードを渡したときに使う出力のアトリビュート名。
                Noneならdisplacementではdisplacement、それ以外ではoutColorを使う。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: kindが対応していない値の場合。
            RuntimeError: 接続元と接続先が同じアトリビュートの場合(fastの指定に関係なく)、
                またはMayaが接続を拒否した場合。
        """
        with _edit_context("mlibShadingEngineSetShader", fast):
            # plugs は nodes を参照するため、循環importを避けて呼出し時に取得する。
            from ..plugs.plug import Plug

            target = self.getPlug(self._shader_attribute(kind))
            if isinstance(shader, Plug) or (isinstance(shader, str) and "." in shader):
                source = Plug._resolve_input(shader)
            else:
                source = Node._resolve_input(shader).getPlug(output or ("displacement" if kind == "displacement" else "outColor"))
            if source == target:
                # fastのMDGModifierは自己接続を拒否しないため、cmdsの経路と同じく先に拒否する。
                raise RuntimeError(f"アトリビュート{target._full_name()}を自分自身へは接続できません")
            # 同じ割り当ての再実行は、既存の同じ接続をそのまま残して成功させる。
            source.connectTo(target, force=True, skipExisting=True, fast=fast)

    def assign(self, targets):
        """形状またはフェースへ割り当てる。

        すでにある割り当ては、この割り当てに置き換わる。``cmds.sets(forceElement=...)`` と同じ。
        例えば ``engine.assign(mlib.getNode("pCube1"))`` は形状全体へ、
        ``engine.assign("pCube1.f[0:3]")`` はそのフェースだけへ割り当てる。
        シェーダーの接続は :meth:`setShader` で行う(クラスの説明の例を参照)。
        OpenMayaでの割り当ては ``cmds.sets`` より遅いため、fast引数は持たない。

        Mayaは割り当てられない対象(頂点・形状の無いTransformなど)を警告だけで飛ばすため、割り当てた後に
        対象ごとに所属を確かめる。割り当てられなかった対象があれば、Undoで割り当てをすべて戻してから
        RuntimeErrorにする(undoTransactionと同じく、Undoが有効なことが前提)。

        Args:
            targets (Node | Face | Faces | str | Iterable): 割り当てる対象。選択されているものには関係しない。
                Transformを渡すと、その下の中間オブジェクトでない形状へ割り当てる。

        Returns:
            None: 値を返さない。targetsが空なら何も変えない。

        Raises:
            TypeError: DAGでないノード(DGノード・セットなど)やPlugを渡した場合。何も変えない。
            RuntimeError: Mayaが割り当てなかった対象(頂点・形状の無いTransformなど)がある場合。
                割り当てた分も戻す。
        """
        names = Object._input_names(targets, allow_plugs=False)
        for name in names:
            selection = om2.MSelectionList()
            try:
                selection.add(name)
            except RuntimeError:
                # 見つからない名前は、これまでどおりMayaの例外に任せる。
                continue
            try:
                selection.getDagPath(0)
            except TypeError:
                raise TypeError(f"ShadingEngineへ割り当てられるのは形状・フェースです: {name}") from None
        if not names:
            return
        engine = self._full_name()
        with undoTransaction("mlibShadingEngineAssign"):
            cmds.sets(names, edit=True, forceElement=engine)
            rejected = [name for name in names if not self._is_assigned(name, engine)]
            if rejected:
                raise RuntimeError(f"Mayaが割り当てなかった対象があります: {', '.join(rejected)}")

    def getMembers(self, *, flatten=False, dagOnly=False, shadingOnly=False):
        """割り当てている先を取得する。

        Args:
            flatten (bool): 指定できない(割り当て先は入れ子のセットを持たない)。既定False。
            dagOnly (bool): Trueなら、:meth:`ObjectSet.getMembers` と同じく、DAGパスだけをNodesで返す。既定False。
            shadingOnly (bool): dagOnly=Trueのときに、Trueならマテリアルの割り当てに関係するDAGパスだけを返す。既定False。

        Returns:
            list[Node | Face] | Nodes[DagNode]: 形状全体に割り当てていればそのノード、フェースに割り当てていれば
                フェース1つずつのオブジェクト。どれもインスタンスのDAGパスを保つ。
                dagOnly=Trueなら、Mayaの順に並ぶパスごとのノードの集まり。

        Raises:
            TypeError: flattenを指定した場合、dagOnly・shadingOnlyがboolでない場合、
                またはdagOnly=TrueなしでshadingOnlyを指定した場合。
            NotImplementedError: dagOnly=Trueで、使っているMayaに対応するAPI 2.0のメソッドが無い場合。
        """
        if flatten is not False:
            raise TypeError("ShadingEngine.getMembers()にflattenは指定できません")
        if dagOnly is not False or shadingOnly is not False:
            return super().getMembers(dagOnly=dagOnly, shadingOnly=shadingOnly)
        selection = om2.MFnSet(self.mnode()).getMembers(False)
        result = []
        for index in range(selection.length()):
            path, component = selection.getComponent(index)
            # 選択リストから取得したばかりのパスなので、入力の再解決を省いてラッパーにする。
            node = Node._wrap_dag_path(path)
            if component.hasFn(om2.MFn.kMeshPolygonComponent):
                fn = om2.MFnSingleIndexedComponent(component)
                indices = range(om2.MFnMesh(path).numPolygons) if fn.isComplete else fn.getElements()
                result.extend(node.getFaces(value) for value in indices)
            else:
                result.append(node)
        return result

    @staticmethod
    def _is_assigned(name, engine):
        """1つの対象が、割り当てた後にこのシェーディングエンジンへ所属しているかを返す。

        Transformはそれ自身ではなく形状が所属するので、中間オブジェクトでない形状がすべて所属しているかを見る。

        Args:
            name (str): 割り当てた対象の名前。
            engine (str): シェーディングエンジンの名前。

        Returns:
            bool: 所属していればTrue。
        """
        if cmds.sets(name, isMember=engine):
            return True
        if "." in name or not cmds.objectType(name, isAType="transform"):
            return False
        shapes = cmds.listRelatives(name, shapes=True, noIntermediate=True, fullPath=True) or []
        return bool(shapes) and all(cmds.sets(shape, isMember=engine) for shape in shapes)

    @staticmethod
    def _shader_attribute(kind):
        """シェーダーの種類を、接続先のアトリビュート名へ変える。

        Args:
            kind (str): surface・volume・displacementのどれか。

        Returns:
            str: 接続先のアトリビュート名。

        Raises:
            ValueError: kindが対応していない値の場合。
        """
        if kind not in ("surface", "volume", "displacement"):
            raise ValueError("kindはsurface・volume・displacementのどれかで指定してください")
        return kind + "Shader"
