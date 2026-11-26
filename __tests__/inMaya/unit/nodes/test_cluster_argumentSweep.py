"""Clusterの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
GeometryFilter から受け継いだメソッドは ``test_geometryFilter_argumentSweep.py`` が cluster で確かめる。
"""

import contextlib
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method


@contextlib.contextmanager
def _current(case):
    """名前空間を今の名前空間にする(Maya が自動で作るノードも名前空間の中に入れるため)。"""
    previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
    cmds.namespace(set=":" + case.ns)
    try:
        yield
    finally:
        cmds.namespace(set=previous)


def _cluster(case):
    """平面を変形する cluster を作り、Cluster を返す。"""
    with _current(case):
        plane = cmds.polyPlane(name="plane", subdivisionsX=2, subdivisionsY=1, constructionHistory=False)[0]
        cmds.cluster(plane)
    return mlib.getNode(cmds.ls(case.ns + ":*", type="cluster")[0])


def _handleless(case):
    """ハンドルの接続を外した cluster を返す(None を返す場合)。"""
    node = _cluster(case)
    source = cmds.listConnections(f"{node}.matrix", source=True, destination=False, plugs=True)[0]
    cmds.disconnectAttr(source, f"{node}.matrix")
    return node


def _expect_weighted(case, call):
    sources = cmds.ls(cmds.listConnections(f"{call.target}.matrix", source=True, destination=False) or [], long=True)
    case.assertEqual(None if call.result is None else call.result.getName(full=True), sources[0] if sources else None)


METHODS = (Method("getWeightedNode", _cluster, expect=_expect_weighted),)
#: ハンドルの無い cluster での呼び方。
HANDLELESS_METHODS = (Method("getWeightedNode", _handleless, expect=_expect_weighted),)


class _ClusterSweepCase(ArgumentSweepCase):
    """この表の基底。

    部品の段1は引数の無いメソッドを呼ばず、段3は引数が1つのメソッドで組を作らない(Undo・fast を確かめない)ので、
    その2つの場合だけ、引数なしの1回・候補を1つずつの呼び出しを足す(findings4/sweep-deform.md の部品への要望)。
    """

    PREFIX = "mlibSweepCluster_"

    def _cases(self, method, stage, params, base):
        cases, cut = super()._cases(method, stage, params, base)
        if stage == "invalid" or len(params) > 1 or (stage == "values" and params):
            return cases, cut
        if not params:
            return [(f"{stage}:(引数なし)", dict(base))], cut
        param = params[0]
        values = param.candidates(method.values.get(param.name, ()), param.name in method.replace)
        return [(f"pairs:{param.name}={value!r}", dict(base, **{param.name: value})) for value in values], cut


class ClusterArgumentSweepTest(_ClusterSweepCase):
    """Cluster の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


class ClusterHandlelessArgumentSweepTest(_ClusterSweepCase):
    """ハンドルの接続が無い Cluster で、getWeightedNode が None を返すことを確かめる。"""

    METHODS = HANDLELESS_METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
