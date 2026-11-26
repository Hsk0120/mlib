"""アニメーションカーブのキーを、「カーブ + キーの番号」で指すオブジェクトとして扱う。

:class:`Keyframe` は1つのキー、:class:`Keyframes` は複数のキー(複数のカーブにまたがってよい)を表す。

- 頂点(:class:`~mlib.components.vertex.Vertex`)と同じく、作ったときの番号を持ち続ける。
  キーを追加・削除したり、入力の順が入れ替わったりしたあとも同じキーを指すことは保証しない。
- ドリブンキーのカーブ(入力が時間でない animCurveU*)のキーも同じクラスで扱う。
  その場合の「時刻」は、カーブの入力の値を指す。
- 値と時刻の単位は :class:`~mlib.nodes.animCurve.AnimCurve` と同じ(角度は度、距離はcm、時間はフレーム)。

.. code-block:: python

    import mlib
    from mlib.common import Selection

    for curve, keys in Selection.getKeyframes().iterCurves():
        print(curve, [key.getValue() for key in keys])
    mlib.getNode("pCube1_translateX").getKeyframes(0).setValue(5)
"""

import maya.cmds as cmds

from ..decorator import _require_bool, undoChunk
from ..util import _UNSET, _finite


class Keyframe:
    """アニメーションカーブの1つのキーを指すオブジェクト。

    Args:
        curve (AnimCurve): キーを持つカーブ。
        index (int): 0始まりのキー番号。

    Raises:
        TypeError: curveがAnimCurveでない場合。
        IndexError: indexがキーの数の範囲にない場合。
    """

    __slots__ = ("_curve", "_index")

    def __init__(self, curve, index):
        # nodes.animCurve はこのモジュールを読み込むため、循環importを避けて関数内で読み込む。
        from ..nodes.animCurve import AnimCurve

        if not isinstance(curve, AnimCurve):
            raise TypeError(f"curveはAnimCurveで指定してください: {type(curve).__name__}")
        curve._index(index)
        self._curve = curve
        self._index = index

    def __eq__(self, other):
        """同じカーブの同じ番号を指すか比較する。

        Args:
            other: 比較の相手。
        """
        if not isinstance(other, Keyframe):
            return NotImplemented
        return self._curve == other._curve and self._index == other._index

    def __hash__(self):
        """カーブと番号のハッシュを返す。"""
        return hash((self._curve, self._index))

    def __repr__(self):
        """``Keyframe('pCube1_translateX', 3)`` の形で表示する。"""
        name = self._curve.getName() if self._curve.isValid() else "<削除済み>"
        return f"{type(self).__name__}({name!r}, {self._index})"

    def getCurve(self):
        """キーを持つカーブを返す。

        Returns:
            AnimCurve: 保持しているカーブ。
        """
        return self._curve

    def getIndex(self):
        """キーの番号を返す。

        Returns:
            int: 作成時の0始まりのキー番号。
        """
        return self._index

    def isValid(self):
        """カーブが有効で、番号がキーの数の範囲内にあるか調べる。

        Returns:
            bool: 有効ならTrue。番号が同じキーを指し続けているかまでは確かめない。
        """
        return self._curve.isValid() and self._index < self._curve.getKeyCount()

    def getValue(self, *, input=False, unit=_UNSET, timeUnit="frame"):
        """キーの値を返す。``input=True`` なら、キーの入力(時刻、またはドリブンキーの入力の値)を返す。

        Args:
            input (bool): Trueなら、値でなく入力を返す。既定はFalse。
            unit (str): 出力が角度(A型)のときの値の単位。``"deg"`` / ``"rad"``。既定は ``"deg"``。``input=True`` では指定できない。
            timeUnit (str): 値では出力が時間のとき、入力では入力が時間(T型)のときの単位。``"frame"`` / ``"sec"``。

        Returns:
            float: 値、または入力の値。

        Raises:
            TypeError: inputがboolでない場合、input=Trueとunitを同時に指定した場合、またはunit・timeUnitが文字列でない場合。
            ValueError: unit・timeUnitに対応していない単位名の場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        _require_bool(input, "input")
        if input:
            if unit is not _UNSET:
                raise TypeError("unitはinput=Trueと同時に指定できません(入力の単位はtimeUnitで指定します)")
            self._require_valid()
            return self._curve.getKeyInputs(timeUnit=timeUnit)[self._index]
        self._require_valid()
        return self._curve.getKeyValues(unit="deg" if unit is _UNSET else unit, timeUnit=timeUnit)[self._index]

    def setValue(self, value, *, unit="deg", timeUnit="frame", fast=False, check=False):
        """キーの値を、接線の型を保ったまま変える。

        Args:
            value (float): 新しい値(:meth:`getValue` と同じ単位)。
            unit (str): 出力が角度(A型)のときの単位。``"deg"`` / ``"rad"``。
            timeUnit (str): 出力が時間のときの単位。``"frame"`` / ``"sec"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 数値に変換できない型の場合、またはfast・checkがboolでない場合。
            ValueError: 値が有限でない場合、または単位名に対応していない場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。check=Trueで、キーを格納するアトリビュートが書き込めない場合。
        """
        _require_bool(check, "check")
        self._curve._set_key_values(self._index, value, unit=unit, timeUnit=timeUnit, fast=fast, check=check)

    def getTangent(self, *, unit="deg"):
        """接線の型・角度・ウェイト・ロックを返す。

        角度はunitの単位(既定は度)。接線のウェイトはAPIの値のまま返す(入力が時間のカーブでは、今のUIの時間単位で変わる)。
        lockとweightLockはキーごとの状態、weightedTangentsはカーブ全体の状態。

        Args:
            unit (str): 角度の単位。``"deg"`` / ``"rad"``。

        Returns:
            dict: inTangentType・outTangentType・inAngle・outAngle・inWeight・outWeight・lock・weightLock・weightedTangents を
                キーにした新しい辞書。型名はMayaのコマンドでの表記で、名前の登録の無い接線の型は空文字列。

        Raises:
            TypeError: unitが文字列・None以外の場合。
            ValueError: unitに対応していない単位名の場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
        """
        return self._curve._get_tangent(self._index, unit=unit)

    def setTangent(self, *, unit="deg", fast=False, check=False, **kwargs):
        """接線を変える。接線のロックの扱いはMayaの規則に従う。

        weightedTangentsを指定した場合は、カーブ全体をウェイト付きの接線にするかどうかだけを変える。

        Args:
            unit (str): 角度の単位。``"deg"`` / ``"rad"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。
            **kwargs: :meth:`getTangent` の辞書と同じ9種類のフラグ(長い名前)。角度はunitの単位、接線のウェイトはAPIの値。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: unitが文字列・None以外の場合、またはfast・checkがboolでない場合。
            ValueError: フラグが空か知らない名前の場合、unitに対応していない場合、
                ウェイト付きの接線でないカーブにinWeight・outWeightを指定した場合(weightedTangentsと一緒に指定した場合を除く)、
                またはfastで正しくない値やglobal・知らない接線の型を指定した場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: check=Trueで、キーを格納するアトリビュートがロック・入力の接続などで書き込めない場合。
            NotImplementedError: fastで入力側の接線にstepnextを指定した場合。
        """
        _require_bool(check, "check")
        _require_weighted(self._curve, kwargs)
        self._curve._set_tangent(self._index, unit=unit, fast=fast, check=check, **kwargs)

    def isBreakdown(self):
        """ブレイクダウンキーか調べる。

        Returns:
            bool: ブレイクダウンキーならTrue。

        Raises:
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        self._require_valid()
        return self._curve._is_breakdown(self._index)

    def setBreakdown(self, state=True):
        """ブレイクダウンキーにする、または通常のキーへ戻す。

        Args:
            state (bool): Trueならブレイクダウンキー、Falseなら通常のキーにする。既定はTrue。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがboolでない場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        self._curve._set_breakdown(self._index, state)

    def move(self, *, timeOffset=0, valueOffset=0, unit="deg", timeUnit="frame"):
        """キーの入力と値をずらす。

        入力が隣のキーと同じか、越える位置になる場合は、何も変えずに例外にする。番号は変わらない。

        Args:
            timeOffset (float): 入力をずらす量。
            valueOffset (float): 値をずらす量。
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 時間の単位。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: timeOffset・valueOffsetが数値でない(boolを含む)、またはunit・timeUnitが文字列でない場合。
            ValueError: timeOffset・valueOffsetが有限でない場合、unit・timeUnitに対応していない単位名の場合、
                または入力が隣のキーと同じか越える位置になる場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        _require_movable(self._curve, [self._index], timeOffset, valueOffset, timeUnit)
        self._curve._move_keys(index=self._index, timeOffset=timeOffset, valueOffset=valueOffset, unit=unit, timeUnit=timeUnit)

    def delete(self, *, keepCurve=True, fast=False, check=False):
        """キーを削除する。

        削除したあとは、同じカーブでこれより後ろの番号を持つオブジェクトが、別のキーを指すようになる。

        Args:
            keepCurve (bool): Trueなら、最後のキーを消してもカーブを残す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: keepCurve・fast・checkがboolでない場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。check=Trueで、キーを格納するアトリビュートが書き込めない場合。
        """
        _require_bool(keepCurve, "keepCurve")
        _require_bool(check, "check")
        self._curve._remove_keys(index=self._index, keepCurve=keepCurve, fast=fast, check=check)

    def select(self, *, add=False):
        """Graph Editor・Dope Sheet でこのキーを選択する。

        Args:
            add (bool): Trueなら今のキーの選択に加える。Falseなら置き換える。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: addがboolでない場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        Keyframes([self]).select(add=add)

    def _require_valid(self):
        """カーブが有効で、番号が範囲内であることを確かめる。"""
        self._curve._require_valid("アトリビュートの取得")
        self._curve._index(self._index)


class Keyframes:
    """キーの集まり。

    複数のカーブにまたがってよい。カーブは最初に出てきた順に、カーブの中のキーは番号の小さい順に並べて持つ。

    Args:
        keyframes (Iterable[Keyframe]): キーのオブジェクト。同じキーは1つにまとめる。

    Raises:
        TypeError: Keyframeでないものを含む場合。
    """

    #: 中身を変えられる集まりなので、ハッシュは作れない(Components と同じ)。
    __hash__ = None

    def __init__(self, keyframes=()):
        groups = {}
        for keyframe in keyframes:
            if not isinstance(keyframe, Keyframe):
                raise TypeError(f"Keyframeを指定してください: {type(keyframe).__name__}")
            groups.setdefault(keyframe._curve, set()).add(keyframe._index)
        self._groups = [(curve, sorted(indices)) for curve, indices in groups.items()]

    def __len__(self):
        """キーの数を返す。"""
        return sum(len(indices) for _, indices in self._groups)

    def __iter__(self):
        """カーブごとに、番号の小さい順で :class:`Keyframe` を返す。"""
        for curve, indices in self._groups:
            for index in indices:
                yield _keyframe(curve, index)

    def __getitem__(self, index):
        """位置で :class:`Keyframe` を返す。

        Args:
            index (int): 並びの位置。負の値なら末尾から数える。

        Returns:
            Keyframe: その位置のキー。
        """
        return list(self)[index]

    def __contains__(self, item):
        """同じカーブの同じ番号を含むか返す。"""
        if not isinstance(item, Keyframe):
            return False
        return any(curve == item._curve and item._index in indices for curve, indices in self._groups)

    def __eq__(self, other):
        """同じカーブと番号の組を、同じ順で持つか比べる。"""
        if not isinstance(other, Keyframes):
            return NotImplemented
        return self._groups == other._groups

    def __repr__(self):
        """``Keyframes(count=4, curves=2)`` の形で表示する。"""
        return f"{type(self).__name__}(count={len(self)}, curves={len(self._groups)})"

    def getCurves(self):
        """キーを持つカーブを返す。

        Returns:
            Nodes[AnimCurve]: カーブ(最初に出てきた順。同じものは1回だけ)。
        """
        # commonの初期化時にnodesを読み込まないよう、使う時点で読み込む。
        from ..nodes.node import Nodes

        return Nodes._wrap([curve for curve, _ in self._groups])

    def iterCurves(self):
        """カーブごとに、そのカーブのキーの集まりを返す。

        Yields:
            tuple[AnimCurve, Keyframes]: カーブと、そのカーブのキー(番号の小さい順)。
        """
        for curve, indices in self._groups:
            yield curve, Keyframes(_keyframe(curve, index) for index in indices)

    def getIndices(self, curve):
        """指定したカーブのキーの番号を返す。

        Args:
            curve (AnimCurve): カーブ。

        Returns:
            list[int]: 番号(小さい順)。このカーブのキーが無ければ空。

        Raises:
            TypeError: curveがAnimCurveでない場合。
        """
        # nodes.animCurve はこのモジュールを読み込むため、循環importを避けて関数内で読み込む。
        from ..nodes.animCurve import AnimCurve

        if not isinstance(curve, AnimCurve):
            raise TypeError(f"curveはAnimCurveで指定してください: {type(curve).__name__}")
        for held, indices in self._groups:
            if held == curve:
                return list(indices)
        return []

    def getValues(self, *, input=False, unit=_UNSET, timeUnit="frame"):
        """各キーの値を返す(並びはforで取り出す順と同じ)。``input=True`` なら、各キーの入力を返す。

        Args:
            input (bool): Trueなら、値でなく入力(時刻、またはドリブンキーの入力の値)を返す。既定はFalse。
            unit (str): 出力が角度のときの値の単位。既定は ``"deg"``。``input=True`` では指定できない。
            timeUnit (str): 値では出力が時間のとき、入力では入力が時間(T型)のときの単位。

        Returns:
            list[float]: 値、または入力の値。

        Raises:
            TypeError: inputがboolでない場合、input=Trueとunitを同時に指定した場合、またはunit・timeUnitが文字列でない場合。
            ValueError: unit・timeUnitに対応していない単位名の場合。
        """
        _require_bool(input, "input")
        if input and unit is not _UNSET:
            raise TypeError("unitはinput=Trueと同時に指定できません(入力の単位はtimeUnitで指定します)")
        unit = "deg" if unit is _UNSET else unit
        result = []
        for curve, indices in self._groups:
            values = curve.getKeyInputs(timeUnit=timeUnit) if input else curve.getKeyValues(unit=unit, timeUnit=timeUnit)
            result.extend(values[index] for index in indices)
        return result

    def setValue(self, value, *, unit="deg", timeUnit="frame", fast=False, check=False):
        """すべてのキーに同じ値を書き込む(1回のUndoで戻せる)。

        Args:
            value (float): 新しい値。
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 出力が時間のときの単位。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 数値に変換できない型の場合、またはfast・checkがboolでない場合。
            ValueError: 値が有限でない場合、または単位名に対応していない場合。
            IndexError: キーの番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。check=Trueで、キーを格納するアトリビュートが書き込めない場合。
        """
        _require_bool(check, "check")
        with undoChunk("mlibKeyframesSetValue"):
            for curve, indices in self._groups:
                curve._set_key_values(indices, value, unit=unit, timeUnit=timeUnit, fast=fast, check=check)

    def setTangent(self, *, unit="deg", fast=False, check=False, **kwargs):
        """すべてのキーの接線を変える(1回のUndoで戻せる)。引数は :meth:`Keyframe.setTangent` と同じ。

        fast=Trueでも全体を1つのUndoチャンクの中で呼ぶ。ただし、OpenMayaでの更新はUndoに記録されない。

        Args:
            unit (str): 角度の単位。``"deg"`` / ``"rad"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。
            **kwargs: :meth:`Keyframe.setTangent` と同じフラグ。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: unitが文字列でもNoneでもない場合、またはfast・checkがboolでない場合。
            ValueError: フラグが空か知らないものの場合、unitに対応していない場合、
                ウェイト付きの接線でないカーブにinWeight・outWeightを指定した場合(weightedTangentsと一緒に指定した場合を除く)、
                またはfastで正しくない値や、global・知らない接線の型を指定した場合。
            IndexError: キーの番号が正しくない場合。
            RuntimeError: カーブが無効(削除済み)の場合。check=Trueで、キーを格納するアトリビュートが
                ロック・入力の接続などで書き込めない場合。
            NotImplementedError: fastで、入力側の接線にstepnextを指定した場合。
        """
        _require_bool(check, "check")
        for curve, _indices in self._groups:
            _require_weighted(curve, kwargs)
        with undoChunk("mlibKeyframesSetTangent"):
            if check:
                # 途中のカーブで止まって一部だけ変わらないよう、書く前に全部のカーブを確かめる。
                for curve, _indices in self._groups:
                    curve._require_curve_writable()
            for curve, indices in self._groups:
                for index in indices:
                    curve._set_tangent(index, unit=unit, fast=fast, check=check, **kwargs)

    def setBreakdown(self, state=True):
        """すべてのキーをブレイクダウンキーにする、または通常のキーへ戻す(1回のUndoで戻せる)。

        :meth:`Keyframe.setBreakdown` と同じ。カーブごとに1回で書き換える。

        Args:
            state (bool): Trueならブレイクダウンキー、Falseなら通常のキーにする。既定はTrue。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがboolでない場合。
            IndexError: キーの番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        _require_bool(state, "state")
        with undoChunk("mlibKeyframesSetBreakdown"):
            for curve, indices in self._groups:
                curve._set_breakdown(list(indices), state)

    def move(self, *, timeOffset=0, valueOffset=0, unit="deg", timeUnit="frame"):
        """すべてのキーの入力と値をずらす。

        カーブごとに1回で動かし、全体を1回のUndoで戻せる。
        同じカーブの対象のキーどうしは一緒に動くため、互いを越えられない制限は受けない。
        動かさない隣のキーと同じか越える位置になる場合は、何も変えずに例外にする。

        Args:
            timeOffset (float): 入力をずらす量。
            valueOffset (float): 値をずらす量。
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 時間の単位。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: timeOffset・valueOffsetが数値でない(boolを含む)、またはunit・timeUnitが文字列でない場合。
            ValueError: timeOffset・valueOffsetが有限でない場合、unit・timeUnitに対応していない単位名の場合、
                または入力が動かさない隣のキーと同じか越える位置になる場合(何も変えない)。
            IndexError: キーの番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        for curve, indices in self._groups:
            _require_movable(curve, indices, timeOffset, valueOffset, timeUnit)
        with undoChunk("mlibKeyframesMove"):
            for curve, indices in self._groups:
                curve._move_keys(index=indices, timeOffset=timeOffset, valueOffset=valueOffset, unit=unit, timeUnit=timeUnit)

    def delete(self, *, keepCurve=True, fast=False, check=False):
        """すべてのキーを削除する(1回のUndoで戻せる)。

        削除したあとは、この集まりのオブジェクトが別のキーを指すことがある。

        Args:
            keepCurve (bool): Trueなら、すべてのキーを消してもカーブを残す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、すべてのカーブが書き込めるか(ロック・入力の接続が無いか)を確かめて、
                問題があれば何も消さずに例外にする。既定はFalseで、確かめずに消す(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: keepCurve・fast・checkがboolでない場合。
            IndexError: キーの番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。check=Trueで、キーを格納するアトリビュートが書き込めない場合。
        """
        _require_bool(keepCurve, "keepCurve")
        _require_bool(check, "check")
        with undoChunk("mlibKeyframesDelete"):
            if check:
                # 途中のカーブで止まって一部だけ消えないよう、消す前に全部のカーブを確かめる。
                for curve, _indices in self._groups:
                    curve._require_curve_writable()
            for curve, indices in self._groups:
                curve._remove_keys(index=indices, keepCurve=keepCurve, fast=fast, check=check)

    def select(self, *, add=False):
        """Graph Editor・Dope Sheet でこれらのキーを選択する。

        空の集まりで add=False なら、キーの選択を外す。

        Args:
            add (bool): Trueなら今のキーの選択に加える。Falseなら置き換える。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: addがboolでない場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        _require_bool(add, "add")
        with undoChunk("mlibKeyframesSelect"):
            if not add:
                # 対象を省いた selectKey -clear は選択ノードが無いと失敗するため、選んでいるカーブを指定して外す。
                selected = cmds.keyframe(query=True, selected=True, name=True) or []
                if selected:
                    cmds.selectKey(selected, clear=True)
            for curve, indices in self._groups:
                ranges = curve._key_ranges(indices, None, "frame")
                cmds.selectKey(curve._full_name(), index=ranges, add=True, animation="objects")


def _keyframe(curve, index):
    """確認を省いて :class:`Keyframe` を作る(番号を確認済みの集まりから取り出すときに使う)。"""
    keyframe = Keyframe.__new__(Keyframe)
    keyframe._curve = curve
    keyframe._index = index
    return keyframe


def _require_weighted(curve, flags):
    """ウェイト付きの接線でないカーブへ、接線のウェイトを書こうとしていないか確かめる。

    Mayaは、ウェイト付きでないカーブへのウェイトの指定を例外にするが、同じ呼び出しの先のフラグは書き換えたまま残す。
    そのため、何かを書き換える前に確かめる。

    Args:
        curve (AnimCurve): 書き込むカーブ。
        flags (dict): setTangentのフラグ。

    Raises:
        ValueError: ウェイト付きでないカーブに、weightedTangentsなしでinWeight・outWeightを指定した場合。
    """
    if "weightedTangents" in flags or not ("inWeight" in flags or "outWeight" in flags):
        return
    if curve.isValid() and not curve._curve_fn().isWeighted:
        raise ValueError("ウェイト付きの接線でないカーブには、inWeight・outWeightを指定できません(weightedTangents=Trueで切り替えます)")


def _require_movable(curve, indices, time_offset, value_offset, time_unit):
    """キーを動かす前に、量の型と、動かさない隣のキーと同じか越える位置にならないかを確かめる。

    Args:
        curve (AnimCurve): キーを持つカーブ。
        indices (Sequence[int]): 一緒に動かすキーの番号。
        time_offset (float): 入力をずらす量。
        value_offset (float): 値をずらす量。
        time_unit (str): 入力が時間のカーブでの単位。

    Raises:
        TypeError: 量が数値でない(boolを含む)、またはtime_unitが文字列でない場合。
        ValueError: 量が有限でない、time_unitに対応していない、または隣のキーと同じか越える位置になる場合。
        IndexError: 番号がキーの数の範囲から外れた場合。
        RuntimeError: カーブが無効(削除済み)の場合。
    """
    offset = _finite(time_offset, "timeOffset")
    _finite(value_offset, "valueOffset")
    curve._require_valid("キーの移動")
    inputs = curve.getKeyInputs(timeUnit=time_unit)
    moved = set(indices)
    for index in moved:
        curve._index(index)
    if offset == 0.0:
        return
    for index in moved:
        new = inputs[index] + offset
        left = next((number for number in range(index - 1, -1, -1) if number not in moved), None)
        right = next((number for number in range(index + 1, len(inputs)) if number not in moved), None)
        if (left is not None and new <= inputs[left]) or (right is not None and new >= inputs[right]):
            raise ValueError(f"キーの入力が隣のキーと同じか越えるため、動かせません: {curve.getName()}[{index}]")
