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
    mlib.getNode("pCube1_translateX").getKeyframe(0).setValue(5)
"""

import maya.cmds as cmds

from ..decorator import _require_bool, undoChunk


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

    def getTime(self, *, timeUnit="frame"):
        """キーの入力(時刻、またはドリブンキーの入力の値)を返す。

        Args:
            timeUnit (str): 入力が時間(T型)のときの単位。``"frame"`` / ``"sec"``。

        Returns:
            float: 入力の値。

        Raises:
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        self._require_valid()
        return self._curve.getKeyInputs(timeUnit=timeUnit)[self._index]

    def getValue(self, *, unit="deg", timeUnit="frame"):
        """キーの値を返す。

        Args:
            unit (str): 出力が角度(A型)のときの単位。``"deg"`` / ``"rad"``。
            timeUnit (str): 出力が時間のときの単位。``"frame"`` / ``"sec"``。

        Returns:
            float: 値。

        Raises:
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        self._require_valid()
        return self._curve.getKeyValues(unit=unit, timeUnit=timeUnit)[self._index]

    def setValue(self, value, *, unit="deg", timeUnit="frame", fast=False):
        """キーの値を、接線の型を保ったまま変える。

        Args:
            value (float): 新しい値(:meth:`getValue` と同じ単位)。
            unit (str): 出力が角度(A型)のときの単位。``"deg"`` / ``"rad"``。
            timeUnit (str): 出力が時間のときの単位。``"frame"`` / ``"sec"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Keyframe: 自身。

        Raises:
            TypeError: 数値に変換できない型の場合、またはfastがboolでない場合。
            ValueError: 値が有限でない場合、または単位名に対応していない場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        self._curve._set_key_values(self._index, value, unit=unit, timeUnit=timeUnit, fast=fast)
        return self

    def getTangent(self, *, unit="deg"):
        """接線の型・角度・ウェイト・ロックを返す。

        :meth:`AnimCurve.getTangent <mlib.nodes.animCurve.AnimCurve.getTangent>` と同じ。

        Args:
            unit (str): 角度の単位。``"deg"`` / ``"rad"``。

        Returns:
            dict: AnimCurve.getTangent と同じ辞書。
        """
        return self._curve.getTangent(self._index, unit=unit)

    def setTangent(self, *, unit="deg", fast=False, **kwargs):
        """接線を変える。

        :meth:`AnimCurve.setTangent <mlib.nodes.animCurve.AnimCurve.setTangent>` と同じ。

        Args:
            unit (str): 角度の単位。``"deg"`` / ``"rad"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            **kwargs: AnimCurve.setTangent と同じフラグ。

        Returns:
            Keyframe: 自身。
        """
        self._curve.setTangent(self._index, unit=unit, fast=fast, **kwargs)
        return self

    def isBreakdown(self):
        """ブレイクダウンキーか調べる。

        :meth:`AnimCurve.isBreakdown <mlib.nodes.animCurve.AnimCurve.isBreakdown>` と同じ。

        Returns:
            bool: ブレイクダウンキーならTrue。

        Raises:
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        self._require_valid()
        return self._curve.isBreakdown(self._index)

    def setBreakdown(self, state=True):
        """ブレイクダウンキーにする、または通常のキーへ戻す。

        :meth:`AnimCurve.setBreakdown <mlib.nodes.animCurve.AnimCurve.setBreakdown>` と同じ。

        Args:
            state (bool): Trueならブレイクダウンキー、Falseなら通常のキーにする。既定はTrue。

        Returns:
            Keyframe: 自身。

        Raises:
            TypeError: stateがboolでない場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        self._curve.setBreakdown(self._index, state)
        return self

    def move(self, *, timeOffset=0, valueOffset=0, unit="deg", timeUnit="frame"):
        """キーの入力と値をずらす。

        :meth:`AnimCurve.moveKey <mlib.nodes.animCurve.AnimCurve.moveKey>` と同じ。
        入力は隣のキーを越えない(Mayaの ``keyframe -relative`` と同じ)。番号は変わらない。

        Args:
            timeOffset (float): 入力をずらす量。
            valueOffset (float): 値をずらす量。
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 時間の単位。

        Returns:
            Keyframe: 自身。
        """
        self._curve.moveKey(self._index, timeOffset=timeOffset, valueOffset=valueOffset, unit=unit, timeUnit=timeUnit)
        return self

    def remove(self, *, keepCurve=True, fast=False):
        """キーを削除する。

        削除したあとは、同じカーブでこれより後ろの番号を持つオブジェクトが、別のキーを指すようになる。

        Args:
            keepCurve (bool): Trueなら、最後のキーを消してもカーブを残す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。
        """
        self._curve.removeKey(self._index, keepCurve=keepCurve, fast=fast)

    def select(self, *, add=False):
        """Graph Editor・Dope Sheet でこのキーを選択する。

        Args:
            add (bool): Trueなら今のキーの選択に加える。Falseなら置き換える。

        Returns:
            Keyframe: 自身。
        """
        Keyframes([self]).select(add=add)
        return self

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
            list[AnimCurve]: カーブ(最初に出てきた順。同じものは1回だけ)。
        """
        return [curve for curve, _ in self._groups]

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
        """
        for held, indices in self._groups:
            if held == curve:
                return list(indices)
        return []

    def getTimes(self, *, timeUnit="frame"):
        """各キーの入力を返す(並びはforで取り出す順と同じ)。

        Args:
            timeUnit (str): 入力が時間(T型)のときの単位。

        Returns:
            list[float]: 入力の値。
        """
        result = []
        for curve, indices in self._groups:
            inputs = curve.getKeyInputs(timeUnit=timeUnit)
            result.extend(inputs[index] for index in indices)
        return result

    def getValues(self, *, unit="deg", timeUnit="frame"):
        """各キーの値を返す(並びはforで取り出す順と同じ)。

        Args:
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 出力が時間のときの単位。

        Returns:
            list[float]: 値。
        """
        result = []
        for curve, indices in self._groups:
            values = curve.getKeyValues(unit=unit, timeUnit=timeUnit)
            result.extend(values[index] for index in indices)
        return result

    def setValue(self, value, *, unit="deg", timeUnit="frame", fast=False):
        """すべてのキーに同じ値を書き込む(1回のUndoで戻せる)。

        Args:
            value (float): 新しい値。
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 出力が時間のときの単位。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Keyframes: 自身。
        """
        with undoChunk("mlibKeyframesSetValue"):
            for curve, indices in self._groups:
                curve._set_key_values(indices, value, unit=unit, timeUnit=timeUnit, fast=fast)
        return self

    def setTangent(self, *, unit="deg", fast=False, **kwargs):
        """すべてのキーの接線を変える(1回のUndoで戻せる)。引数は :meth:`Keyframe.setTangent` と同じ。

        fast=Trueでも全体を1つのUndoチャンクの中で呼ぶ。ただし、OpenMayaでの更新はUndoに記録されない。

        Args:
            unit (str): 角度の単位。``"deg"`` / ``"rad"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            **kwargs: :meth:`AnimCurve.setTangent <mlib.nodes.animCurve.AnimCurve.setTangent>` と同じフラグ。

        Returns:
            Keyframes: 自身。

        Raises:
            TypeError: unitが文字列でもNoneでもない場合。
            ValueError: フラグが空か知らないものの場合、unitに対応していない場合、
                またはfastで正しくない値や、global・知らない接線の型を指定した場合。
            IndexError: キーの番号が正しくない場合。
            RuntimeError: カーブが無効(削除済み)の場合。
            NotImplementedError: fastで、入力側の接線にstepnextを指定した場合。
        """
        with undoChunk("mlibKeyframesSetTangent"):
            for curve, indices in self._groups:
                for index in indices:
                    curve.setTangent(index, unit=unit, fast=fast, **kwargs)
        return self

    def move(self, *, timeOffset=0, valueOffset=0, unit="deg", timeUnit="frame"):
        """すべてのキーの入力と値をずらす。

        カーブごとに1回で動かし、全体を1回のUndoで戻せる。
        同じカーブの対象のキーどうしは一緒に動くため、互いを越えられない制限は受けない。

        Args:
            timeOffset (float): 入力をずらす量。
            valueOffset (float): 値をずらす量。
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 時間の単位。

        Returns:
            Keyframes: 自身。
        """
        with undoChunk("mlibKeyframesMove"):
            for curve, indices in self._groups:
                curve.moveKey(indices, timeOffset=timeOffset, valueOffset=valueOffset, unit=unit, timeUnit=timeUnit)
        return self

    def remove(self, *, keepCurve=True, fast=False):
        """すべてのキーを削除する(1回のUndoで戻せる)。

        削除したあとは、この集まりのオブジェクトが別のキーを指すことがある。

        Args:
            keepCurve (bool): Trueなら、すべてのキーを消してもカーブを残す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。
        """
        with undoChunk("mlibKeyframesRemove"):
            for curve, indices in self._groups:
                curve.removeKey(indices, keepCurve=keepCurve, fast=fast)

    def select(self, *, add=False):
        """Graph Editor・Dope Sheet でこれらのキーを選択する。

        空の集まりで add=False なら、キーの選択を外す。

        Args:
            add (bool): Trueなら今のキーの選択に加える。Falseなら置き換える。

        Returns:
            Keyframes: 自身。

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
                cmds.selectKey(curve.getFullName(), index=ranges, add=True, animation="objects")
        return self


def _keyframe(curve, index):
    """確認を省いて :class:`Keyframe` を作る(番号を確認済みの集まりから取り出すときに使う)。"""
    keyframe = Keyframe.__new__(Keyframe)
    keyframe._curve = curve
    keyframe._index = index
    return keyframe
