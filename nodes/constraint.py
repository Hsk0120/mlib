"""Maya の標準コンストレイントに共通するターゲット・ウェイトの取得と設定を扱う。"""

import maya.cmds as cmds

from ..decorator import _edit_context, undoChunk
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
        この順はgetWeightAliases()の並びと対応する。

        Returns:
            list[Node]: ターゲットの新しいオブジェクトのリスト。登録が無ければ空リスト。
                ノードを複製したものではない。
        """
        names = getattr(cmds, self.getType())(self.getFullName(), query=True, targetList=True) or []
        return [Node(name) for name in names]

    def getWeightAliases(self):
        """登録されているターゲットの、ウェイトのエイリアスを取得する。

        Maya標準のコンストレイントコマンドで調べる。

        Returns:
            list[str]: エイリアスの名前。getTargets()と同じ順に並ぶ。
                ノードにあるエイリアスをすべて返すgetAliases()とは、対象が違う。
        """
        return getattr(cmds, self.getType())(self.getFullName(), query=True, weightAliasList=True) or []

    def getWeightPlugs(self):
        """ターゲットのウェイトのアトリビュートを取得する。

        Returns:
            list[Plug]: getTargets()と同じ順に並ぶ。set()で値を変更できる。
        """
        return [self.getPlug(alias) for alias in self.getWeightAliases()]

    def getWeights(self):
        """ターゲットの現在のウェイトを取得する。

        Returns:
            list[float]: getTargets()と同じ順に並ぶ値。正規化はしない。
        """
        return [plug.get() for plug in self.getWeightPlugs()]

    def getWeight(self, target):
        """指定したターゲットの現在のウェイトを取得する。

        Args:
            target (Node | str): このコンストレイントに登録されたターゲット。

        Returns:
            float: ウェイトの値。正規化はしない。

        Raises:
            ValueError: ターゲットが登録されていない場合。
        """
        requested = Node._resolve_input(target).getFullName()
        for node, plug in zip(self.getTargets(), self.getWeightPlugs()):
            if node.getFullName() == requested:
                return plug.get()
        raise ValueError(f"このコンストレイントにターゲットが見つかりません: {requested}")

    def setWeight(self, weight, *targets, fast=False):
        """ターゲットのウェイトを設定する。

        値は正規化せず、そのまま書き込む。書き込む順はMayaのターゲットの順になる。

        ターゲットを指定した場合は、まず全部が登録されているかを確かめ、重なりをまとめてから書き込む。
        ターゲットは完全名で照らし合わせ、指定した順には並べ替えない。

        書き込めるかの確認と書き込みは、Plug.set()に1つずつ任せる。
        そのため、途中で失敗すると、それより前の書き込みは残ることがある。
        前もって全部のPlugを確かめたり、失敗時に自動で元に戻したりはしない。

        Args:
            weight (float): 対象すべてへ設定する値。正規化も、0〜1への制限もしない。
            targets (Node | str): 設定するターゲット。省略すると全ターゲット。
                ターゲットが1つも無ければ、値を確かめずにそのまま返る。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。Plugの書き込みに使う。
                Falseなら、Undoが有効なときに通常の書き込みを1回のUndoにまとめる。Undoの設定は変えない。
                ターゲットやエイリアスを調べるには、fastでもcmdsを使う。

        Returns:
            Constraint: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
            ValueError: 指定したターゲットがこのコンストレイントに登録されていない場合。
        """
        with _edit_context("mlibConstraintSetWeight", fast):
            weight_plugs = self.getWeightPlugs()
            if not targets:
                for plug in weight_plugs:
                    plug.set(weight, fast=fast)
                return self
            requested = {Node._resolve_input(target).getFullName() for target in Nodes._resolve_inputs(targets)}
            available = {node.getFullName(): plug for node, plug in zip(self.getTargets(), weight_plugs)}
            missing = requested - available.keys()
            if missing:
                raise ValueError(f"このコンストレイントにターゲットが見つかりません: {sorted(missing)}")
            # 全ターゲットを解決してから更新する。無効な指定で部分更新しない。
            for name, plug in available.items():
                if name in requested:
                    plug.set(weight, fast=fast)
            return self

    def removeTarget(self, *targets):
        """ターゲットをコンストレイントから外す。

        ``cmds.<コンストレイント>(target, self, edit=True, remove=True)`` と同じ処理をする。
        Mayaの標準コマンドと同じく、ターゲットのウェイトのアトリビュートと接続も消える。
        最後のターゲットを外すと、Mayaはコンストレイントそのものを削除する。
        Undoが有効なら、1回のUndoで戻せる。

        Args:
            targets (Node | str): 外すターゲット。1つ以上。

        Returns:
            Constraint: 自身。

        Raises:
            TypeError: ターゲットを1つも指定しない場合、またはターゲットの型が不正な場合。
            ValueError: ターゲットがこのコンストレイントに登録されていない場合。このときは何も外さない。
            RuntimeError: コンストレイントが無効な場合、またはMayaが変更を拒否した場合。
        """
        if not targets:
            raise TypeError("removeTargetにはターゲットを1つ以上指定してください")
        self._require_valid("ターゲットの削除")
        requested = [Node._resolve_input(target).getFullName() for target in Nodes._resolve_inputs(targets)]
        registered = {node.getFullName() for node in self.getTargets()}
        missing = sorted(set(requested) - registered)
        if missing:
            raise ValueError(f"このコンストレイントにターゲットが見つかりません: {missing}")
        with undoChunk("mlibConstraintRemoveTarget"):
            getattr(cmds, self.getType())(*(requested + [self.getFullName()]), edit=True, remove=True)
        return self
