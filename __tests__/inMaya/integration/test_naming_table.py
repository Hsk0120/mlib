"""mlib の名前方針を対応表データで固定する。

旧名(別名を含む)が単数・複数形クラスのどこにも残らないこと、新名が単数に定義されること、
複数形クラスが単数への一括転送を持たないこと、mlib 本体のソースに旧名の def が無いことを確かめる。
lowerCamelCase へ改名した公開引数に旧名が残らないことも確かめる。
マルチアトリビュートの呼び名へ揃えた ``MultiPlug``・``isMulti``・``getMulti`` について、
旧名(``ArrayPlug``・``isArray``・``isElement``・``getArray``)が公開APIに残らないことも確かめる。
フラグ・引数へまとめて無くした Plug のメソッド(``MERGED_PLUG``)が、Plug のどのクラスにも残らないことも確かめる。
フラグ・引数へまとめて無くしたノードのメソッド(``MERGED_NODE``)が、持ち主のクラスと複数形に残らないことも確かめる。
個々の新しい約束(引数・戻り値・Undo・fast)は test_spec_node_*/dag_*/transform_*/plug_* が受け持つ。
"""

import inspect
import re
import unittest
from pathlib import Path

import mlib

mlib.reload()
import functools
import operator

from mlib.nodes import (
    Constraint,
    DagNode,
    DagPose,
    GeometryFilter,
    IkHandle,
    Joint,
    Joints,
    Node,
    Nodes,
    ObjectSet,
    ShadingEngine,
    Shape,
    SkinCluster,
    Transform,
)
from mlib.plugs import CompoundPlug, MultiPlug, Plug

#: 廃止した名前。単数クラスと、その複数形の双方に残らない。
REMOVED = {
    Node: ("create", "getPath", "isChildOf", "getAttrCount", "sameInstance", "getAssignedObjects", "getMaterials", "getExtraAttrs"),
    DagNode: ("dagFn", "getParentPath", "getFullPath", "getPartialPath", "collectSkinClusters"),
    Transform: ("transformFn", "reset", "resetPivot", "freeze", "getEuler", "getJointOrientQuaternion", "getShearing", "setShearing"),
    Joint: ("isJoint",),
    Plug: (
        "getDataType",
        "getPlugName",
        "getEnumFieldName",
        "getNextAvailable",
        "isArray",
        "isElement",
        "getArray",
        "getAttrName",
        "lock",
        "unlock",
        "mute",
        "unmute",
    ),
    MultiPlug: ("getNextAvailableIndex", "isArray", "isElement", "getArray"),
    CompoundPlug: ("isArray", "isElement", "getArray"),
}

#: マルチアトリビュートの呼び名へ改名したPlugの判定・取得(旧名, 新名)。
RENAMED_MULTI = (("isArray", "isMulti"), ("isElement", "isMulti"), ("getArray", "getMulti"))

#: フラグ・引数へまとめて無くした Plug のメソッド(無くした名前の並び, まとめた先)。
#: show・hide・getShortName のように別のクラスが持つ名前もあるので、REMOVED(複数形とソース全体を見る)とは分ける。
MERGED_PLUG = (
    (("getMin", "getMax", "hasMin", "hasMax", "getSoftMin", "getSoftMax", "hasSoftMin", "hasSoftMax", "getSoftRange"), "getRange"),
    (("setMin", "setMax", "setSoftMin", "setSoftMax", "setSoftRange"), "setRange"),
    (("isSource", "isDestination", "isConnectedTo"), "isConnected"),
    (("setKeyable", "setChannelBox", "show", "hide"), "setFlags"),
    (("getFullName",), "getName"),
    (("isKeyable", "isChannelBox", "isHidden"), "getFlags"),
    (("disconnectInput",), "disconnectAll"),
    (("getConnectedIndices",), "getIndices"),
    (("getElementByPhysicalIndex", "getElements"), "getElement"),
    (("isMultiElement",), "isMulti"),
    (("isChild",), "isCompound"),
    (("getAllParents",), "getParent"),
    (("getAnimCurveType",), "getAnimCurve"),
    (("getEnumName", "getEnumValue"), "getEnumNames"),
    (("isExisting",), "isValid"),
    (("getSource", "getDestinations"), "getConnections"),
    (("getLongName", "getShortName", "getNiceName"), "getAttributeName"),
)

#: フラグ・引数へまとめて無くしたノードのメソッド(持ち主, 無くした名前の並び, まとめた先, まとめた先のキーワード専用引数)。
#: 派生クラスが同じ名前の別のメソッドを持つもの(Joint.removeInfluence・SkinCluster.getWeights)があるので、持ち主ごとに確かめる。
MERGED_NODE = (
    (Node, ("getNodeName",), "getName", ("short", "removeNamespace")),
    (Node, ("isParentOf",), "isAncestorOf", ("direct",)),
    (Node, ("getAnimatablePlugs",), "getPlugs", ("writable", "animatable")),
    (Node, ("setDgTimerEnabled",), "setDgTimer", ()),
    (Node, ("getDgCallbacks", "getDgTimerState"), "getDgTimer", ("kind", "timerType")),
    (DagNode, ("show", "hide"), "setVisibility", ("fast", "check")),
    (DagNode, ("getParents",), "getParent", ("instances", "indirect")),
    (DagNode, ("getShapes",), "getShape", ("all",)),
    (DagNode, ("getBoundingBoxCorners",), "getBoundingBox", ("includeInvisible", "corners")),
    (DagNode, ("setOutlinerOrder",), "reorder", ("index", "front", "back", "relative")),
    (DagNode, ("getActiveColor", "getDormantColor", "getHiliteColor", "getDrawOverrideColor"), "getDrawColor", ("kind",)),
    (DagNode, ("getOverrideColor", "getOutlinerColor"), "getColor", ("outliner", "toShape")),
    (DagNode, ("setOverrideColor", "setOutlinerColor"), "setColor", ("outliner", "toShape", "fast", "check")),
    (Transform, ("translateBy",), "setTranslation", ("relative", "safe", "get", "fast", "check")),
    (Transform, ("rotateBy",), "setRotate", ("relative", "safe", "get", "unit", "fast", "check")),
    (Transform, ("scaleBy",), "setScale", ("relative", "safe", "get", "fast", "check")),
    (Transform, ("shearBy",), "setShear", ("relative", "safe", "get", "fast", "check")),
    (Transform, ("centerPivotsOnComponents",), "centerPivot", ("fast", "check")),
    (Transform, ("getPivotTranslation",), "getPivot", ("kind", "translation")),
    (Transform, ("setPivotTranslation",), "setPivot", ("kind", "translation", "preserve", "fast", "check")),
    (Joint, ("jointOrientToRotate",), "freezeRotate", ("toRotate",)),
    (Joint, ("getIkHandles",), "getConnections", ()),
    (SkinCluster, ("removeInfluence", "removeUnusedInfluences"), "removeInfluences", ("unused", "transferToParent", "requireAncestor", "repair")),
    (SkinCluster, ("forceNormalizeWeights",), "normalizeWeights", ("force", "fast")),
    (SkinCluster, ("getLockedInfluences", "getUnusedInfluences"), "getInfluences", ("locked", "unused")),
    (SkinCluster, ("isMaintainingMaxInfluences",), "getMaxInfluences", ("maintain",)),
    (SkinCluster, ("getSkinningMethod", "getNormalizeMode"), "getMode", ()),
    (SkinCluster, ("setSkinningMethod", "setNormalizeMode"), "setMode", ()),
    (SkinCluster, ("getVertexWeights",), "getWeights", ("vertices", "vertex", "nonzero", "rows", "geometryIndex")),
    (SkinCluster, ("setVertexWeights",), "setWeights", ("vertices", "vertex", "normalize", "broadcast", "rows", "fast", "check", "geometryIndex")),
    (GeometryFilter, ("getInputGeometry", "getInputGeometryAtIndex", "getGeometryAtIndex"), "getGeometry", ("input", "geometryIndex")),
    (GeometryFilter, ("getGeometryIndex",), "getGeometryIndices", ()),
    (ObjectSet, ("addExclusiveMembers",), "addMembers", ("forceElement",)),
    (ObjectSet, ("removeAllMembers",), "removeMembers", ("all",)),
    (ObjectSet, ("getUnion", "getIntersection", "getDifference"), "combine", ()),
    (ObjectSet, ("getMemberDagNodes",), "getMembers", ("flatten", "dagOnly", "shadingOnly")),
    (ShadingEngine, ("getShaderPlug",), "getShader", ("asPlug",)),
    (Constraint, ("getWeight",), "getWeights", ()),
    (Constraint, ("getWeightAliases",), "getWeightPlugs", ("aliases",)),
    (DagPose, ("getMemberIndex",), "getMemberIndices", ()),
    (DagPose, ("isAtPose",), "getNotAtPose", ()),
    (IkHandle, ("getEndJoint",), "getJoints", ("tipOnly",)),
)

#: フラグ・引数へまとめて無くした複数形のメソッド(複数形, 無くした名前の並び, まとめた先, まとめた先のキーワード専用引数)。
MERGED_PLURAL = (
    (Nodes, ("show", "hide"), "setVisibility", ("fast", "check")),
    (Nodes, ("getOverrideColor", "getOutlinerColor"), "getColor", ("outliner", "toShape")),
    (Nodes, ("setOverrideColor", "setOutlinerColor"), "setColor", ("outliner", "toShape", "fast", "check")),
    (Nodes, ("setOverrideColors", "setOutlinerColors"), "setColors", ("outliner", "toShape", "fast", "check")),
    (Nodes, ("getFullNames",), "getNames", ("full",)),
    (Node, ("getFullName",), "getName", ("full", "short", "removeNamespace")),
)

#: 単数クラスと対応する複数形クラス。
PLURALS = {Node: Nodes, Joint: Joints}

#: 統合後に定義されている名前。単数の def を確かめる。
REQUIRED = {
    Node: ("mfn", "hasFn", "setLocked", "getType", "isType", "resetAttrs", "getPlugs", "getConnections", "isAncestorOf", "getName", "sameNode"),
    DagNode: (
        "mfn",
        "getRoot",
        "getSiblings",
        "getBoundingBox",
        "isIntermediateObject",
        "getShape",
        "setVisibility",
        "getSkinClusters",
        "getParent",
        "getChildren",
        "mpath",
    ),
    Transform: ("mfn", "setPivot", "getPivot", "makeIdentity", "setParent", "getRotate", "getShear", "setShear", "getQuaternion", "getMatrix", "setMatrix"),
    Joint: ("getJointOrient", "freezeRotate", "getSkinClusters"),
}

#: 複数形が独自の集約として持つ名前(単数への転送ではない)。Nodes.getSkinClusters は重複を除いた SkinClusters を返す(Joints は継承する)。
PLURAL_OWN = ("getSkinClusters",)

#: Joints だけが持つ、REMOVED_PLURAL と同じ名前(influence解除付きの一括削除)。
JOINTS_OWN = ("delete",)

#: 複数形が明示的に持つ一括の書込み(Nodes._forward で各要素へ適用する)。
PLURAL_BULK = ("resetAttrs", "setColor", "setColors", "setVisibility", "setParent")

#: 複数形が持たない一括転送と、その基盤の名前(callEach・getNames は持つ)。
REMOVED_PLURAL = ("delete", "removeInfluences", "freezeRotate", "_bulk_entries", "_bulk_methods", "_bulk_returns", "_dispatch_shared", "_calculating_setters")


class RemovedNamesTest(unittest.TestCase):
    """旧名は単数・複数形のどちらにも無い(別名も残さない)。"""

    def test_singular_classes_have_no_removed_names(self):
        for cls, names in REMOVED.items():
            for name in names:
                with self.subTest(cls=cls.__name__, name=name):
                    self.assertFalse(hasattr(cls, name), f"{cls.__name__}.{name} remains")

    def test_plural_classes_have_no_removed_names(self):
        for cls, plural in PLURALS.items():
            for base, names in REMOVED.items():
                if not issubclass(cls, base):
                    continue
                for name in names:
                    with self.subTest(cls=plural.__name__, name=name):
                        self.assertFalse(hasattr(plural, name), f"{plural.__name__}.{name} remains")

    def test_multi_plug_owns_next_available(self):
        """getNextAvailable は MultiPlug だけに定義され、Plug・CompoundPlug には無い。"""
        self.assertIn("getNextAvailable", MultiPlug.__dict__)
        self.assertFalse(hasattr(Plug, "getNextAvailable"))
        self.assertFalse(hasattr(CompoundPlug, "getNextAvailable"))
        self.assertFalse(hasattr(MultiPlug, "getNextAvailableIndex"))
        parameters = inspect.signature(MultiPlug.getNextAvailable).parameters
        self.assertIn("vacant", parameters)
        self.assertEqual(parameters["vacant"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIs(parameters["vacant"].default, False)
        self.assertNotIn("asPlug", parameters)

    def test_shape_does_not_override_get_parent(self):
        """Shape.getParent の override(super 転送のみ)は削除し、DagNode の実装を継承する。"""
        self.assertNotIn("getParent", Shape.__dict__)
        self.assertIs(Shape.getParent, DagNode.getParent)

    def test_plug_operators_exist(self):
        """接続演算子(D3-5)は Plug に定義される。"""
        for name in ("__rshift__", "__lshift__", "__floordiv__"):
            with self.subTest(name=name):
                self.assertIn(name, Plug.__dict__)
                self.assertTrue(callable(getattr(Plug, name)))

    def test_lock_and_mute_use_set_methods(self):
        """lock/unlock/mute/unmuteは無く、setLocked/setMutedだけを持つ。Channel Boxの表示はsetFlags/getFlagsで扱う。"""
        for name in ("lock", "unlock", "mute", "unmute", "getAttrName"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(Plug, name))
        for name in ("setLocked", "setMuted", "isLocked", "setFlags", "getFlags"):
            with self.subTest(name=name):
                self.assertIn(name, Plug.__dict__)
        self.assertIn("fast", inspect.signature(Plug.setLocked).parameters)

    def test_merged_plug_methods_are_removed(self):
        """フラグ・引数へまとめたメソッドはどのPlugクラスにも無く、まとめた先はPlugかMultiPlugに定義される。"""
        for names, target in MERGED_PLUG:
            with self.subTest(target=target):
                self.assertTrue(target in Plug.__dict__ or target in MultiPlug.__dict__)
            for name in names:
                for owner in mlib.plugs.__all__:
                    with self.subTest(cls=owner, name=name):
                        self.assertFalse(hasattr(getattr(mlib.plugs, owner), name), f"{owner}.{name} remains")

    def test_merged_node_methods_are_removed(self):
        """フラグ・引数へまとめたノードのメソッドは持ち主のクラスに無く、まとめた先が定義され、足した引数はキーワード専用。"""
        for owner, names, target, keywords in MERGED_NODE + MERGED_PLURAL:
            with self.subTest(cls=owner.__name__, target=target):
                self.assertTrue(callable(getattr(owner, target)))
                parameters = inspect.signature(getattr(owner, target)).parameters
                for keyword in keywords:
                    with self.subTest(keyword=keyword):
                        self.assertEqual(parameters[keyword].kind, inspect.Parameter.KEYWORD_ONLY)
            for name in names:
                with self.subTest(cls=owner.__name__, name=name):
                    self.assertFalse(hasattr(owner, name), f"{owner.__name__}.{name} remains")
        # 複数形は、単数のまとめた名前を明示メソッドとして持つか、各要素へ転送する。無くした名前は転送もしない。
        for name in ("show", "hide", "getFullName", "getFullNames", "setOverrideColors", "setOutlinerColors"):
            for plural in (Nodes, Joints):
                with self.subTest(cls=plural.__name__, name=name):
                    self.assertFalse(hasattr(plural, name), f"{plural.__name__}.{name} remains")

    def test_merged_node_defaults(self):
        """まとめた先の引数の既定は、まとめる前の動き(フラグなし)のまま。

        指定の有無で動きが変わる引数(setPivot の preserve、removeInfluences の transferToParent・requireAncestor、
        setWeights の normalize)は既定が番兵なので、ここでは見ない(それぞれのテストが動きで確かめる)。
        """
        expected = (
            (Node.getName, {"short": False, "removeNamespace": False}),
            (Node.isAncestorOf, {"direct": False}),
            (DagNode.getParent, {"step": 1, "instances": False, "indirect": False}),
            (DagNode.getShape, {"index": 0, "intermediates": False, "all": False}),
            (DagNode.getBoundingBox, {"includeInvisible": False, "corners": False}),
            (DagNode.getDrawColor, {"kind": "dormant"}),
            (DagNode.getColor, {"outliner": False, "toShape": False}),
            (DagNode.setColor, {"outliner": False, "toShape": False, "fast": False, "check": False}),
            (Transform.setTranslation, {"relative": False}),
            (Transform.setRotate, {"relative": False}),
            (Transform.setScale, {"relative": False}),
            (Transform.setShear, {"relative": False}),
            (Transform.centerPivot, {"components": None, "fast": False, "check": False}),
            (Transform.getPivot, {"kind": "rotate", "translation": False}),
            (Transform.setPivot, {"kind": "rotate", "translation": False}),
            (Joint.freezeRotate, {"toRotate": False}),
            (SkinCluster.removeInfluences, {"joints": None, "unused": False, "repair": False}),
            (SkinCluster.normalizeWeights, {"ndigits": None, "force": False, "fast": False}),
            (SkinCluster.getInfluences, {"locked": None, "unused": None}),
            (SkinCluster.getMaxInfluences, {"maintain": False}),
            (SkinCluster.getMode, {"kind": "skinning"}),
            (SkinCluster.setMode, {"kind": "skinning"}),
            (SkinCluster.getWeights, {"joints": None, "vertices": None, "vertex": None}),
            (SkinCluster.setWeights, {"weights": None, "vertices": None, "vertex": None}),
            (GeometryFilter.getGeometry, {"input": False, "geometryIndex": None}),
            (GeometryFilter.getGeometryIndices, {"geometry": None}),
            (ObjectSet.getMembers, {"flatten": False, "dagOnly": False, "shadingOnly": False}),
            (ObjectSet.addMembers, {"forceElement": False}),
            (ObjectSet.removeMembers, {"all": False}),
            (ObjectSet.combine, {"mode": "union"}),
            (ShadingEngine.getShader, {"kind": "surface", "asPlug": False}),
            (Constraint.getWeightPlugs, {"aliases": False}),
            (DagPose.getMemberIndices, {"member": None}),
            (IkHandle.getJoints, {"includeTip": False, "tipOnly": False}),
            (Nodes.getNames, {"full": False}),
            (Nodes.setColors, {"outliner": False, "toShape": False, "fast": False, "check": False}),
        )
        for function, defaults in expected:
            parameters = inspect.signature(function).parameters
            for name, default in defaults.items():
                with self.subTest(function=function.__qualname__, name=name):
                    self.assertEqual(parameters[name].default, default)
                    self.assertIs(type(parameters[name].default), type(default))

    def test_merged_plug_arguments(self):
        """まとめた先の引数は、位置で渡す値(範囲・相手・番号・名前の種類)を除いてキーワード専用。"""
        expected = {
            "getRange": ("soft", "unit", "timeUnit", "uiUnits"),
            "setRange": ("soft", "unit", "timeUnit"),
            "isConnected": ("source", "destination"),
            "setFlags": ("locked", "keyable", "channelBox", "children", "leaves", "fast"),
            "disconnectAll": ("source", "destination", "fast"),
            "isMulti": ("element",),
            "isCompound": ("child",),
            "getParent": ("all", "includeMulti"),
            "getAnimCurve": ("indirect", "suitableType", "timeInput"),
            "getEnumNames": ("value", "name", "current"),
            "isValid": ("elements",),
            "getConnections": ("input", "output"),
        }
        for method, names in expected.items():
            parameters = inspect.signature(getattr(Plug, method)).parameters
            for name in names:
                with self.subTest(method=method, name=name):
                    self.assertEqual(parameters[name].kind, inspect.Parameter.KEYWORD_ONLY)
        for method, names in (("getIndices", ("connected",)), ("getElement", ("physical",))):
            parameters = inspect.signature(getattr(MultiPlug, method)).parameters
            for name in names:
                with self.subTest(method=method, name=name):
                    self.assertEqual(parameters[name].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(list(inspect.signature(Plug.getFlags).parameters), ["self"])
        self.assertEqual(inspect.signature(Plug.getAttributeName).parameters["kind"].default, "long")

    def test_connections_do_not_skip_conversion_nodes_by_default(self):
        """接続照会のskipConversionNodesは既定False(cmds.listConnectionsと同じ直結)。

        短縮名scnと同時の指定を値に関係なく見分けるため、シグネチャの既定は「指定なし」の番兵でもよい(意味の既定はFalse)。
        """
        for function in (Node.getConnections, Plug.getConnections):
            parameters = inspect.signature(function).parameters
            with self.subTest(function=function.__qualname__):
                default = parameters["skipConversionNodes"].default
                self.assertTrue(default is False or default is mlib.util._UNSET)
                if "scn" in parameters:
                    self.assertIsNot(parameters["scn"].default, True)

    def test_connections_have_no_pcls(self):
        for cls in (Node, Plug):
            with self.subTest(cls=cls.__name__):
                self.assertNotIn("pcls", inspect.signature(cls.getConnections).parameters)


class MultiRenameTest(unittest.TestCase):
    """マルチアトリビュートの改名: ArrayPlug → MultiPlug、isArray/isElement/getArray → isMulti/isMulti(element=True)/getMulti。

    互換の別名・旧モジュールは残さない。
    """

    def test_old_class_is_not_public(self):
        """ArrayPlug は mlib.plugs・mlib のどちらにも無く、__all__ にも無い。"""
        for module in (mlib.plugs, mlib):
            with self.subTest(module=module.__name__):
                self.assertFalse(hasattr(module, "ArrayPlug"))
                self.assertNotIn("ArrayPlug", getattr(module, "__all__", ()))
        self.assertIn("MultiPlug", mlib.plugs.__all__)
        self.assertIs(mlib.MultiPlug, MultiPlug)
        self.assertEqual(MultiPlug.__module__, "mlib.plugs.multiPlug")
        self.assertTrue(issubclass(MultiPlug, Plug))

    def test_old_module_is_removed(self):
        """旧モジュール mlib.plugs.arrayPlug は import できず、ファイルも無い。"""
        root = Path(mlib.__file__).resolve().parent
        self.assertFalse((root / "plugs" / "arrayPlug.py").exists())
        self.assertTrue((root / "plugs" / "multiPlug.py").exists())
        with self.assertRaises(ImportError):
            __import__("mlib.plugs.arrayPlug")

    def test_plug_methods_are_renamed(self):
        """新名は Plug に定義され、旧名はどのPlugクラスにも無い。"""
        for old, new in RENAMED_MULTI:
            with self.subTest(old=old, new=new):
                self.assertIn(new, Plug.__dict__)
                self.assertTrue(callable(getattr(Plug, new)))
                for cls in (Plug, MultiPlug, CompoundPlug):
                    self.assertFalse(hasattr(cls, old), f"{cls.__name__}.{old} remains")
        for name in mlib.plugs.__all__:
            cls = getattr(mlib.plugs, name)
            for old, _new in RENAMED_MULTI:
                with self.subTest(cls=name, old=old):
                    self.assertFalse(hasattr(cls, old), f"{name}.{old} remains")


class RequiredNamesTest(unittest.TestCase):
    """新名は単数に定義され、複数形へ同じ署名で転送される。"""

    def test_singular_classes_define_required_names(self):
        for cls, names in REQUIRED.items():
            for name in names:
                with self.subTest(cls=cls.__name__, name=name):
                    self.assertTrue(callable(getattr(cls, name)), f"{cls.__name__}.{name} missing")

    def test_plural_classes_do_not_forward(self):
        """複数形クラスは、明示した書込み(PLURAL_BULK)以外の転送メソッドを定義しない。

        単数の呼出しは、インスタンスの __getattr__ が各要素へ転送する(test_spec_collection_forwarding で確認)。
        """
        for cls, plural in PLURALS.items():
            for base, names in REQUIRED.items():
                if not issubclass(cls, base):
                    continue
                for name in names:
                    if name in PLURAL_OWN:
                        continue
                    if name in PLURAL_BULK:
                        with self.subTest(cls=plural.__name__, bulk=name):
                            self.assertIn(name, Nodes.__dict__)
                        continue
                    with self.subTest(cls=plural.__name__, name=name):
                        self.assertFalse(hasattr(plural, name), f"{plural.__name__}.{name} remains")
            for name in PLURAL_OWN:
                with self.subTest(cls=plural.__name__, own=name):
                    self.assertIn(name, Nodes.__dict__)
            for name in REMOVED_PLURAL:
                if plural is Joints and name in JOINTS_OWN:
                    continue
                with self.subTest(cls=plural.__name__, name=name):
                    self.assertFalse(hasattr(plural, name), f"{plural.__name__}.{name} remains")
        self.assertFalse(hasattr(mlib.nodes, "DagNodes"))
        self.assertFalse(hasattr(mlib.nodes, "Transforms"))

    def test_moved_dag_queries_live_on_dag_node(self):
        """getRoot・getSiblings・getBoundingBox・isIntermediateObject は DagNode が持ち、Transform は継承する。"""
        for name in ("getRoot", "getSiblings", "getBoundingBox", "isIntermediateObject"):
            with self.subTest(name=name):
                self.assertIn(name, DagNode.__dict__)
                self.assertNotIn(name, Transform.__dict__)

    def test_rotate_accepts_order(self):
        parameters = inspect.signature(Transform.getRotate).parameters
        self.assertIn("order", parameters)
        self.assertEqual(parameters["order"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIsNone(parameters["order"].default)

    def test_set_parent_has_no_short_relative(self):
        """短縮名rは無く、長名relativeだけを持つ。"""
        parameters = inspect.signature(Transform.setParent).parameters
        self.assertIn("relative", parameters)
        self.assertNotIn("r", parameters)

    def test_get_plugs_signature(self):
        parameters = inspect.signature(Node.getPlugs).parameters
        self.assertIn("userDefined", parameters)
        self.assertIn("children", parameters)
        self.assertIs(parameters["userDefined"].default, False)
        self.assertIs(parameters["children"].default, True)

    def test_set_visibility_accepts_fast(self):
        """表示・非表示は setVisibility だけで行い、fast・check はキーワード専用。"""
        for name in ("fast", "check"):
            with self.subTest(name=name):
                parameters = inspect.signature(DagNode.setVisibility).parameters
                self.assertEqual(parameters[name].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_enum_names_accepts_value(self):
        parameters = inspect.signature(Plug.getEnumNames).parameters
        for name in ("value", "name"):
            with self.subTest(name=name):
                self.assertIsNone(parameters[name].default)
        self.assertIs(parameters["current"].default, False)

    def test_ui_units_on_limits(self):
        for name in ("getRange", "getDefault"):
            with self.subTest(name=name):
                parameters = inspect.signature(getattr(Plug, name)).parameters
                self.assertIn("uiUnits", parameters)
                self.assertEqual(parameters["uiUnits"].kind, inspect.Parameter.KEYWORD_ONLY)


class SourceTextTest(unittest.TestCase):
    """mlib の nodes・plugs のソースに旧名の def・集まりクラスの転送文字列が残らない。

    Plugin/Module の getPath()、components の getMaterials() は別クラスの正式名なので対象外(nodes・plugs だけを見る)。
    """

    OLD_NAMES = sorted(
        set(functools.reduce(operator.iadd, (list(names) for names in REMOVED.values()), [])) - {"create", "reset", "lock", "mute", "getNextAvailable"}
    )

    def test_no_old_definitions_in_sources(self):
        root = Path(mlib.__file__).resolve().parent
        pattern = re.compile(r"^\s*def ({})\(|\"({})\":".format("|".join(self.OLD_NAMES), "|".join(self.OLD_NAMES)), re.MULTILINE)
        offenders = []
        for file in list((root / "nodes").glob("*.py")) + list((root / "plugs").glob("*.py")):
            text = file.read_text(encoding="utf-8")
            offenders.extend(f"{file.relative_to(root)}: {match.group(0).strip()}" for match in pattern.finditer(text))
        self.assertEqual(offenders, [])


class RenamedArgumentsTest(unittest.TestCase):
    """lowerCamelCase へ改名した公開引数に旧名が残らない(互換の旧名も受け付けない)。"""

    @staticmethod
    def renamed():
        """(呼出し先の表示名, 呼出し先, 旧引数名, 新引数名)を返す。"""
        from mlib import common
        from mlib.common import references, units
        from mlib.nodes import AnimCurve, DagPose, IkHandle, Mesh, Reference, SkinCluster

        return (
            ("Node.isType", Node.isType, "node_type", "type"),
            ("Node.getName", Node.getName, "remove_namespace", "removeNamespace"),
            ("Transform.getClosestAxisToVector", Transform.getClosestAxisToVector, "ref_vector", "refVector"),
            ("Transform.getClosestAxisToVector", Transform.getClosestAxisToVector, "include_negative", "includeNegative"),
            ("Joint.removeInfluence", Joint.removeInfluence, "transfer_to_parent", "transferToParent"),
            ("Joint.removeInfluence", Joint.removeInfluence, "skin_cluster", "skinCluster"),
            ("Joint.reparentChildren", Joint.reparentChildren, "parent_joint", "parentJoint"),
            ("SkinCluster.__init__", SkinCluster.__init__, "skin_cluster", "node"),
            ("SkinCluster.removeInfluences", SkinCluster.removeInfluences, "transfer_to_parent", "transferToParent"),
            ("SkinCluster.transferWeights", SkinCluster.transferWeights, "source_target_pairs", "sourceTargetPairs"),
            ("DagPose.fromSkinCluster", DagPose.fromSkinCluster, "skin_cluster", "skinCluster"),
            ("IkHandle.getJoints", IkHandle.getJoints, "include_tip", "includeTip"),
            ("Mesh.reorderVertices", Mesh.reorderVertices, "uv_set", "uvSet"),
            ("Mesh.getVertexNormals", Mesh.getVertexNormals, "angle_weighted", "angleWeighted"),
            ("Reference.getFilename", Reference.getFilename, "with_copy_number", "withCopyNumber"),
            ("Keyframe.move", common.Keyframe.move, "time_offset", "timeOffset"),
            ("AnimCurve.scaleKey", AnimCurve.scaleKey, "value_pivot", "valuePivot"),
            ("AnimCurve.scaleKey", AnimCurve.scaleKey, "input_pivot", "inputPivot"),
            ("CompoundPlug.__getitem__", CompoundPlug.__getitem__, "name_or_index", "nameOrIndex"),
            ("DampedSpring.solve", common.DampedSpring.solve, "seconds_per_sample", "secondsPerSample"),
            ("DrivenKey.setKey", common.DrivenKey.setKey, "driver_value", "driverValue"),
            ("Plugin.ensureNodePlugin", common.Plugin.ensureNodePlugin, "node_type", "type"),
            ("PluginPackage.__init__", common.PluginPackage.__init__, "minimum_version", "minimumVersion"),
            ("ScalarGraph.__init__", common.ScalarGraph.__init__, "create_node", "createNode"),
            ("ScriptJob.__init__", common.ScriptJob.__init__, "kill_with_scene", "killWithScene"),
            ("listReferences", references.listReferences, "top_level_only", "topLevelOnly"),
            ("units.convertDistance", units.convertDistance, "to_unit", "toUnit"),
        )

    def test_old_argument_names_are_absent(self):
        for label, function, old, new in self.renamed():
            with self.subTest(function=label, old=old):
                parameters = inspect.signature(function).parameters
                self.assertNotIn(old, parameters)
                self.assertIn(new, parameters)

    def test_old_keyword_raises_type_error(self):
        from mlib.common import DampedSpring, references, units

        calls = (
            ("units.convertDistance", lambda: units.convertDistance(1.0, to_unit="cm")),
            ("DampedSpring.solve", lambda: DampedSpring.solve([0.0, 1.0], seconds_per_sample=1.0 / 24.0)),
            ("listReferences", lambda: references.listReferences(top_level_only=True)),
        )
        for label, call in calls:
            with self.subTest(function=label):
                with self.assertRaises(TypeError):
                    call()


if __name__ == "__main__":
    unittest.main()
