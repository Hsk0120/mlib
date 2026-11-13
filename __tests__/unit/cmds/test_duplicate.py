"""Node.duplicate が複製した自身を同じ種類のラッパーで返すことを確かめる。

各種ノード(transform・joint・DGノード・shape)の戻り型、名前・suffix・Mayaフラグの受け渡し、
Undo 1 回で戻ること、無効なノード・不正なフラグの例外を確かめる。

あわせて次も確かめる。

- リグ構築の補助APIの約束を固定する。
- mlib.cmds の7入口(getNode・getPlug・createNode・ls・delete・duplicate・select)の仕様テスト(担当D)。
"""

import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.components import Vertex, Vertices
from mlib.nodes import BlendShape, IkHandle, Joint, Joints, Node, Nodes, SkinClusters
from mlib.plugs import Plug, Plugs
from support.namespaceCase import NamespaceCase


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecRigBuilders_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        # Maya が現在の名前空間へ作るノード(エフェクター・自動カーブ・名前空間を外した鏡映)も片付ける。
        self.existing = set(cmds.ls(long=True))

    def tearDown(self):
        for name in cmds.ls(long=True):
            if (name not in self.existing and cmds.objExists(name) and not cmds.lockNode(name, query=True)[0]
                    and not cmds.objectType(name, isAType="ikSolver")):
                cmds.delete(name)
        super().tearDown()

    def chain(self, *items):
        """(名前, 位置) の並びで、選択を使わずに親子の joint を作る。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(text), position=position) for text, position in items]
        cmds.select(clear=True)
        return [cmds.ls(name, long=True)[0] for name in names]

    def sphere(self, text):
        """構築履歴の無い polySphere の transform を作る。"""
        return cmds.polySphere(name=self.name(text), constructionHistory=False)[0]

    def aliases(self, blend):
        """aliasAttr の照会から、weight のエイリアスを論理番号順に返す。"""
        items = cmds.aliasAttr(str(blend), query=True) or []
        pairs = [(int(target[target.index("[") + 1:-1]), alias)
                 for alias, target in zip(items[::2], items[1::2]) if target.startswith("weight[")]
        return [alias for _index, alias in sorted(pairs)]

    def leaf(self, name):
        """完全パス・名前空間を除いた名前を返す。"""
        return name.split("|")[-1].split(":")[-1]


class DuplicateSuffixTest(_SpecCase):
    """mlib.duplicate(suffix=...) は複製の起点と全 DAG 子孫へ接尾辞を付ける。"""

    def setUp(self):
        super().setUp()
        self.joints = self.chain(("L_hip", (0, 5, 0)), ("L_knee", (0, 3, 1)), ("L_ankle", (0, 1, 0)))
        self.cube = cmds.polyCube(name=self.name("box"), constructionHistory=False)[0]
        cmds.parent(self.cube, self.joints[1])

    def names(self, root):
        """root と DAG 子孫の名前(名前空間付き)を並べ替えて返す。"""
        names = [root] + (cmds.listRelatives(root, allDescendents=True, fullPath=True) or [])
        return sorted(name.split("|")[-1] for name in cmds.ls(names, long=True))

    def leaves(self, root):
        """root と DAG 子孫の、名前空間を除いた名前を並べ替えて返す。"""
        return sorted(self.leaf(name) for name in self.names(root))

    def test_suffix_renames_chain(self):
        """L_hip|L_knee|... が L_hip_FK|L_knee_FK|... になり、shape にも付く。

        名前空間は Maya が複製を置いた名前空間(現在の名前空間)のまま。
        """
        copy = mlib.duplicate(self.joints[0], suffix="_FK")
        self.assertIs(type(copy), Joint)
        self.assertEqual(copy.getName(), "L_hip_FK")
        self.assertEqual(self.names(copy.getFullName()),
                         sorted(("L_hip_FK", "L_knee_FK", "L_ankle_FK", "box_FK", "boxShape_FK")))
        cmds.namespace(set=self.ns)
        try:
            copy = mlib.duplicate(self.joints[0], suffix="_IK")
        finally:
            cmds.namespace(set=":")
        self.assertEqual(self.names(copy.getFullName()), sorted(self.name(text) for text in (
            "L_hip_IK", "L_knee_IK", "L_ankle_IK", "box_IK", "boxShape_IK")))
        self.assertEqual(cmds.ls(self.joints[0], long=True), [self.joints[0]])
        self.assertEqual(self.names(self.joints[0]), sorted(self.name(text) for text in (
            "L_hip", "L_knee", "L_ankle", "box", "boxShape")))

    def test_name_keeps_root(self):
        """name を指定すると起点は name のまま、子孫だけに接尾辞を付ける。"""
        copy = mlib.duplicate(self.joints[0], name=self.name("hipRoot"), suffix="_IK")
        self.assertEqual(copy.getName(), self.name("hipRoot"))
        self.assertEqual(self.leaves(copy.getFullName()),
                         sorted(("hipRoot", "L_knee_IK", "L_ankle_IK", "box_IK", "boxShape_IK")))

    def test_parent_only_and_instance_leaf(self):
        """parentOnly は起点だけ、instanceLeaf の共有 shape は改名しない。"""
        copy = mlib.duplicate(self.joints[0], parentOnly=True, suffix="_P")
        self.assertEqual(self.leaves(copy.getFullName()), ["L_hip_P"])
        copy = mlib.duplicate(self.cube, instanceLeaf=True, suffix="_I")
        self.assertEqual(self.leaf(copy.getName()), "box_I")
        self.assertTrue(cmds.objExists(self.name("boxShape")))
        self.assertFalse(cmds.objExists(self.name("boxShape_I")))

    def test_without_suffix_unchanged(self):
        """suffix を省略すると従来どおり Maya の自動命名。"""
        copy = mlib.duplicate(self.joints[0])
        self.assertEqual(self.leaves(copy.getFullName()), sorted(("L_hip", "L_knee", "L_ankle", "box", "boxShape")))

    def test_undo_once(self):
        """複製と改名が Undo 1回で戻る。"""
        self.flushUndo()
        mlib.duplicate(self.joints[0], suffix="_FK")
        self.assertUndoesInOneStep(lambda: self.assertEqual(cmds.ls("*_FK"), []),
                                   lambda: self.assertEqual(len(cmds.ls("*_FK")), 5))

    def test_errors(self):
        """不正な suffix・renameChildren との併用は複製前に拒否する。"""
        before = cmds.ls(type="joint")
        for error, flags in ((TypeError, dict(suffix=1)), (ValueError, dict(suffix="")),
                             (ValueError, dict(suffix="a b")), (ValueError, dict(suffix="_FK", renameChildren=True)),
                             (ValueError, dict(suffix="_FK", rc=True))):
            with self.subTest(flags=flags):
                with self.assertRaises(error):
                    mlib.duplicate(self.joints[0], **flags)
        self.assertEqual(cmds.ls(type="joint"), before)


class _CmdsCase(unittest.TestCase):
    """一時名前空間・選択・Undo設定の保存と復元を共通にする。"""

    def setUp(self):
        """一時名前空間を作り、選択とUndo設定を保存する。"""
        self.undo_state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(stateWithoutFlush=True)
        self.selection = cmds.ls(selection=True, long=True)
        self.ns = "mlibSpecDCmds_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)

    def tearDown(self):
        """一時名前空間を中身ごと削除し、選択とUndo設定を戻す。"""
        cmds.select(clear=True)
        if cmds.namespace(exists=self.ns):
            for node in cmds.ls(self.ns + ":*", long=True) or []:
                if cmds.objExists(node) and cmds.lockNode(node, query=True, lock=True)[0]:
                    cmds.lockNode(node, lock=False)
            cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        existing = [name for name in self.selection if cmds.objExists(name)]
        if existing:
            cmds.select(existing, replace=True)
        cmds.undoInfo(state=self.undo_state)

    def name(self, leaf):
        """一時名前空間内の名前を返す。"""
        return self.ns + ":" + leaf

    def transforms(self):
        """一時名前空間内のtransformの数を返す。"""
        return len(cmds.ls(self.ns + ":*", type="transform") or [])


class DuplicateSpecTest(_CmdsCase):
    """duplicateのフラグ・戻り値・Undoを固定する。"""

    def test_result_and_flags(self):
        """複製結果の先頭をラッパーで返し、name/n・parentOnly/poをMayaへ渡す。"""
        parent = cmds.createNode("transform", name=self.name("src"))
        cmds.createNode("transform", name=self.name("srcChild"), parent=parent)
        copied = mlib.duplicate(parent, name=self.name("copy"))
        self.assertIsInstance(copied, Node)
        self.assertEqual(copied.getName(), self.name("copy"))
        self.assertEqual(len(cmds.listRelatives(copied.getFullName(), children=True) or []), 1)
        only = mlib.duplicate(mlib.getNode(parent), n=self.name("only"), po=True)
        self.assertIsNone(cmds.listRelatives(only.getFullName(), children=True))
        joint = cmds.createNode("joint", name=self.name("joint"))
        self.assertEqual(type(mlib.duplicate(joint)).__name__, "Joint")

    def test_conflicts_and_undo(self):
        """長短名の同時指定はTypeErrorで複製せず、通常の複製は1回のUndoで戻る。"""
        node = cmds.createNode("transform", name=self.name("src"))
        before = self.transforms()
        for kwargs in (dict(name="a", n="b"), dict(parentOnly=True, po=True), dict(fullPath=True, f=True),
                       dict(returnRootsOnly=True, rr=True), dict(inputConnections=True, ic=True)):
            with self.assertRaises(TypeError, msg=repr(kwargs)):
                mlib.duplicate(node, **kwargs)
        self.assertEqual(self.transforms(), before)
        with self.assertRaises(ValueError):
            mlib.duplicate("")
        mlib.duplicate(node, name=self.name("copy"))
        cmds.undo()
        self.assertFalse(cmds.objExists(self.name("copy")))


def _short(node):
    """名前空間とDAGパスを除いたノード名を返す。"""
    return node.getNodeName().rpartition(":")[2]


class NodeDuplicateTest(NamespaceCase):
    """Node.duplicate の戻り型・引数・Undo・例外。"""

    PREFIX = "mlibNodeDuplicate_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        # 複製はカレントの名前空間に作られるため、テストの名前空間へ切り替えて後始末の対象にする。
        self.current_namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=":" + self.ns)
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.ns + ":root", position=(0, 0, 0))
        self.tip = cmds.joint(name=self.ns + ":tip", position=(0, 1, 0))
        cmds.select(clear=True)
        self.cube = cmds.polyCube(name=self.ns + ":cube")[0]

    def tearDown(self):
        cmds.namespace(setNamespace=self.current_namespace)
        super().tearDown()

    def test_returns_same_wrapper_type(self):
        cases = (
            ("transform", mlib.createNode("transform", name=self.ns + ":xform"), "transform"),
            ("joint", mlib.getNode(self.root), "joint"),
            ("dg", mlib.createNode("multiplyDivide", name=self.ns + ":md"), "multiplyDivide"),
            ("locator transform", mlib.createLocator(name=self.ns + ":loc").getParent(), "transform"),
        )
        for label, node, node_type in cases:
            with self.subTest(label):
                copied = node.duplicate()
                self.assertIs(type(copied), type(node))
                self.assertEqual(copied.getType(), node_type)
                self.assertNotEqual(copied.getFullName(), node.getFullName())
                self.assertTrue(cmds.objExists(copied.getFullName()))

    def test_shape_returns_duplicated_shape(self):
        cmds.cluster(self.cube)
        shapes = cmds.listRelatives(self.cube, shapes=True, fullPath=True)
        for index, shape_name in enumerate(shapes):
            with self.subTest(shape_name):
                shape = mlib.getNode(shape_name)
                copied = shape.duplicate()
                self.assertIs(type(copied), type(shape))
                self.assertNotEqual(copied.getFullName(), shape.getFullName())
                parent = cmds.listRelatives(copied.getFullName(), parent=True, fullPath=True)[0]
                self.assertNotEqual(parent, cmds.ls(self.cube, long=True)[0])
                children = cmds.listRelatives(parent, shapes=True, fullPath=True)
                self.assertEqual(children[index], copied.getFullName())

    def test_name_suffix_and_flags(self):
        root = mlib.getNode(self.root)
        named = root.duplicate(self.ns + ":copy")
        self.assertEqual(_short(named), "copy")
        suffixed = root.duplicate(suffix="_FK")
        self.assertEqual(_short(suffixed), "root_FK")
        self.assertEqual([_short(child) for child in suffixed.getChildren()], ["tip_FK"])
        parent_only = root.duplicate(parentOnly=True)
        self.assertEqual(parent_only.getChildren(), [])
        short = root.duplicate(po=True)
        self.assertEqual(short.getChildren(), [])

    def test_undo_once(self):
        node = mlib.getNode(self.root)
        before = set(cmds.ls(long=True))
        self.flushUndo()
        copied = node.duplicate(suffix="_copy")
        self.assertIn(copied.getFullName(), set(cmds.ls(long=True)) - before)
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)

    def test_invalid_inputs(self):
        node = mlib.createNode("transform", name=self.ns + ":gone")
        cmds.delete(node.getFullName())
        with self.assertRaisesRegex(RuntimeError, "Cannot duplicate an invalid"):
            node.duplicate()
        root = mlib.getNode(self.root)
        before = set(cmds.ls(long=True))
        with self.assertRaises(TypeError):
            root.duplicate(parentOnly=True, po=True)
        with self.assertRaises(TypeError):
            root.duplicate(suffix=1)
        with self.assertRaises(ValueError):
            root.duplicate(suffix="a b")
        self.assertEqual(set(cmds.ls(long=True)), before)


if __name__ == "__main__":
    unittest.main()
