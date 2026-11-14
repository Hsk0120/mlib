# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""マルチアトリビュートの論理番号と、要素のPlugを扱う。"""

import operator
from contextlib import nullcontext
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.attributeType import _convert_angles, _convert_times, _convert_units, _plain_angle_unit, _plain_time_unit, is_internal_data_type, value_reader
from ..decorator import _edit_context, _require_bool, undoChunk
from .plug import MAX_LOGICAL_INDEX, Plug, _instance_count
from typing import Iterator
from mlib.nodes.node import Node


def _descendants(mplug: om2.MPlug, steps: tuple[tuple[str, int], ...] = ...) -> Iterator[tuple[tuple[tuple[str, int], ...], om2.MPlug]]:
    """Plug自身と、その下のPlugを深さ優先で1つずつ返す。

    下へたどるのは、コンパウンドアトリビュートの子と、マルチアトリビュートのすでにある要素。

    Args:
        mplug (om2.MPlug): 起点のPlug。
        steps (tuple[tuple[str, int], ...]): 起点までのたどり方(``("child", 番号)``・``("element", 論理番号)``)。

    Yields:
        tuple[tuple[tuple[str, int], ...], om2.MPlug]: 起点からのたどり方と、Plug。
    """
    ...

def _follow(mplug: om2.MPlug, steps: tuple[tuple[str, int], ...]) -> om2.MPlug:
    """_descendants のたどり方に従って、別の要素から同じ位置のPlugを取得する。

    要素は作らない。

    Args:
        mplug (om2.MPlug): 起点のPlug。
        steps (tuple[tuple[str, int], ...]): たどり方。

    Returns:
        om2.MPlug: たどった先のPlug。
    """
    ...


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
    def __getitem__(self, index: int) -> Plug:
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
        ...
    def __contains__(self, item: int | Plug) -> bool:
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
        ...
    def __iter__(self) -> Iterator[Plug]:
        """すでにある要素を、論理番号の順に1つずつ返す。

        反復を始めた時点のgetElements()の結果を使う。欠けている番号は返さない。要素の値は読み出さない。

        Returns:
            Iterator[Plug]: 反復を始めた時点で集めた要素のイテレーター。
        """
        ...
    def get(self, *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ...) -> dict[int, object]:
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
        ...
    def getElement(self, index: int) -> Plug:
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
        ...
    def getElements(self) -> list[Plug]:
        """すでにある要素のPlugを、論理番号の小さい順に取得する。

        getIndices()の番号の要素だけを返す。欠けている番号は埋めず、要素の値も読み出さない。
        まだ作られていない要素も取得できる :meth:`getElement` とは、この点が違う。
        worldSpaceのアトリビュートでは、評価の前でもDAGのインスタンス番号の要素を含む。

        Returns:
            list[Plug]: 要素の新しいオブジェクトのリスト。ノードは共有し、シーンのものを複製しない。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    def getNextAvailable(self, start: int = ..., checkLocked: bool = ..., checkChildren: bool = ..., *, vacant: bool = ...) -> Plug:
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
        ...
    def removeElement(self, index: int, shift: bool = ..., *, fast: bool = ...) -> MultiPlug:
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
        ...
    def compact(self) -> MultiPlug:
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
        ...
    def getSourceNodes(self) -> dict[int, Node]:
        """各要素へつながっている接続元のノードを、論理番号の順に取得する。

        Returns:
            dict[int, Node]: 論理番号をキーにした接続元のノード。接続のある要素だけを含み、
                接続の無い番号は詰めずに抜けたままにする。
        """
        ...
    def appendMessage(self, node: str | Node, *, fast: bool = ...) -> int:
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
        ...
    def getIndices(self) -> list[int]:
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
        ...
    def getConnectedIndices(self) -> list[int]:
        """接続のある要素の論理番号を、小さい順に取得する。

        要素自身か、その下(コンパウンドアトリビュートの子・入れ子の要素)に、入力か出力の接続がある要素を返す。
        ``MPlug.numConnectedElements`` / ``connectionByPhysicalIndex`` で求める。値だけを持つ要素は含まない。

        Returns:
            list[int]: 論理番号の新しいリスト。接続が無ければ空リスト。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    def _require_movable(self, indices: list[int]) -> None:
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
        ...
    def _move_elements(self, moves: list[tuple[int, int]]) -> None:
        """要素の値と、入力・出力の接続を、cmdsで別の番号の要素へ移す。

        先にすべての要素の値と接続を集め、移す元をすべて削除する。そのあと移す先へ値を設定し、接続し直す。
        移す先は、移す元を削除したあとに空いている番号でなければならない(compact・shiftの順番ならそうなる)。

        Args:
            moves (list[tuple[int, int]]): (移す元の論理番号, 移す先の論理番号)の並び。

        Returns:
            None: 値を返さない。
        """
        ...
    def _capture_element(self, index: int) -> tuple[list, list, list]:
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
        ...
    @staticmethod
    def _validated_logical_index(index: int) -> int:
        """要素の取得・編集に使う論理番号を確かめて、intで返す。

        Args:
            index (int): 対象要素の論理番号。``operator.index`` で整数へ変換できる値(boolを除く)。

        Returns:
            int: 検証済みの論理番号。

        Raises:
            TypeError: boolまたは整数以外の場合。
            IndexError: 0〜2147483647の範囲外の場合。
        """
        ...
    def _element_at(self, index: int) -> Plug:
        """書き込み・接続に使う要素を取得する。欠けている番号の要素は作らない。

        Args:
            index (int): 論理番号。

        Returns:
            Plug: 型に合ったPlug。作ると危険な内部データ型の要素で、まだ無いものは拒否する。
        """
        ...
