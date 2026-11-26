"""マルチアトリビュートの論理番号と、要素のPlugを扱う。"""

import operator
from contextlib import nullcontext

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.attributeType import _convert_angles, _convert_times, _convert_units, _plain_angle_unit, _plain_time_unit, is_internal_data_type, value_reader
from ..decorator import _edit_context, _require_bool, undoChunk
from .plug import MAX_LOGICAL_INDEX, Plug, Plugs, _instance_count


def _descendants(mplug, steps=()):
    """Plug自身と、その下のPlugを深さ優先で1つずつ返す。

    下へたどるのは、コンパウンドアトリビュートの子と、マルチアトリビュートのすでにある要素。

    Args:
        mplug (om2.MPlug): 起点のPlug。
        steps (tuple[tuple[str, int], ...]): 起点までのたどり方(``("child", 番号)``・``("element", 論理番号)``)。

    Yields:
        tuple[tuple[tuple[str, int], ...], om2.MPlug]: 起点からのたどり方と、Plug。
    """
    yield steps, mplug
    if mplug.isArray:
        for index in mplug.getExistingArrayAttributeIndices():
            yield from _descendants(mplug.elementByLogicalIndex(index), (*steps, ("element", index)))
    elif mplug.isCompound:
        for index in range(mplug.numChildren()):
            yield from _descendants(mplug.child(index), (*steps, ("child", index)))


def _follow(mplug, steps):
    """_descendants のたどり方に従って、別の要素から同じ位置のPlugを取得する。

    要素は作らない。

    Args:
        mplug (om2.MPlug): 起点のPlug。
        steps (tuple[tuple[str, int], ...]): たどり方。

    Returns:
        om2.MPlug: たどった先のPlug。
    """
    for kind, index in steps:
        mplug = mplug.child(index) if kind == "child" else mplug.elementByLogicalIndex(index)
    return mplug


class MultiPlug(Plug):
    """マルチアトリビュート全体を扱うPlug。とびとびの論理番号と、要素のPlugを扱う。

    doubleArrayなど、1つのPlugが持つ並びのデータとは別のもの。

    - ``multi[index]`` は、論理番号で要素を取得する。
    - 反復すると、すでにある要素を返す。
    - get()は値を取得する。

    欠けている番号の要素は、取得しただけでは作られず、set・connectしたときに作られる。
    maya.cmdsへは ``str(multi)`` で渡す。要素がコンパウンドアトリビュートのPlugでも文字列にして渡す。
    mlib.selectにはそのまま渡せる。
    """

    def __getitem__(self, index):
        """論理番号で、マルチアトリビュートの要素を取得する。

        すでにある要素も、まだ作られていない要素も取得できる。番号はリスト上の位置ではない。
        たとえば、すでにある番号が[2, 10]なら、[10]で後ろの要素を取得する。
        取得しただけでは値を読み出さず、欠けている番号の要素も作らない。要素はset・connectしたときに作られる。

        Args:
            index (int): 0〜2147483647の論理番号。負の数とsliceは使えない。

        Returns:
            Plug: 要素の新しいオブジェクト。ノードはマルチアトリビュートと共有し、値やノードを複製するわけではない。
                worldSpaceの要素の番号を指定しても、ノードが持つDAGパスは切り替えない。

        Raises:
            TypeError: indexがboolの場合、または整数でない場合。
            IndexError: 論理番号が0〜2147483647の範囲外の場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        self._require_valid()
        index = self._validated_logical_index(index)
        return Plug(self._node, self._mplug.elementByLogicalIndex(index))

    def __contains__(self, item):
        """論理番号または要素のPlugが、すでにある要素に含まれるか判定する。

        - 整数は論理番号として、getIndices()と比べる。リスト上の位置ではない。
        - Plugは、このマルチアトリビュートのすでにある要素と同じものかを比べる。

        値は読み出さず、欠けている番号の要素も作らない。

        ``__len__`` は持たない。持つとmaya.cmdsが位置0〜len-1の並びとして展開し、
        論理番号と食い違う値を黙って返してしまうため。要素の数は ``len(multi.getIndices())`` で求める。

        Args:
            item (int | Plug): 論理番号、または要素のPlug。

        Returns:
            bool: すでにある要素に含まれればTrue。範囲外の番号や、別のアトリビュートのPlugはFalse。

        Raises:
            TypeError: boolの場合、または整数でもPlugでもない場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        if isinstance(item, Plug):
            self._require_valid()
            if not item.isValid() or not item.isMulti(element=True):
                return False
            return item.getMulti() == self and item.getIndex() in self.getIndices()
        if isinstance(item, bool):
            raise TypeError("論理番号は整数か要素のPlugで指定してください")
        try:
            index = operator.index(item)
        except TypeError:
            raise TypeError("論理番号は整数か要素のPlugで指定してください") from None
        return index in self.getIndices()

    def __iter__(self):
        """すでにある要素を、論理番号の順に1つずつ返す。

        反復を始めた時点のgetElement()(すでにある要素の一覧)の結果を使う。欠けている番号は返さない。要素の値は読み出さない。

        Returns:
            Iterator[Plug]: 反復を始めた時点で集めた要素のイテレーター。
        """
        return iter(self.getElement())

    def get(self, *, unit=None, timeUnit=None, uiUnits=False, time=None):
        """すでにある要素の値を、論理番号をキーにしたdictで取得する。

        すでにある要素(getElement())ごとに値を読むので、DGの評価が起きることがある。
        番号は詰め直さない。要素がコンパウンドアトリビュートや ``doubleArray`` などのデータ型でも、
        値を平らにならさない。

        Args:
            time (float | om2.MTime | None): 評価する時刻。数値はUI時間単位のフレーム。Noneは現在の評価コンテキスト。
                現在フレームは動かさない。timeUnitは返す値の換算用で、評価時刻には適用しない。
                シミュレーションの順次再生と同じ結果は保証しない。
            unit (str | None): 各要素のgetへ渡す角度の単位。None(既定)は度、``"rad"`` はラジアン。
                uiUnits=Trueとは同時に指定できない。
            timeUnit (str | None): 各要素のgetへ渡す時間の単位。None(既定)は現在のUIの時間単位でのフレーム、
                ``"sec"`` は秒。uiUnits=Trueとは同時に指定できない。
            uiUnits (bool): 各要素のgetへ渡す。TrueならUIの単位。
                既定はFalseで、角度は度、距離はcm、時間はフレームになる。

        Returns:
            dict[int, object]: 新しいdict。値の型と単位は各要素のgetのとおり。
                worldSpaceのアトリビュートでは、DAGのインスタンス番号の要素も含む。

        Raises:
            TypeError: uiUnitsがboolでない場合、またはunit・timeUnitが文字列でもNoneでもない場合。
            ValueError: unit・timeUnitが対応していない単位名の場合、またはuiUnits=Trueと同時に指定した場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合、または要素の値を取得できない場合。
            NotImplementedError: 指定時刻の取得に対応しない型(cmdsで読むgeneric・messageなど)の場合。

        """
        if time is not None:
            return self._get_at_time(time, unit, timeUnit, uiUnits)
        _require_bool(uiUnits, "uiUnits")
        angle_unit = _plain_angle_unit(unit, uiUnits)
        time_unit = _plain_time_unit(timeUnit, uiUnits)
        if type(self).getElement is not MultiPlug.getElement:
            return {plug.mplug().logicalIndex(): plug.get(unit=unit, timeUnit=timeUnit, uiUnits=uiUnits) for plug in self.getElement()}
        indices = self.getIndices()
        if not indices:
            return {}
        # 要素は同じアトリビュート定義を共有するため、ラッパーの型と読取関数は全要素で同じになる。
        # 基底Plugの読取(get/_get_value)をそのまま使う型に限り、2個目以降のラッパー作成を省いて
        # 同じ手順(有効性の確認→読取関数→単位換算)で読む。それ以外は従来どおり要素ごとのget。
        mplug = self._mplug
        first = Plug(self._node, mplug.elementByLogicalIndex(indices[0]))
        element_class = type(first)
        reader = None
        if element_class.get is Plug.get and element_class._get_value is Plug._get_value and element_class._require_valid is Plug._require_valid:
            first._require_valid()
            reader = first._reader
            if reader is None:
                reader = first._reader = value_reader(first._attribute)
        if not reader:
            elements = [first] + [Plug(self._node, mplug.elementByLogicalIndex(index)) for index in indices[1:]]
            return {plug.mplug().logicalIndex(): plug.get(unit=unit, timeUnit=timeUnit, uiUnits=uiUnits) for plug in elements}
        result = {}
        for index in indices:
            element = mplug.elementByLogicalIndex(index)
            first._require_valid()
            value = reader(element)
            if uiUnits:
                result[element.logicalIndex()] = _convert_units(element, value)
            else:
                value = _convert_angles(element, value, angle_unit, to_internal=False)
                result[element.logicalIndex()] = _convert_times(element, value, time_unit, to_internal=False)
        return result

    def getElementCount(self, *, evaluate=False):
        """Mayaが保持するマルチアトリビュートの要素数を取得する。

        既定では未評価の接続要素を数えない場合がある。evaluate=Trueでは接続要素を評価してから数える。
        getIndicesのインスタンス要素補完は行わず、MPlugの保持状態をそのまま返す。

        Args:
            evaluate (bool): Trueなら接続要素を評価する。既定False。

        Returns:
            int: 要素数。最大の論理番号とは異なる。

        Raises:
            TypeError: evaluateがboolでない場合。
            RuntimeError: Plugが無効、または評価できない場合。
        """
        _require_bool(evaluate, "evaluate")
        self._require_valid("要素数の取得")
        return self._mplug.evaluateNumElements() if evaluate else self._mplug.numElements()

    def getElement(self, index=None, *, physical=False):
        """要素を取得する。番号を渡すとその要素、省略するとすでにある要素をすべて返す。

        値の評価も、要素の作成もしない。

        - ``getElement(index)``: 論理番号で要素を1つ取得する(``multi[index]`` と同じ)。
          まだ無い要素(欠けている番号)も取得でき、その要素へset・connectしたときに作られる。
        - ``getElement()``: すでにある要素だけを、論理番号の小さい順にPlugsで返す(``for plug in multi`` と同じ要素)。
          :meth:`getIndices` の番号の要素だけで、欠けている番号は埋めない。
          worldSpaceのアトリビュートでは、評価の前でもDAGのインスタンス番号の要素を含む。
        - ``getElement(index, physical=True)``: 論理番号でなく、Mayaが保持している要素の並びでの位置(物理番号)で取得する。
          物理番号は論理番号の小さい順とは限らず、要素の追加・削除のあとも同じ要素を指す番号ではない。

        ある番号の要素がすでにあるかどうかは ``index in multi`` で判定する。

        Args:
            index (int | None): 0〜2147483647の論理番号。``physical=True`` なら、0以上、
                :meth:`getElementCount` 未満の物理番号。既定はNoneで、すでにある要素をすべて返す。
            physical (bool): Trueなら、indexを物理番号として扱う。既定はFalse。indexを省略したときは指定できない。

        Returns:
            Plug | Plugs: 要素の新しいオブジェクト。ノードはマルチアトリビュートと同じもので、シーンのものを複製しない。
                indexを省略したときは、すでにある要素のPlugs。

        Raises:
            TypeError: indexがboolの場合、整数でもNoneでもない場合、physicalがboolでない場合、
                またはindexを省略して ``physical=True`` を指定した場合。
            IndexError: 論理番号が0〜2147483647の範囲外の場合、または物理番号が範囲外の場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        _require_bool(physical, "physical")
        if index is None:
            if physical:
                raise TypeError("physical=Trueにはindexを指定してください")
            # 要素ごとに存在を確かめ直さず、既存の番号から直接 Plug を作る。
            return Plugs._from_plugs([Plug(self._node, self._mplug.elementByLogicalIndex(i)) for i in self.getIndices()])
        if not physical:
            return self[index]
        self._require_valid("要素の取得")
        index = self._validated_logical_index(index)
        if index >= self._mplug.numElements():
            raise IndexError("物理番号がマルチアトリビュートの範囲外です")
        return Plug(self._node, self._mplug.elementByPhysicalIndex(index))

    def getNextAvailable(self, start=-1, *, checkLocked=True, checkChildren=True, vacant=False):
        """次に使える、マルチアトリビュートの要素のPlugを探す。

        要素を作ったり、予約したりはしない。論理番号は、戻り値の
        :meth:`~mlib.plugs.plug.Plug.getIndex` で取得する(``multi.getNextAvailable().getIndex()``)。
        番号を返す指定(``asPlug`` 引数)は無い。

        既定(``vacant=False``)は、``cmds.connectAttr(nextAvailable=True)`` と同じ決まりで探す。
        :meth:`Plug.connectTo` / :meth:`Plug.connect` の ``nextAvailable=True`` も、この結果へ接続する。

        - 入力の接続が無い要素は使える。値を持つだけの要素や、出力の接続だけがある要素も候補になる。
        - ``start`` が負なら、接続(子の接続を含む)のある最後の要素の次から探す。途中の空きは飛ばす。
        - ``checkLocked`` ならロックされた要素を避ける。
        - ``checkChildren`` なら、子(とそのマルチアトリビュート)の入力の接続とロックも避ける。

        ``vacant=True`` は、Mayaの決まりとは別に「使われていない番号」を探す。すでにある番号
        (``getExistingArrayAttributeIndices()``。値を持つ要素も含む)に無い、最初の番号を返す。

        - ``start`` が負なら0から探す。
        - checkLocked・checkChildren は無視し、マルチアトリビュートのロックも例外にしない。
        - worldSpaceのマルチアトリビュートでの、インスタンス番号の補い(:meth:`getIndices`)も使わない。

        値を設定するための空いた要素を探すときに使う。

        3つの探し方の比較:

        .. list-table::
           :header-rows: 1

           * - 呼び方
             - 開始
             - 避けるもの
           * - ``getNextAvailable()``
             - 最後の接続要素の次(start<0)
             - 入力接続・ロック・子の入力
           * - ``getNextAvailable(vacant=True)``
             - 0(start<0)
             - 既存番号(値・接続のある要素)
           * - ``appendMessage(node)``
             - 最大番号+1
             - 既存番号すべて(穴は再利用しない)

        Args:
            start (int): 探し始める番号。負の数なら、上に書いた既定の位置から探す。bool は受け付けない。
            checkLocked (bool): Trueなら、ロックされた要素(とマルチアトリビュート全体のロック)を避ける。
                vacantでは無視する。
            checkChildren (bool): Trueなら、コンパウンドアトリビュートの子と、そのマルチアトリビュートも調べる。
                vacantでは無視する。
            vacant (bool): Trueなら、すでにある番号(値や接続のある要素)に無い、最初の番号を探す。

        Returns:
            Plug: 空いている番号の要素。まだ無い要素でも作らない。番号は ``getIndex()`` で取得する。

        Raises:
            TypeError: startがboolの場合や整数でない場合、またはcheckLocked・checkChildren・vacantがboolでない場合。
            IndexError: startが上限(2147483647)を超える場合、または空きが無い場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合。または ``vacant=False`` かつ
                ``checkLocked=True`` で、マルチアトリビュート全体がロックされている場合。
        """
        for name, flag in (("checkLocked", checkLocked), ("checkChildren", checkChildren), ("vacant", vacant)):
            _require_bool(flag, name)
        if isinstance(start, bool) or not isinstance(start, int):
            raise TypeError("startは整数で指定してください")
        self._require_valid()
        mp = self._mplug
        if vacant:
            existing = set(mp.getExistingArrayAttributeIndices())
            index = self._validated_logical_index(max(start, 0))
            while index in existing:
                index += 1
            if index > MAX_LOGICAL_INDEX:
                raise IndexError("マルチアトリビュートに空いている論理番号がありません")
            return Plug(self._node, mp.elementByLogicalIndex(index))
        if checkLocked and mp.isLocked:
            raise RuntimeError(f"マルチアトリビュートがロックされています: {self._full_name()}")
        if start < 0:
            count = mp.numConnectedElements()
            start = mp.connectionByPhysicalIndex(count - 1).logicalIndex() + 1 if count else 0
        index = self._validated_logical_index(start)

        def occupied(value):
            """子の階層も含めて、入力の接続とロックがあるか調べる。"""
            if value.isDestination or (checkLocked and value.isLocked):
                return True
            if checkChildren:
                if value.isArray:
                    return any(occupied(value.elementByLogicalIndex(i)) for i in value.getExistingArrayAttributeIndices())
                if value.isCompound:
                    return any(occupied(value.child(i)) for i in range(value.numChildren()))
            return False

        while index <= MAX_LOGICAL_INDEX:
            candidate = mp.elementByLogicalIndex(index)
            if not occupied(candidate):
                return Plug(self._node, candidate)
            index += 1
        raise IndexError("マルチアトリビュートに空いている論理番号がありません")

    def removeElement(self, index, shift=False, *, fast=False, breakConnections=True):
        """マルチアトリビュートの要素を削除する。

        削除できるのは、実際にある要素(OpenMayaが返す、すでにある要素の番号)だけ。
        worldSpaceでgetIndices()が補っただけの番号は削除の対象にしない。

        - 通常はcmds.removeMultiInstanceを使い、Undoが有効なら記録する。
        - fastではMDGModifierで削除し、Undoの設定は変えない。
        - ``shift=True`` なら、削除した番号より後ろのすでにある要素を、1つずつ前の番号へ移す。
          値と、入力・出力の接続を移す。移し方は :meth:`compact` と同じ。

        Args:
            index (int): 削除する論理番号。
            shift (bool): Trueなら、後ろの要素を1つずつ前へ詰める。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            breakConnections (bool): Trueなら接続を切る。Falseなら削除・移動対象に接続がある場合は更新前に拒否する。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: indexがboolの場合や整数でない場合、またはshift・fast・breakConnectionsがboolでない場合。
            IndexError: 論理番号が範囲外の場合、またはその番号の要素が実際には無い場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合、またはMayaが削除を拒否した場合。
                ``shift=True`` で、マルチアトリビュートか移す要素がロックされている場合や、
                リファレンスのノードの場合も含む。
            NotImplementedError: ``fast=True`` と ``shift=True`` を同時に指定した場合。

        Note:
            デフォーマーのターゲットは、この方法では取り除かない。たとえばblendShapeの ``weight`` の要素を
            消しても、エイリアスと ``inputTarget[].inputTargetGroup[i]`` が残る。blendShapeのターゲットは
            :meth:`mlib.nodes.BlendShape.removeTarget` で取り除く。
        """
        _require_bool(breakConnections, "breakConnections")
        _require_bool(shift, "shift")
        _require_bool(fast, "fast")
        if fast and shift:
            raise NotImplementedError("fastのremoveElementはshift=Trueに対応していません")
        with _edit_context("mlibMultiPlugRemoveElement", fast):
            self._require_valid()
            index = self._validated_logical_index(index)
            existing = sorted(self._mplug.getExistingArrayAttributeIndices())
            if index not in existing:
                raise IndexError(f"{self._full_name()}に論理番号{index}の要素はありません")
            moves = [(source, source - 1) for source in existing if source > index] if shift else []
            if not breakConnections:
                for target in [index] + [source for source, _ in moves]:
                    element = self._element_at(target)
                    if any(plug.isConnected() for plug in [element, *element.getDescendants()]):
                        raise RuntimeError("削除・移動対象の要素に接続があります")
            if shift:
                self._require_movable([index] + [source for source, _ in moves])
            if fast:
                modifier = om2.MDGModifier()
                modifier.removeMultiInstance(self._mplug.elementByLogicalIndex(index), breakConnections)
                modifier.doIt()
            else:
                cmds.removeMultiInstance(self._element_at(index)._full_name(), b=breakConnections)
                if moves:
                    self._move_elements(moves)

    def compact(self):
        """空いた番号を詰めて、要素の論理番号を0からの連番に並べ直す。

        すでにある要素を、論理番号の小さい順に0, 1, 2…へ移す。移すのは、各要素の値
        (コンパウンドアトリビュートの子と、入れ子のマルチアトリビュートの要素を含む)と、入力・出力の接続。
        すでに連番になっていれば何も変えない。cmdsで編集し、1回のUndoで戻せる。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。マルチアトリビュートか移す要素(子を含む)が
                ロックされている場合。またはリファレンスのノードの場合。

        Note:
            値はmlibの :meth:`~mlib.plugs.plug.Plug.get` / :meth:`~mlib.plugs.plug.Plug.set` で移す。
            書き込めない子・保存されない子の値と、接続の無いmessageの要素は移せない(messageの要素は移した先に作られない)。
            値を一度も設定していない要素は、移した先に値の無い要素として作る。
            同じマルチアトリビュートの要素どうしの接続は考慮していない。
            要素の下にマルチアトリビュートがある場合と、値の無い要素を元に無かった番号へ移した場合は、
            Undoで値と接続は戻るが、移した先の番号に空の要素が残ることがある
            (Mayaは子の要素への書き込みや、値の無い要素の作成をUndoしても、その要素を消さないため)。
        """
        with undoChunk("mlibMultiPlugCompact"):
            self._require_valid()
            existing = sorted(self._mplug.getExistingArrayAttributeIndices())
            moves = [(source, target) for target, source in enumerate(existing) if source != target]
            if moves:
                self._require_movable([source for source, _ in moves])
                self._move_elements(moves)

    def getSourceNodes(self):
        """各要素へつながっている接続元のノードを、論理番号の順に取得する。

        Returns:
            dict[int, Node]: 論理番号をキーにした接続元のノード。接続のある要素だけを含み、
                接続の無い番号は詰めずに抜けたままにする。
        """
        result = {}
        for element in self.getElement():
            source = element._source_plug(False)
            if source is not None:
                result[element.mplug().logicalIndex()] = source.getNode()
        return result

    def appendMessage(self, node, *, fast=False):
        """messageのマルチアトリビュートへ、ノードをつないで追加する。

        いちばん大きい番号の次の要素へ、ノードの ``message`` を接続する。

        Args:
            node (str | Node): つなぐノード。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            int: 追加した論理番号。途中の空いた番号は使わない。

        Raises:
            TypeError: messageのマルチアトリビュートでない場合、またはfastがboolでない場合。
            IndexError: 論理番号が上限に達した場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合、nodeが無い場合、または接続に失敗した場合。
        """
        _require_bool(fast, "fast")
        with nullcontext() if fast else undoChunk("mlibMultiPlugAppendMessage"):
            # 循環import(nodes → plugs)を避けるため、使う時点で読み込む。
            from ..nodes.node import Node

            self._require_valid()
            if not self._mplug.attribute().hasFn(om2.MFn.kMessageAttribute):
                raise TypeError("messageのマルチアトリビュートを指定してください")
            index = max(self.getIndices(), default=-1) + 1
            if index > MAX_LOGICAL_INDEX:
                raise IndexError("messageのマルチアトリビュートの論理番号が上限に達しました")
            Node(node).getPlug("message").connectTo(self._element_at(index), fast=fast)
            return index

    def getIndices(self, *, connected=False):
        """すでにある要素の論理番号を、小さい順に取得する。

        値は評価しない。番号がとびとびの[2, 10]なら[2, 10]を返し、並びの位置の[0, 1]へ詰め直さない。
        worldSpaceのマルチアトリビュートでは、OpenMayaが返す番号に、DAGのすべてのインスタンスの
        番号(0から数-1まで)を補う。祖先がインスタンス化されたことによる間接的なインスタンスも含む。
        欠けている番号の要素は作らない。getElement()(すでにある要素の一覧)も同じ番号を使う。

        ``connected=True`` なら、接続のある要素の番号だけを返す。要素自身か、その下(コンパウンドアトリビュートの子・
        入れ子の要素)に、入力か出力の接続がある要素が対象で、値だけを持つ要素は含まない
        (``MPlug.numConnectedElements`` / ``connectionByPhysicalIndex`` で求め、インスタンスの番号は補わない)。

        Args:
            connected (bool): Trueなら、接続のある要素の番号だけを返す。既定はFalse。

        Returns:
            list[int]: 論理番号の新しいリスト。``connected=True`` で接続が無ければ空リスト。

        Raises:
            TypeError: connectedがboolでない場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        _require_bool(connected, "connected")
        self._require_valid()
        mplug = self._mplug
        if connected:
            return sorted(mplug.connectionByPhysicalIndex(index).logicalIndex() for index in range(mplug.numConnectedElements()))
        indices = list(mplug.getExistingArrayAttributeIndices())
        count = _instance_count(mplug)
        if count:
            indices = sorted(set(indices).union(range(count)))
        return indices

    def _require_movable(self, indices):
        """要素を別の番号へ移せるか確かめる。シーンは変えない。

        compactと、removeElementのshiftで使う。

        Args:
            indices (list[int]): 移す要素の論理番号。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: マルチアトリビュートか移す要素(その下を含む)がロックされている場合、
                またはリファレンスのノードの場合。
        """
        name = self._full_name()
        if self._node._dependency_fn().isFromReferencedFile:
            raise RuntimeError(f"マルチアトリビュートがリファレンスです: {name}")
        if self._mplug.isLocked:
            raise RuntimeError(f"マルチアトリビュートがロックされています: {name}")
        for index in indices:
            for _, mplug in _descendants(self._mplug.elementByLogicalIndex(index)):
                if mplug.isLocked:
                    raise RuntimeError(f"マルチアトリビュートの要素がロックされています: {name}[{index}]")

    def _move_elements(self, moves):
        """要素の値と、入力・出力の接続を、cmdsで別の番号の要素へ移す。

        先にすべての要素の値と接続を集め、移す元をすべて削除する。そのあと移す先へ値を設定し、接続し直す。
        値も入力の接続も無い要素も、移す先に要素を作る(messageの要素を除く)。
        移す先は、移す元を削除したあとに空いている番号でなければならない(compact・shiftの順番ならそうなる)。

        Args:
            moves (list[tuple[int, int]]): (移す元の論理番号, 移す先の論理番号)の並び。

        Returns:
            None: 値を返さない。
        """
        captured = [(target, self._capture_element(source)) for source, target in moves]
        name = self._full_name()
        for source, _ in moves:
            element = self._mplug.elementByLogicalIndex(source)
            # 要素を丸ごと消すと、Undoで要素は戻っても、その下のマルチアトリビュートの値が戻らない(Mayaの制約)。
            # 下の要素を深いものから先に1つずつ消して、Undoで値まで戻るようにする。
            nested = [steps for steps, mplug in _descendants(element) if steps and mplug.isElement]
            for steps in sorted(nested, key=len, reverse=True):
                cmds.removeMultiInstance(_follow(element, steps).name(), b=True)
            cmds.removeMultiInstance(f"{name}[{source}]", b=True)
        for target, (values, inputs, outputs) in captured:
            element = self._mplug.elementByLogicalIndex(target)
            for steps, value in values:
                Plug(self._node, _follow(element, steps)).set(value)
            for steps, source in inputs:
                cmds.connectAttr(source._full_name(), Plug(self._node, _follow(element, steps))._full_name())
            for steps, destinations in outputs:
                plug_name = Plug(self._node, _follow(element, steps))._full_name()
                for destination in destinations:
                    cmds.connectAttr(plug_name, destination._full_name())
        # 値も入力の接続も無い要素(値を一度も設定していない要素など)は、上の処理では移す先に作られない。
        # 読み取ると要素が作られるので、移す先に要素を残す。messageの要素は読み取れないため対象外。
        existing = set(self._mplug.getExistingArrayAttributeIndices())
        for target, _ in captured:
            element = self._mplug.elementByLogicalIndex(target)
            if target not in existing and not element.attribute().hasFn(om2.MFn.kMessageAttribute):
                cmds.getAttr(f"{name}[{target}]")

    def _capture_element(self, index):
        """要素の値と、入力・出力の接続を、要素からのたどり方と組にして集める。

        入力の接続があるPlugの値も集める。接続する前に値を設定して移す先の要素を作り、Undoで要素ごと戻せるようにするため
        (接続しただけで作られた要素は、Undoしても消えない)。
        messageと、書き込めない・保存されないPlugの値は集めない。

        Args:
            index (int): 既存要素の論理番号。

        Returns:
            tuple[list, list, list]: (値の(たどり方, 値)、入力の(たどり方, 接続元Plug)、
                出力の(たどり方, list[接続先Plug]))。
        """
        values, inputs, outputs = [], [], []
        for steps, mplug in _descendants(self._mplug.elementByLogicalIndex(index)):
            sources = mplug.connectedTo(True, False)
            if sources:
                inputs.append((steps, Plug(self._node_from_mplug(sources[0]), sources[0])))
            destinations = mplug.connectedTo(False, True)
            if destinations:
                outputs.append((steps, [Plug(self._node_from_mplug(plug), plug) for plug in destinations]))
            if mplug.isArray or mplug.isCompound:
                continue
            attribute = mplug.attribute()
            fn = om2.MFnAttribute(attribute)
            if attribute.hasFn(om2.MFn.kMessageAttribute) or not (fn.writable and fn.storable):
                continue
            value = Plug(self._node, mplug).get()
            if value is not None:
                values.append((steps, value))
        return values, inputs, outputs

    @staticmethod
    def _validated_logical_index(index):
        """要素の取得・編集に使う論理番号を確かめて、intで返す。

        Args:
            index (int): 対象要素の論理番号。``operator.index`` で整数へ変換できる値(boolを除く)。

        Returns:
            int: 検証済みの論理番号。

        Raises:
            TypeError: boolまたは整数以外の場合。
            IndexError: 0〜2147483647の範囲外の場合。
        """
        if isinstance(index, bool):
            raise TypeError("論理番号は整数で指定してください")
        try:
            index = operator.index(index)
        except TypeError:
            raise TypeError("論理番号は整数で指定してください") from None
        if not 0 <= index <= MAX_LOGICAL_INDEX:
            raise IndexError("論理番号は0〜2147483647で指定してください")
        return index

    def _element_at(self, index):
        """書き込み・接続に使う要素を取得する。欠けている番号の要素は作らない。

        Args:
            index (int): 論理番号。

        Returns:
            Plug: 型に合ったPlug。作ると危険な内部データ型の要素で、まだ無いものは拒否する。
        """
        self._require_valid()
        index = self._validated_logical_index(index)
        mplug = self._mplug.elementByLogicalIndex(index)
        if is_internal_data_type(mplug) and index not in self._mplug.getExistingArrayAttributeIndices():
            raise RuntimeError(f"内部データ型のマルチアトリビュートの要素は作成できません: {self._full_name()}")
        return Plug(self._node, mplug)
