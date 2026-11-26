"""``Node.getConnections`` のフラグと、通っていなかった照会・削除の経路のテスト。

- getConnections の s・d・scn・connections を cmds.listConnections と比べる。
- getName(full=False)・getPlugs(children=False, connectable=True) を cmds と比べる。
- delete(skipConnected=True) の DGノードと、同じShapeを2つの親に持つ階層を確かめる。
- インスタンスのShapeのアトリビュートを、Shapeより前に子を持つtransformの名前で取得する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """このテストファイルの名前空間の先頭と、接続の作成。"""

    PREFIX = "mlibSpecNodeConnections_"

    def wired(self):
        """source.tx → node.tx、node.rx → target.ty(unitConversionを挟む)、node.sx → target.sz の接続を作る。"""
        source, node, target = (mlib.getNode(self.make(text=text)) for text in ("source", "node", "target"))
        cmds.connectAttr(f"{source}.translateX", f"{node}.translateX")
        cmds.connectAttr(f"{node}.rotateX", f"{target}.translateY")
        cmds.connectAttr(f"{node}.scaleX", f"{target}.scaleZ")
        return source, node, target

    @staticmethod
    def node_names(nodes):
        """ノードの名前の集合。"""
        return {node.getName() for node in nodes}


class GetConnectionsFlagsTest(_Case):
    """s・d・scn・connections を cmds.listConnections の結果と比べる。"""

    def test_direction_flags(self):
        """s=Falseは出力側だけ、d=Falseは入力側だけを返し、cmdsのsource・destinationと同じノードになる。"""
        _source, node, _target = self.wired()
        name = str(node)
        outputs = node.getConnections(s=False, asNode=True)
        inputs = node.getConnections(d=False, asNode=True)
        self.assertEqual(self.node_names(outputs), set(cmds.listConnections(name, source=False) or []))
        self.assertEqual(self.node_names(inputs), set(cmds.listConnections(name, destination=False) or []))
        self.assertTrue(any(item.getType() == "unitConversion" for item in outputs))
        self.assertEqual(list(node.getConnections(s=False, d=False)), [])

    def test_skip_conversion_short_name(self):
        """scn=Trueは変換ノードを飛ばし、cmdsのskipConversionNodes=Trueと同じノードになる。"""
        _source, node, target = self.wired()
        result = node.getConnections(scn=True, asNode=True)
        expected = cmds.listConnections(str(node), skipConversionNodes=True) or []
        self.assertEqual(self.node_names(result), set(expected))
        self.assertIn(target.getName(), self.node_names(result))
        self.assertFalse(any(item.getType() == "unitConversion" for item in result))

    def test_connections_pairs(self):
        """asPair=Trueは自身の側と相手の側のPlugの組で返し、cmdsのconnections・plugsと同じ組になる。connections・cは受けず、短縮名と長い名前の同時指定はTypeError。"""
        _source, node, _target = self.wired()
        pairs = node.getConnections(asPair=True)
        for flags in (
            {"connections": True},
            {"c": True},
            {"s": False, "source": False},
            {"t": "transform", "type": "transform"},
            {"et": True, "exactType": True},
        ):
            with self.subTest(flags=flags), self.assertRaises(TypeError):
                node.getConnections(**flags)
        flat = cmds.listConnections(str(node), connections=True, plugs=True) or []
        # cmdsの名前は短縮名のこともあるため、同じ決まりの名前(ノードの一意名とロング名)へそろえて比べる。
        expected = {(str(mlib.getPlug(flat[index])), str(mlib.getPlug(flat[index + 1]))) for index in range(0, len(flat), 2)}
        actual = {(str(mine), str(other)) for mine, other in pairs}
        self.assertEqual(actual, expected)
        self.assertEqual(len(pairs), len(expected))


class NodeQueriesTest(_Case):
    """getName・getPlugsの、通っていなかった指定。"""

    def test_get_name_full_false(self):
        """full=Falseは既定と同じ一意な名前を返し、cmds.lsの名前と合う。"""
        parent = self.make(text="parent")
        node = mlib.getNode(self.make(text="child", parent=parent))
        self.assertEqual(node.getName(full=False), node.getName())
        self.assertEqual(cmds.ls(node.getName(full=False), long=True), cmds.ls(node.getName(full=True), long=True))

    def test_get_plugs_without_children_by_list_attr(self):
        """cmds.listAttrを使うフラグとincludeChildren=Falseでは、子のアトリビュートを除く。"""
        node = mlib.getNode(self.make(text="node"))
        listed = cmds.listAttr(str(node), connectable=True)
        self.assertTrue(any("." in name for name in listed))
        names = [plug.getAttributeName() for plug in node.getPlugs(children=False, connectable=True)]
        # 子のアトリビュートは、cmds.attributeQueryで親を持つもの(``boundingBoxMinX`` などの「.」の無い名前も含む)。
        expected = [name for name in listed if "." not in name and not cmds.attributeQuery(name, node=str(node), listParent=True)]
        self.assertEqual(names, expected)
        self.assertFalse([plug for plug in node.getPlugs(children=False, connectable=True) if plug.mplug().isChild])


class DeleteSkipConnectedTest(_Case):
    """delete(skipConnected=True) の、DGノードと共有したShapeを含む階層。"""

    def test_dg_node(self):
        """接続の無いDGノードは削除し、接続のあるDGノードは残す。Undo 1回で戻る。"""
        free = mlib.getNode(self.make("multiplyDivide", "free"))
        linked = mlib.getNode(self.make("multiplyDivide", "linked"))
        cmds.connectAttr(f"{linked}.outputX", f"{linked}.input1Y")
        self.flushUndo()
        free.delete(skipConnected=True)
        self.assertFalse(cmds.objExists(self.name("free")))
        cmds.undo()
        self.assertTrue(cmds.objExists(self.name("free")))
        linked.delete(skipConnected=True)
        self.assertTrue(cmds.objExists(self.name("linked")))

    def test_shared_shape_is_checked_once(self):
        """同じShapeを2つの親の下に持つ階層も、接続が無ければ削除する。"""
        root = self.make(text="root")
        first = cmds.spaceLocator(name=self.name("first"))[0]
        first = cmds.parent(first, root)[0]
        second = self.make(text="second", parent=root)
        shape = cmds.listRelatives(first, shapes=True, fullPath=True)[0]
        cmds.parent(shape, second, shape=True, add=True)
        self.assertEqual(len(cmds.listRelatives(shape, allParents=True)), 2)
        node = mlib.getNode(root)
        node.delete(skipConnected=True)
        self.assertFalse(cmds.objExists(root))


class InstancedPlugOwnerTest(_Case):
    """インスタンスのShapeのアトリビュートを、transformの名前で指したときの持ち主。"""

    def test_transform_name_with_child_before_shape(self):
        """Shapeより前に別の子を持つtransformの名前でも、そのtransformの下のShapeを持ち主にする。"""
        box = cmds.polyCube(name=self.name("box"), constructionHistory=False)[0]
        kid = self.make(text="kid", parent=box)
        cmds.reorder(kid, front=True)
        self.assertEqual(cmds.listRelatives(box, children=True)[0], kid)
        cmds.instance(box, name=self.name("copy"))
        long_box = cmds.ls(box, long=True)[0]
        plug = mlib.getPlug(long_box + ".castsShadows")
        shape = cmds.listRelatives(long_box, shapes=True, fullPath=True)[0]
        self.assertEqual(plug.getNode().getName(full=True), shape)
        self.assertEqual(plug.get(), cmds.getAttr(shape + ".castsShadows"))
        self.assertTrue(om2.MFnDagNode(plug.getNode().mnode()).isInstanced())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
