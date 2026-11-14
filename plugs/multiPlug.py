"""マルチアトリビュートの論理番号と、要素のPlugを扱う。"""

import operator
from contextlib import nullcontext

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.attributeType import _convert_angles, _convert_times, _convert_units, _plain_angle_unit, _plain_time_unit, is_internal_data_type, value_reader
from ..decorator import _edit_context, _require_bool, undoChunk
from .plug import MAX_LOGICAL_INDEX, Plug, _instance_count


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
            yield from _descendants(mplug.elementByLogicalIndex(index), steps + (("element", index),))
    elif mplug.isCompound:
        for index in range(mplug.numChildren()):
            yield from _descendants(mplug.child(index), steps + (("child", index),))


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
            if not item.isValid() or not item.isMultiElement():
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

        反復を始めた時点のgetElements()の結果を使う。欠けている番号は返さない。要素の値は読み出さない。

        Returns:
            Iterator[Plug]: 反復を始めた時点で集めた要素のイテレーター。
        """
        return iter(self.getElements())

    def get(self, *, unit=None, timeUnit=None, uiUnits=False):
        """すでにある要素の値を、論理番号をキーにしたdictで取得する。

        getElements()の要素ごとに値を読むので、DGの評価が起きることがある。
        番号は詰め直さない。要素がコンパウンドアトリビュートや ``doubleArray`` などのデータ型でも、
        値を平らにならさない。

        Args:
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
        """
        _require_bool(uiUnits, "uiUnits")
        angle_unit = _plain_angle_unit(unit, uiUnits)
        time_unit = _plain_time_unit(timeUnit, uiUnits)
        if type(self).getElements is not MultiPlug.getElements:
            return {plug.mplug().logicalIndex(): plug.get(unit=unit, timeUnit=timeUnit, uiUnits=uiUnits) for plug in self.getElements()}
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

    def getElement(self, index):
        """論理番号で要素を取得する(``multi[index]`` と同じ)。

        値の評価も、要素の作成もしない。まだ無い要素(欠けている番号)も取得でき、
        その要素へset・connectしたときに作られる。
        すでにある要素だけが必要なら、:meth:`getElements` (すでにある要素の一覧)か
        ``index in multi`` (あるかどうかの判定)を使う。

        Args:
            index (int): 0〜2147483647の論理番号。

        Returns:
            Plug: 要素の新しいオブジェクト。ノードはマルチアトリビュートと同じもの。

        Raises:
            TypeError: indexを指定していない場合、boolの場合、または整数でない場合。
            IndexError: 番号が0〜2147483647の範囲外の場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        return self[index]

    def getElements(self):
        """すでにある要素のPlugを、論理番号の小さい順に取得する。

        getIndices()の番号の要素だけを返す。欠けている番号は埋めず、要素の値も読み出さない。
        まだ作られていない要素も取得できる :meth:`getElement` とは、この点が違う。
        worldSpaceのアトリビュートでは、評価の前でもDAGのインスタンス番号の要素を含む。

        Returns:
            list[Plug]: 要素の新しいオブジェクトのリスト。ノードは共有し、シーンのものを複製しない。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        # 要素ごとに存在を確かめ直さず、既存の番号から直接 Plug を作る。
        return [Plug(self._node, self._mplug.elementByLogicalIndex(index)) for index in self.getIndices()]

    def getNextAvailable(self, start=-1, checkLocked=True, checkChildren=True, *, vacant=False):
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
            raise RuntimeError(f"マルチアトリビュートがロックされています: {self.getFullName()}")
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

    def removeElement(self, index, shift=False, *, fast=False):
        """マルチアトリビュートの要素を削除する。接続も切る。

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

        Returns:
            MultiPlug: 自身。

        Raises:
            TypeError: indexがboolの場合や整数でない場合、またはshift・fastがboolでない場合。
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
        _require_bool(shift, "shift")
        _require_bool(fast, "fast")
        if fast and shift:
            raise NotImplementedError("fastのremoveElementはshift=Trueに対応していません")
        with _edit_context("mlibMultiPlugRemoveElement", fast):
            self._require_valid()
            index = self._validated_logical_index(index)
            existing = sorted(self._mplug.getExistingArrayAttributeIndices())
            if index not in existing:
                raise IndexError(f"{self.getFullName()}に論理番号{index}の要素はありません")
            moves = [(source, source - 1) for source in existing if source > index] if shift else []
            if shift:
                self._require_movable([index] + [source for source, _ in moves])
            if fast:
                modifier = om2.MDGModifier()
                modifier.removeMultiInstance(self._mplug.elementByLogicalIndex(index), True)
                modifier.doIt()
            else:
                cmds.removeMultiInstance(self._element_at(index).getFullName(), b=True)
                if moves:
                    self._move_elements(moves)
            return self

    def compact(self):
        """空いた番号を詰めて、要素の論理番号を0からの連番に並べ直す。

        すでにある要素を、論理番号の小さい順に0, 1, 2…へ移す。移すのは、各要素の値
        (コンパウンドアトリビュートの子と、入れ子のマルチアトリビュートの要素を含む)と、入力・出力の接続。
        すでに連番になっていれば何も変えない。cmdsで編集し、1回のUndoで戻せる。

        Returns:
            MultiPlug: 自身。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。マルチアトリビュートか移す要素(子を含む)が
                ロックされている場合。またはリファレンスのノードの場合。

        Note:
            値はmlibの :meth:`~mlib.plugs.plug.Plug.get` / :meth:`~mlib.plugs.plug.Plug.set` で移す。
            書き込めない子・保存されない子と、接続の無いmessageの要素は移せない(移した先に作られない)。
            同じマルチアトリビュートの要素どうしの接続は考慮していない。
        """
        with undoChunk("mlibMultiPlugCompact"):
            self._require_valid()
            existing = sorted(self._mplug.getExistingArrayAttributeIndices())
            moves = [(source, target) for target, source in enumerate(existing) if source != target]
            if moves:
                self._require_movable([source for source, _ in moves])
                self._move_elements(moves)
            return self

    def getSourceNodes(self):
        """各要素へつながっている接続元のノードを、論理番号の順に取得する。

        Returns:
            dict[int, Node]: 論理番号をキーにした接続元のノード。接続のある要素だけを含み、
                接続の無い番号は詰めずに抜けたままにする。
        """
        result = {}
        for element in self.getElements():
            source = element.getSource()
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

    def getIndices(self):
        """すでにある要素の論理番号を、小さい順に取得する。

        値は評価しない。番号がとびとびの[2, 10]なら[2, 10]を返し、並びの位置の[0, 1]へ詰め直さない。
        worldSpaceのマルチアトリビュートでは、OpenMayaが返す番号に、DAGのすべてのインスタンスの
        番号(0から数-1まで)を補う。祖先がインスタンス化されたことによる間接的なインスタンスも含む。
        欠けている番号の要素は作らない。getElements()も同じ番号を使う。

        Returns:
            list[int]: 論理番号の新しいリスト。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        self._require_valid()
        indices = list(self._mplug.getExistingArrayAttributeIndices())
        count = _instance_count(self._mplug)
        if count:
            indices = sorted(set(indices).union(range(count)))
        return indices

    def getConnectedIndices(self):
        """接続のある要素の論理番号を、小さい順に取得する。

        要素自身か、その下(コンパウンドアトリビュートの子・入れ子の要素)に、入力か出力の接続がある要素を返す。
        ``MPlug.numConnectedElements`` / ``connectionByPhysicalIndex`` で求める。値だけを持つ要素は含まない。

        Returns:
            list[int]: 論理番号の新しいリスト。接続が無ければ空リスト。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        self._require_valid()
        mplug = self._mplug
        return sorted(mplug.connectionByPhysicalIndex(index).logicalIndex() for index in range(mplug.numConnectedElements()))

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
        name = self.getFullName()
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
        移す先は、移す元を削除したあとに空いている番号でなければならない(compact・shiftの順番ならそうなる)。

        Args:
            moves (list[tuple[int, int]]): (移す元の論理番号, 移す先の論理番号)の並び。

        Returns:
            None: 値を返さない。
        """
        captured = [(target, self._capture_element(source)) for source, target in moves]
        name = self.getFullName()
        for source, _ in moves:
            cmds.removeMultiInstance(f"{name}[{source}]", b=True)
        for target, (values, inputs, outputs) in captured:
            element = self._mplug.elementByLogicalIndex(target)
            for steps, value in values:
                Plug(self._node, _follow(element, steps)).set(value)
            for steps, source in inputs:
                cmds.connectAttr(source.getFullName(), Plug(self._node, _follow(element, steps)).getFullName())
            for steps, destinations in outputs:
                plug_name = Plug(self._node, _follow(element, steps)).getFullName()
                for destination in destinations:
                    cmds.connectAttr(plug_name, destination.getFullName())

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
            raise RuntimeError(f"内部データ型のマルチアトリビュートの要素は作成できません: {self.getFullName()}")
        return Plug(self._node, mplug)
