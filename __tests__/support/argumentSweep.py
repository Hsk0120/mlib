"""公開メソッドの引数を、表から網羅して確かめるテストケース基底。

クラスごとに「正しい呼び方の表」(:class:`support.argumentTable.Method` の並び)を ``METHODS`` に書くと、
メソッドごとに次の4つのテストができる。

- ``test_<メソッド>_values`` (段1): 引数ごとに値の候補を1つずつ差し替えて呼び、例外が出ない
  (docstring の Raises の型は許す)・例外のときシーンが変わらない・``expect`` の確かめ方に合うことを確かめる。
- ``test_<メソッド>_invalid`` (段2): 引数ごとに「違う型の値」を差し替え、docstring の Raises の型になり、
  シーン(ノードの数・名前空間のノードの値・接続)が変わらないことを確かめる。
- ``test_<メソッド>_pairs`` (段3): 2つの引数の値の組(上限つき)で、例外が Raises の型だけ・同時に指定できない組は TypeError・
  通常の書き込みは Undo 1回で戻り redo で同じ・``fast=True`` と通常でシーンが同じ(fast は Undo に残らない)・
  短縮名と長い名前で同じ・set の後の get が同じ・複数形と単数の並びが同じ、のうち当てはまる性質を確かめる。
- ``test_<メソッド>_known``: 表の ``known`` に書いた本体との食い違いが、まだ食い違っていることを確かめる(expectedFailure)。

各テストはメソッド・段ごとの件数・上限で切った数・秒数を出力する。
"""

import inspect
import time
import unittest

import maya.cmds as cmds
from support import argumentTable as table
from support.namespaceCase import NamespaceCase

import mlib


class ArgumentSweepCase(NamespaceCase):
    """``METHODS`` の表から、引数を網羅するテストを作る基底。

    Attributes:
        METHODS (tuple[Method, ...]): 正しい呼び方の表。
        PREFIX (str): 名前空間の先頭。
    """

    METHODS = ()
    PREFIX = "mlibSweep_"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for method in cls.METHODS:
            for stage in ("values", "invalid", "pairs"):
                setattr(cls, f"test_{method.name}_{stage}", _stage_test(method, stage))
            if method.known:
                setattr(cls, f"test_{method.name}_known", unittest.expectedFailure(_known_test(method)))

    # ------------------------------------------------------------------
    # 表から使う補助

    def fresh(self, method):
        """名前空間の中身を作り直し、表の setup で対象を作って返す。

        Args:
            method (Method): 表の1行。

        Returns:
            object: メソッドを呼ぶ対象。
        """
        if cmds.namespace(exists=self.ns):
            cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        cmds.namespace(add=self.ns)
        return method.setup(self)

    def deletedNode(self):
        """削除済みのノードを返す(段2の値)。

        Returns:
            Node: 削除したノード。
        """
        node = mlib.createNode("transform", name=self.name("sweepDeleted#"))
        cmds.delete(str(node))
        return node

    def deletedPlug(self):
        """削除済みのノードの Plug を返す(段2の値)。

        Returns:
            Plug: 削除したノードの translateX。
        """
        node = mlib.createNode("transform", name=self.name("sweepDeleted#"))
        plug = node.getPlug("translateX")
        cmds.delete(str(node))
        return plug

    def sceneState(self):
        """比べるシーンの状態(全体のノードの数、名前空間のノード・keyable の値・ワールドのマトリクス・接続)を返す。

        Returns:
            list: 状態。
        """
        nodes = sorted(cmds.ls(self.ns + ":*", long=True) or [])
        values = []
        for node in nodes:
            for attr in cmds.listAttr(node, keyable=True, scalar=True) or []:
                try:
                    values.append((node, attr, cmds.getAttr(node + "." + attr)))
                except (RuntimeError, ValueError):
                    values.append((node, attr, None))
            if cmds.objectType(node, isAType="transform"):
                values.append((node, "worldMatrix", cmds.getAttr(node + ".worldMatrix[0]")))
        connections = sorted(cmds.listConnections(nodes, connections=True, plugs=True) or []) if nodes else []
        return [len(cmds.ls()), nodes, values, connections]

    # ------------------------------------------------------------------
    # 実行

    def _state(self, method, target):
        return method.state(self, target) if method.state else self.sceneState()

    def _prepare(self, method):
        """表の1行から、対象・引数・Raises・正しい呼び方を作る。"""
        target = self.fresh(method)
        function = getattr(type(target), method.name)
        doc = inspect.getdoc(function) or ""
        signature = inspect.signature(function)
        bound = signature.bind_partial(target, *method.args, **method.kwargs).arguments
        base = {name: value for name, value in bound.items() if name not in ("self", "cls")}
        params = table.parameters(function, doc, skip=method.skip)
        return target, base, params, table.raisesNames(doc)

    def _resolve(self, kwargs):
        return {name: value.make(self) if isinstance(value, table.Lazy) else value for name, value in kwargs.items()}

    def _call(self, method, target, kwargs, raises, stage, undo=False):
        """1回呼び、例外と状態を確かめる。

        Returns:
            tuple: (成功したか, 戻り値, 呼ぶ前の状態, 呼んだ後の状態, 渡した値)。
        """
        resolved = self._resolve(kwargs)
        if undo:
            cmds.flushUndo()
        before = self._state(method, target)
        conflict = method.conflicting(kwargs)
        try:
            result = getattr(target, method.name)(**resolved)
        except Exception as error:
            if conflict:
                self.assertIsInstance(error, TypeError, f"同時に指定できない組の例外が TypeError でない: {error!r}")
            else:
                self.assertTrue(table.isDocumented(error, raises), f"docstring の Raises {sorted(raises)} に無い例外: {error!r}")
            self.assertTrue(table.same(self._state(method, target), before), f"例外({type(error).__name__})のあとシーンが変わった")
            return False, error, before, before, resolved
        if conflict:
            self.fail(f"同時に指定できない組なのに例外にならない(戻り値 {result!r})")
        after = self._state(method, target)
        if method.expect:
            method.expect(self, table.Call(target, resolved, result, stage))
        return True, result, before, after, resolved

    def _cases(self, method, stage, params, base):
        """段ごとの (名前, 引数) の並びと、上限で切った数を返す。"""
        if stage == "values":
            cases = [
                (f"values:{param.name}={value!r}", dict(base, **{param.name: value}))
                for param in params
                for value in param.candidates(method.values.get(param.name, ()), param.name in method.replace)
            ]
            return cases, 0
        if stage == "invalid":
            cases = []
            for param in params:
                values = method.invalid[param.name] if param.name in method.invalid else param.invalidValues()
                for value in values:
                    cases.append((f"invalid:{param.name}={value!r}", dict(base, **{param.name: value})))
            return cases, 0
        candidates = {param.name: param.candidates(method.values.get(param.name, ()), param.name in method.replace) for param in params}
        combos, cut = table.pairs(candidates, method.limit)
        return [("pairs:" + table.label(combo), dict(base, **combo)) for combo in combos], cut

    def _run_case(self, method, stage, kwargs, params, raises, target):
        """1件を確かめる。"""
        if stage == "invalid":
            if method.writes:
                target = self.fresh(method)
            resolved = self._resolve(kwargs)
            before = self._state(method, target)
            try:
                result = getattr(target, method.name)(**resolved)
            except Exception as error:
                self.assertTrue(table.isDocumented(error, raises), f"docstring の Raises {sorted(raises)} に無い例外: {error!r}")
            else:
                self.fail(f"違う型の値を受け付けた(戻り値 {result!r})")
            self.assertTrue(table.same(self._state(method, target), before), "例外のあとシーンが変わった")
            return
        if stage == "values":
            if method.writes:
                target = self.fresh(method)
            self._call(method, target, kwargs, raises, stage)
            return
        self._check_pair(method, kwargs, params, raises, target)

    def _check_pair(self, method, kwargs, params, raises, target):
        """段3の1件: 性質を確かめる。"""
        names = {param.name for param in params}
        if method.writes:
            target = self.fresh(method)
        ok, result, before, after, resolved = self._call(method, target, kwargs, raises, "pairs", undo=method.writes)
        if not ok:
            return
        if method.writes:
            if kwargs.get("fast") is True:
                self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True), "fast=True なのに Undo に記録した")
            elif cmds.undoInfo(query=True, undoQueueEmpty=True):
                self.assertTrue(table.same(after, before), "Undo に記録せずにシーンを変えた")
            else:
                cmds.undo()
                self.assertTrue(table.same(self._state(method, target), before), "Undo 1回で元に戻らない")
                self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True), "Undo 1回で戻したあと、まだ Undo の記録が残る")
                cmds.redo()
                self.assertTrue(table.same(self._state(method, target), after), "redo で同じ結果にならない")
            if "fast" in names and "fast" not in kwargs and not kwargs.get("get"):
                fast_target = self.fresh(method)
                fast_ok, fast_result, _, fast_after, _ = self._call(method, fast_target, dict(kwargs, fast=True), raises, "pairs")
                self.assertTrue(fast_ok, f"fast=True だけ例外になった: {fast_result!r}")
                self.assertTrue(table.same(fast_after, after), "fast=True と通常でシーンの結果が違う")
        for param in params:
            if param.alias and param.alias in kwargs and param.name not in kwargs and param.alias in names:
                renamed = {(param.name if name == param.alias else name): value for name, value in kwargs.items()}
                alias_target = self.fresh(method) if method.writes else target
                alias_ok, alias_result, _, alias_after, _ = self._call(method, alias_target, renamed, raises, "pairs")
                self.assertTrue(alias_ok, f"短縮名 {param.name} だけ例外になった: {alias_result!r}")
                self.assertTrue(table.same(alias_result, result), f"短縮名 {param.name} と {param.alias} で戻り値が違う")
                if method.writes:
                    self.assertTrue(table.same(alias_after, after), f"短縮名 {param.name} と {param.alias} でシーンの結果が違う")
        trip = method.roundTrip
        if trip and not (trip.skip and trip.skip(kwargs)):
            if method.writes:
                target = self.fresh(method)
                self._call(method, target, kwargs, raises, "pairs")
            shared = {name: resolved[name] for name in trip.shared if name in resolved}
            value = getattr(target, trip.getter)(**shared)
            self.assertTrue(table.same(value, resolved[trip.value], trip.places), f"{trip.getter} が書いた値と違う: {value!r}")
        if method.plural:
            self._check_plural(method, kwargs, raises, result, after)

    def _check_plural(self, method, kwargs, raises, result, after):
        """複数形から呼んだ結果が、単数を1つずつ呼んだ結果の並びと同じことを確かめる。"""
        if method.writes:
            self.fresh(method)
            plural, singles = method.plural(self)
        else:
            # 読むだけのメソッドは、組ごとにノードを作り足さないよう、段の最初に作った複数形を使い回す。
            if self._plural is None:
                self._plural = method.plural(self)
            plural, singles = self._plural
        resolved = self._resolve(kwargs)
        plural_result = getattr(plural, method.name)(**resolved)
        plural_after = self.sceneState()
        if method.writes:
            self.fresh(method)
            plural, singles = method.plural(self)
            single_result = [getattr(single, method.name)(**resolved) for single in singles]
            self.assertTrue(table.same(plural_after, self.sceneState()), "複数形と単数の並びでシーンの結果が違う")
        else:
            single_result = [getattr(single, method.name)(**resolved) for single in singles]
            self.assertTrue(table.same(list(plural_result), single_result), "複数形の結果が単数の並びと違う")

    def _sweep(self, method, stage, knownOnly=False):
        """段を実行し、件数と秒数を出力する。knownOnly なら known の場合だけを実行して、食い違いの数を返す。"""
        start = time.perf_counter()
        self._plural = None
        target, base, params, raises = self._prepare(method)
        cases, cut = self._cases(method, stage, params, base)
        run = skipped = 0
        failures = []
        for name, kwargs in cases:
            reason = method.isKnown(name)
            if bool(reason) != knownOnly:
                skipped += 1
                continue
            run += 1
            if knownOnly:
                try:
                    self._run_case(method, stage, kwargs, params, raises, target)
                except Exception as error:
                    failures.append(f"{name}: {error}")
                else:
                    print(f"[argumentSweep] 食い違いが直った可能性(known から外す): {method.name} {name}")
                continue
            with self.subTest(stage=stage, args=name[len(stage) + 1 :]):
                self._run_case(method, stage, kwargs, params, raises, target)
        seconds = time.perf_counter() - start
        if knownOnly:
            if run:
                print(f"[argumentSweep] {type(target).__name__}.{method.name} {stage} known: {run}件 {seconds:.2f}秒 食い違い{len(failures)}件")
            return failures
        note = f" 上限{method.limit}で{cut}件を省略" if cut else ""
        known = f" known{skipped}件は別" if skipped else ""
        print(f"[argumentSweep] {type(target).__name__}.{method.name} {stage}: {run}件 {seconds:.2f}秒{note}{known}")
        uncovered = [param.name for param in params if param.name not in base and not param.candidates(method.values.get(param.name, ()))]
        if stage == "values" and uncovered:
            print(f"[argumentSweep] {method.name}: 候補が無い引数(表の values に書く): {', '.join(uncovered)}")
        return failures


def _stage_test(method, stage):
    def test(self):
        self._sweep(method, stage)

    test.__doc__ = f"{method.name} の引数を網羅する({stage})。"
    return test


def _known_test(method):
    def test(self):
        failures = []
        for stage in ("values", "invalid", "pairs"):
            failures += self._sweep(method, stage, knownOnly=True)
        if failures:
            raise AssertionError("本体との食い違い(known):\n" + "\n".join(failures))

    test.__doc__ = f"{method.name} の、表に記録した本体との食い違いがまだあることを確かめる。"
    return test
