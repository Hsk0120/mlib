"""コンパウンドアトリビュートと、その子のPlugを扱う。"""

import maya.api.OpenMaya as om2

from ..core.attributeType import _convert_angles, _convert_times, _convert_units, _plain_angle_unit, _plain_time_unit, attributeType, value_reader
from ..core.fastWrite import set_attr, set_plug
from ..core.object import _missing_member_message
from ..decorator import _require_bool
from .plug import Plug


class CompoundPlug(Plug):
    """コンパウンドアトリビュートを扱うPlug。直接の子のPlugと、その値を扱う。

    子は、定義順に0から数えた番号か、ロング名・ショート名で取得する。
    この番号はMultiPlugの論理番号とは別のもの。get()は子の値を定義順に並べたtupleを返す。
    maya.cmdsへは ``str(plug)`` で渡す。mlib.selectにはそのまま渡せる。
    """

    _child_readers = None  #: 子の値を直接読む関数の列。初回の内部単位get()で子の定義から選ぶ。
    _bulk_children = None  #: 子を1回のsetAttrでまとめて書けるか。初回のset()で子の定義から判定する。

    def __getattr__(self, name):
        """子を ``plug.child`` の形で取得する。

        Args:
            name (str): 子のアトリビュート名。

        Returns:
            Plug: 見つかった子のPlug。

        Raises:
            AttributeError: ``_`` で始まる名前を指定した場合、または子が見つからない場合。
                ノードやアトリビュートが削除されて無効なPlugの場合もAttributeErrorにする。
                ``hasattr``・``getattr(..., default)`` を使えるようにするため。
                元のRuntimeErrorは ``__cause__`` に入る。
        """
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self[name]
        except (AttributeError, TypeError, RuntimeError) as error:
            raise AttributeError(_missing_member_message(self, name, "メソッドや子のアトリビュート")) from error

    def __getitem__(self, nameOrIndex):
        """直接の子を、番号か名前で取得する。

        - 整数は、定義順に0から数えた子の番号。マルチアトリビュートの要素の論理番号ではない。
          負の数とsliceは使えない。
        - 文字列は、直接の子のロング名・ショート名と比べる。孫へのパスやエイリアスは扱わない。

        子の値は読み出さない。

        Args:
            nameOrIndex (str | int): 子のロング名、ショート名、または定義順の子の番号。

        Returns:
            Plug: 子の新しいオブジェクト。ノードは親と同じものを共有し、値やノードを複製するわけではない。

        Raises:
            AttributeError: 名前に一致する直接の子が無い場合。
            IndexError: 番号が子の数の範囲外の場合。
            TypeError: 整数でも文字列でもないものを指定した場合。boolも受け付けない。
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        self._require_valid()
        if isinstance(nameOrIndex, bool) or not isinstance(nameOrIndex, (int, str)):
            raise TypeError("子の番号は整数かアトリビュート名で指定してください")
        if isinstance(nameOrIndex, int):
            if not 0 <= nameOrIndex < self._mplug.numChildren():
                raise IndexError("子の番号が範囲外です")
            return self._child_at(nameOrIndex)
        for index in range(self._mplug.numChildren()):
            child = self._mplug.child(index)
            attribute = om2.MFnAttribute(child.attribute())
            if nameOrIndex in (attribute.name, attribute.shortName):
                return Plug(self._node, child)
        raise AttributeError(f"{self.getFullName()}に{nameOrIndex!r}という名前の子はありません")

    def __iter__(self):
        """直接の子を、アトリビュートの定義順に1つずつ返す。

        反復を始めた時点のgetChildren()の結果を使う。子の値は読み出さない。

        Returns:
            Iterator[Plug]: 反復を始めた時点で集めた、直接の子のイテレーター。
        """
        return iter(self.getChildren())

    def get(self, *, unit=None, timeUnit=None, uiUnits=False):
        """直接の子の値を、アトリビュートの定義順に並べたtupleで取得する。

        子ごとに値を読むので、DGの評価が起きることがある。
        子がコンパウンドアトリビュートや ``doubleArray`` などのデータ型でも、値を平らにならさず、
        各子のgetが返す形のまま入れる。

        Args:
            unit (str | None): 角度の子の数値の単位。None(既定)は度、``"rad"`` はラジアン。
                :meth:`Plug.get` と同じ名前を受け付ける。uiUnits=Trueとは同時に指定できない。
            timeUnit (str | None): 時間の子の数値の単位。None(既定)は現在のUIの時間単位でのフレーム、
                ``"sec"`` は秒。:meth:`Plug.get` と同じ名前を受け付ける。uiUnits=Trueとは同時に指定できない。
            uiUnits (bool): 各子のgetへ渡す。TrueならUIの単位。
                既定はFalseで、角度は度、距離はcm、時間はフレームになる。

        Returns:
            tuple: 子の数と同じ長さの新しいtuple。値の型と単位は各子のgetのとおり。

        Raises:
            TypeError: uiUnitsがboolでない場合、またはunit・timeUnitが文字列でもNoneでもない場合。
            ValueError: unit・timeUnitが対応していない単位名の場合、またはuiUnits=Trueと同時に指定した場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合、または子の値を取得できない場合。
        """
        _require_bool(uiUnits, "uiUnits")
        angle_unit = _plain_angle_unit(unit, uiUnits)
        time_unit = _plain_time_unit(timeUnit, uiUnits)
        self._require_valid()
        if not uiUnits:
            values = _convert_angles(self._mplug, tuple(self._child_values()), angle_unit, to_internal=False)
            return tuple(_convert_times(self._mplug, values, time_unit, to_internal=False))
        return tuple(self._child_at(index).get(uiUnits=uiUnits) for index in range(self._mplug.numChildren()))

    def getChildren(self):
        """直接の子のPlugを、定義順に取得する。

        孫はたどらない。子の値も読み出さない。

        Returns:
            list[Plug]: 子の新しいオブジェクトのリスト。ノードは親と共有し、シーンのものを複製しない。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        self._require_valid()
        return [self._child_at(index) for index in range(self._mplug.numChildren())]

    def _child_values(self):
        """直接の子の値を、内部単位のまま定義順に読む。有効なことは確かめ済みとする。

        子のPlugオブジェクトは作らず、子の ``get()`` と同じ読み取り関数をMPlugへ直接使う。
        読み取り関数はアトリビュートの定義から一度だけ選んで覚えておき、値は毎回読み直す。
        次の子は、これまでどおり子のPlugの ``get()`` で読む。

        - コンパウンドアトリビュート・マルチアトリビュートの子。
        - 読み取り関数を持たない型(generic・message・マトリクスなど)の子。

        Returns:
            list: 子の値。型は各子の ``get()`` と同じで、単位は内部単位(距離cm・角度rad・時間秒)。
        """
        mplug = self._mplug
        readers = self._child_readers
        if readers is None:
            selected = []
            for index in range(mplug.numChildren()):
                child = mplug.child(index)
                if child.isCompound or child.isArray:
                    selected.append(False)
                else:
                    selected.append(value_reader(child.attribute()))
            readers = self._child_readers = tuple(selected)
        return [
            reader(mplug.child(index)) if reader is not False else self._child_at(index).get(unit="rad", timeUnit="sec") for index, reader in enumerate(readers)
        ]

    def _set_value(self, value, *, uiUnits=False, fast=False):
        """子の数と同じ数の値を書き込む。先に、すべての子が書き込めるか確かめる。

        全体の流れは :meth:`Plug.set` が受け持つ。書き込めない子が1つでもあれば、何も書かずに例外にする。
        ただし子の値の型の誤りは、その子を書く時点で見つかる。そのため、前の子の変更が残ることがある
        (1回のUndoで戻せる)。

        Args:
            value (Iterable[object]): 子の数と同じ数の値。
            uiUnits (bool): TrueならUIの単位。既定はFalseで、内部単位(角度はrad・距離はcm・時間は秒)。
                角度・時間の数値は、:meth:`Plug.set` で度からrad、フレームから秒へ換算済み。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 値の型が不正な場合。
            ValueError: 値の数が子の数と合わない場合。
            RuntimeError: アトリビュートが無効な場合、または書き込みに失敗した場合。
        """
        self._require_valid()
        _require_bool(uiUnits, "uiUnits")
        values = tuple(value)
        if len(values) != self._mplug.numChildren():
            raise ValueError("コンパウンドアトリビュートの値の数が子の数と合っていません")
        if fast:
            if uiUnits:
                values = _convert_units(self._mplug, values, to_ui=False)
            set_plug(self._mplug, values)
        elif self.getType() in {"float2", "float3", "long2", "long3", "short2", "short3"}:
            self._require_writable()
            Plug._set_value(self, values, uiUnits=uiUnits, fast=fast)
        else:
            # 子ごとに書く経路でも、先に全子の書込み可否を検査する。ロック・入力接続の
            # ある子より前の子だけが書かれて残ることを防ぐ(Double3Plugと同じ)。
            self._require_writable()
            if not uiUnits:
                self._set_child_values(values, writable_checked=True)
                return
            for index, child_value in enumerate(values):
                self._child_at(index).set(child_value, safe=False, uiUnits=uiUnits, fast=fast)

    def _set_child_values(self, values, *, writable_checked=False):
        """内部単位の値を、cmdsを使って定義順に子へ書き込む。

        次の条件をすべて満たすときは、親へ1回の ``cmds.setAttr`` でまとめて書く。

        - double2・double3で、数値の子だけを持つ。
        - 値がすべてint・float。
        - すべての子が書き込める。

        それ以外の場合と、まとめた書き込みが失敗した場合は、これまでどおり子ごとに ``set()`` する。
        そのため、例外の種類・文言と、途中まで書いたときの順序は、子ごとの書き込みと同じになる。
        Undoチャンクは呼び出し元で開く。

        Args:
            values (tuple): 子の数と同じ長さの、内部単位の値(距離はcm・角度はrad・時間は秒)。
            writable_checked (bool): Trueなら、呼び出し元が ``_require_writable()`` で確かめ済み。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 子の値の型が不正な場合。
            ValueError: 子の値を変換できない場合。
            RuntimeError: 子の書き込みに失敗した場合。
        """
        mplug = self._mplug
        if self._can_set_at_once(values):
            try:
                if not writable_checked:
                    self._require_writable()
            except RuntimeError:
                pass  # 書けない子は、子ごとの書込みで従来の例外にする。
            else:
                try:
                    set_attr(self.getFullName(), *_convert_units(mplug, values), fast=False)
                    return
                except (RuntimeError, TypeError, ValueError):
                    pass  # 子ごとに書き直し、従来の例外と更新順にする。
        for index, child_value in enumerate(values):
            self._child_at(index).set(child_value, safe=False, unit="rad", timeUnit="sec", fast=False)

    def _can_set_at_once(self, values):
        """子を1回のsetAttrでまとめて書けるか判定する。シーンは変更しない。

        子の構成はアトリビュートの定義から一度だけ調べて覚えておく。値の型は毎回確かめる。

        Args:
            values (tuple): 書き込む値。

        Returns:
            bool: 次の条件をすべて満たせばTrue。double2・double3である。子が数値か単位付きの
                単純なアトリビュートである。値がすべてint・float(boolを除く)である。
        """
        bulk = self._bulk_children
        if bulk is None:
            mplug = self._mplug
            bulk = attributeType(mplug) in ("double2", "double3")
            if bulk:
                for index in range(mplug.numChildren()):
                    child = mplug.child(index)
                    attribute = child.attribute()
                    if child.isCompound or child.isArray or not (attribute.hasFn(om2.MFn.kNumericAttribute) or attribute.hasFn(om2.MFn.kUnitAttribute)):
                        bulk = False
                        break
            self._bulk_children = bulk
        if not bulk:
            return False
        for item in values:
            if type(item) is not float and type(item) is not int:
                return False
        return True

    def _child_at(self, index):
        """指定した番号の子のPlugを作る。有効なことは確かめ済みとする。

        Args:
            index (int): 子の番号。

        Returns:
            Plug: 子のPlug。
        """
        return Plug(self._node, self._mplug.child(index))
