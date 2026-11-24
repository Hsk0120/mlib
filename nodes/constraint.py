"""Maya の標準コンストレイントに共通するターゲット・ウェイトの取得と設定を扱う。"""

import maya.cmds as cmds

from ..decorator import _edit_context, _require_bool, undoChunk
from ..plugs.plug import Plugs
from .node import Node, Nodes
from .transform import Transform


class Constraint(Transform):
    """Maya標準のコンストレイントに共通する、ターゲットとウェイトの操作を持つクラス。

    ウェイトは正規化せず、ノードに書かれたままの値を扱う。
    実際のクラスは、parentConstraintなどMayaのノード型ごとに作る。
    ターゲットとウェイトのエイリアスは、各標準コマンドで調べた順のまま対応させ、独自に並べ替えない。
    コンストレイントする相手を探したり、リグを組み立てたりするクラスではない。

    fastを指定したときのウェイトの書き込みはPlugに任せるが、ターゲットやエイリアスを調べるにはcmdsを使う。
    そのため、fastを指定しても、全体がOpenMayaだけで動くわけではない。
    """

    def getTargets(self):
        """登録されているターゲットを取得する。

        ノード型に対応するMaya標準のコンストレイントコマンドで調べる。
        並びはコマンドのtargetListの順のままで、targetマルチアトリビュートの論理番号では並べ替えない。
        この順はgetWeightPlugs()の並びと対応する。

        Returns:
            Nodes: ターゲットの新しいオブジェクト。登録が無ければ空の集まり。
                ノードを複製したものではない。
        """
        names = getattr(cmds, self.getType())(self._full_name(), query=True, targetList=True) or []
        return Nodes._wrap([Node(name) for name in names])

    def getWeightPlugs(self, *, aliases=False):
        """ターゲットのウェイトのアトリビュートを取得する。``aliases=True`` なら、そのエイリアスの名前を取得する。

        Maya標準のコンストレイントコマンドで調べる。

        Args:
            aliases (bool): Trueなら、Plugの代わりにウェイトのエイリアスの名前を返す。既定はFalse。
                ノードにあるエイリアスをすべて返すgetAliases()とは、対象が違う。

        Returns:
            Plugs | list[str]: getTargets()と同じ順に並ぶ。set()で値を変更できる。
                aliases=Trueなら、エイリアスの名前のリスト。

        Raises:
            TypeError: aliasesがboolでない場合。
        """
        _require_bool(aliases, "aliases")
        names = getattr(cmds, self.getType())(self._full_name(), query=True, weightAliasList=True) or []
        if aliases:
            return names
        return Plugs._from_plugs([self.getPlug(alias) for alias in names])

    def getWeights(self, *targets):
        """ターゲットの現在のウェイトを取得する。

        Args:
            *targets (Node | str): このコンストレイントに登録されたターゲット。省略すると全ターゲット。

        Returns:
            list[float]: 正規化しない値。targetsを省略したときはgetTargets()と同じ順、
                渡したときは渡した順に並ぶ(1つ渡しても、要素が1つのリスト)。

        Raises:
            ValueError: 渡したターゲットが登録されていない場合。
        """
        plugs = self.getWeightPlugs()
        if not targets:
            return [plug.get() for plug in plugs]
        available = {node._full_name(): plug for node, plug in zip(self.getTargets(), plugs)}
        result = []
        for target in Nodes._resolve_inputs(targets):
            requested = Node._resolve_input(target)._full_name()
            if requested not in available:
                raise ValueError(f"このコンストレイントにターゲットが見つかりません: {requested}")
            result.append(available[requested].get())
        return result

    def setWeight(self, weight, *targets, fast=False, check=False):
        """ターゲットのウェイトを設定する。

        値は正規化せず、そのまま書き込む。書き込む順はMayaのターゲットの順になる。

        ターゲットを指定した場合は、まず全部が登録されているかを確かめ、重なりをまとめてから書き込む。
        ターゲットは完全名で照らし合わせ、指定した順には並べ替えない。

        書き込みは、Plug.set()に1つずつ任せる。``check=True`` なら、書く前に対象の全部のPlugを確かめる。
        ``check=False`` で途中で失敗すると、それより前の書き込みは残ることがある(失敗時に自動で元に戻すことはしない)。

        Args:
            weight (float): 対象すべてへ設定する値。正規化も、0〜1への制限もしない。
            targets (Node | str): 設定するターゲット。省略すると全ターゲット。
                ターゲットが1つも無ければ、値を確かめずにそのまま返る。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。Plugの書き込みに使う。
                Falseなら、Undoが有効なときに通常の書き込みを1回のUndoにまとめる。Undoの設定は変えない。
                ターゲットやエイリアスを調べるには、fastでもcmdsを使う。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合。
            ValueError: 指定したターゲットがこのコンストレイントに登録されていない場合。
                ``check=True`` で、weightが有限でない場合。
            RuntimeError: ``check=True`` で、ウェイトのアトリビュートがロックや入力の接続などで書き込めない場合。
        """
        with _edit_context("mlibConstraintSetWeight", fast):
            weight_plugs = self.getWeightPlugs()
            if targets:
                requested = {Node._resolve_input(target)._full_name() for target in Nodes._resolve_inputs(targets)}
                available = {node._full_name(): plug for node, plug in zip(self.getTargets(), weight_plugs)}
                missing = requested - available.keys()
                if missing:
                    raise ValueError(f"このコンストレイントにターゲットが見つかりません: {sorted(missing)}")
                # 全ターゲットを解決してから更新する。無効な指定で部分更新しない。
                weight_plugs = [plug for name, plug in available.items() if name in requested]
            if check:
                # 途中で止まって一部だけ書き換わらないよう、書く前に全部を確かめる。
                for plug in weight_plugs:
                    plug._require_writable()
            for plug in weight_plugs:
                plug.set(weight, fast=fast, check=check)

    def removeTarget(self, *targets):
        """ターゲットをコンストレイントから外す。

        ``cmds.<コンストレイント>(target, self, edit=True, remove=True)`` と同じ処理をする。
        Mayaの標準コマンドと同じく、ターゲットのウェイトのアトリビュートと接続も消える。
        最後のターゲットを外すと、Mayaはコンストレイントそのものを削除する。
        Undoが有効なら、1回のUndoで戻せる。

        Args:
            targets (Node | str): 外すターゲット。1つ以上。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: ターゲットを1つも指定しない場合、またはターゲットの型が不正な場合。
            ValueError: ターゲットがこのコンストレイントに登録されていない場合。このときは何も外さない。
            RuntimeError: コンストレイントが無効な場合、またはMayaが変更を拒否した場合。
        """
        if not targets:
            raise TypeError("removeTargetにはターゲットを1つ以上指定してください")
        self._require_valid("ターゲットの削除")
        requested = [Node._resolve_input(target)._full_name() for target in Nodes._resolve_inputs(targets)]
        registered = {node._full_name() for node in self.getTargets()}
        missing = sorted(set(requested) - registered)
        if missing:
            raise ValueError(f"このコンストレイントにターゲットが見つかりません: {missing}")
        with undoChunk("mlibConstraintRemoveTarget"):
            getattr(cmds, self.getType())(*requested, self._full_name(), edit=True, remove=True)
