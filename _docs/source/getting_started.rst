mlib入門
========

既存のMayaノードを取得し、アトリビュートや形状の参照を次の操作へ渡す基本を説明します。
個別の引数・返却値・制限は、各APIのリファレンスを参照してください。

実行環境
--------

対象はMaya 2022〜2027のPython 3環境です。Maya付属のPythonを使用します。

.. list-table:: MayaとPythonのバージョン（Windows）
   :header-rows: 1

   * - Maya
     - Python
   * - 2022
     - 3.7
   * - 2023
     - 3.9
   * - 2024
     - 3.10
   * - 2025・2026
     - 3.11
   * - 2027
     - 3.13

``mlib`` フォルダの親フォルダを、Pythonの検索パス（``PYTHONPATH`` または ``sys.path``）へ追加してください。
例えば ``C:/tools/mlib`` に配置した場合は、Script EditorのPythonタブで次を実行します。

.. code-block:: python

   import sys
   sys.path.insert(0, "C:/tools")
   import mlib

以降の例もScript EditorのPythonタブで実行します。作成・編集の例は現在のシーンを変更します。

コマンドは ``import mlib`` の後、``mlib.createNode()`` のように呼び出します。
クラスは ``mlib.nodes``・``mlib.maths`` など、所属するパッケージから取得します。

ノードとアトリビュート
----------------------

.. code-block:: python

   import mlib

   node = mlib.createNode("transform", name="mlibExample")
   plug = node.getPlug("translateX")
   plug.set(10)

   print(node.getName())
   print(plug.get())
   print(mlib.ls(type="transform"))

``createNode`` は作成した型に対応するラッパーを返します。
既存ノードは ``mlib.ls("ノード名やパターン")`` で検索でき、完全DAGパスも指定できます。

:meth:`~mlib.nodes.node.Node.getName` はMayaコマンドへ渡せる最短の一意な名前で、別の階層に同じ短い名前の
ノードがあると ``grp1|ctrl`` のような部分パスになります。新しい名前を組み立てる(接尾辞を付け替える)ときは、
DAGパスを含まない ``getName(short=True)`` (:meth:`~mlib.nodes.node.Node.getName`)を使います。ノード名に ``|`` は使えず、
``createNode(name=...)``・``rename()`` はValueErrorにします(Mayaは黙って別の文字へ置き換えるため)。

.. code-block:: python

   joint = mlib.getNode("L_arm_JNT")
   ctrl = mlib.createNode("transform", name=joint.getName(short=True).replace("_JNT", "_CTRL"))

名前の取得は呼び出すたびにMayaへ問い合わせます。保持したノードを削除した場合や、作成をUndoで
取り消した場合は参照が無効になり、``getName()`` はRuntimeErrorになります
(``isValid()`` で確かめられます。``str(node)`` だけは ``maya.cmds`` へ渡せるよう空文字列を返します)。
Redoで戻したノードを使う場合も、``mlib.getNode`` などで取得し直してください。

mlibが送出した例外は、Script Editorでは利用者がmlibを呼んだ行(``file ... line N``)で表示されます
(mlib内部のフレームを省きます)。内部の位置まで確かめる場合は、環境変数 ``MLIB_FULL_TRACEBACK=1`` を設定します。
存在しないメソッドの名前を使うと、近い名前やmlibでの書き方(``getAttr`` なら ``getPlug(name).get()``)を
案内するAttributeErrorになります。
``ls`` は結果の種類に応じた集まりを返します(ノードは ``Nodes``、``type="joint"``・``type="skinCluster"`` は
それぞれ ``Joints``・``SkinClusters``、アトリビュートは ``Plugs``、コンポーネントは ``Vertices`` 等)。

アトリビュートは :meth:`~mlib.nodes.node.Node.getPlug` で取得した
:class:`~mlib.plugs.plug.Plug` の ``get()``・``set()`` で読み書きします。
``node.tx`` もPlugを返し、``node.tx = 10`` は ``node.getPlug("tx").set(10)`` と同じ書込みになります
(Undoに記録され、角度は度。``node.t = (1, 2, 3)`` も同じです)。Mayaアトリビュートの無い名前への代入は
AttributeErrorになり、ノードへ任意のPython属性は追加できません。

値の単位は距離cmを基本とし、角度の数値は度、時間の数値は現在のUI時間単位のフレーム
(film なら24フレームが1秒)で扱います。
``node.getPlug("rotateX").set(90)`` は90度、``get()`` も度を返します。ラジアンで扱う場合は
``get(unit="rad")``・``set(..., unit="rad")`` を指定します。``rotate`` の ``get()`` が返す
:class:`~mlib.maths.EulerRotate` や :class:`~mlib.maths.Quaternion` などの数学型は、OpenMayaと同じく
内部がラジアンで、値自身が単位を持つため ``set()`` へそのまま渡せます。

.. warning::

   角度の値を取り出して入れ直すときは、数学型のオブジェクトをそのまま渡すか、``asDegrees()`` を使います。
   :class:`~mlib.maths.EulerRotate` は度で表示されますが、``list()``・``tuple()``・添字・``.x`` で取り出す中身はラジアンです。
   一方、3つの数値を ``set`` 系へ渡すと度として扱うので、取り出した中身をそのまま渡すと値がずれます(例外にはなりません)。

   .. code-block:: python

      rotation = node.getRotate()            # EulerRotate(degrees=(10, 20, 30), order='xyz') と表示される
      other.setRotate(rotation)              # 正しい。オブジェクトをそのまま渡す
      other.setRotate(rotation.asDegrees())  # 正しい。度の3つの数値にして渡す
      other.setRotate(tuple(rotation))       # 誤り。中身はラジアンなので、約0.17度・0.35度・0.52度が書かれる

   ``getRotate()``・``getJointOrient()``・``getPreferredAngle()``・``setRotate(..., get=True)`` と、
   ``getPlug("rotate").get()`` が同じ決まりです。``getPlug("rotateX").get()`` のような1つの角度は、度の数値を返します。

``time1.outTime`` のような時間アトリビュートの ``get()`` はフレームを返し、秒で扱う場合は
``get(timeUnit="sec")``・``set(..., timeUnit="sec")`` を指定します。アニメーションカーブのキー
(:meth:`~mlib.nodes.animCurve.AnimCurve.addKey`・``getKeyInputs()``・``getKeyframes().move()`` 等)と
:meth:`~mlib.common.drivenKey.DrivenKey.setKey` の時間も同じ規則で、``timeUnit="sec"`` で秒を指定できます。
角度は ``unit``、時間は ``timeUnit`` と別の引数にしてあるため、animCurveTA のように両方を持つカーブでも
それぞれを指定できます。
Plugを現在のUI単位で扱う場合は ``get(uiUnits=True)``・``set(..., uiUnits=True)`` を使います
(``unit``・``timeUnit`` とは同時に指定できません)。
``maya.cmds`` へ渡すフラグ値はMayaの単位規則に従います。

.. _tool-undo-chunk:

通常の編集はUndo有効時に記録され、上の作成と値変更は別々のUndoになります。
複数の呼出し全体を一回で戻す場合は、外側でまとめます。

.. code-block:: python

   from mlib.decorator import undoChunk

   with undoChunk("editControl"):
       node.setTranslation((1, 2, 3))
       node.getPlug("visibility").set(False)

対応するAPIの ``fast=True`` はUndoなしの直接更新で、Undo設定は変更しません。
``Plug.set(safe=True)`` は対応する書込み失敗数を返し、成功した成分の更新は残します。
Mayaのコマンドのフラグを受け取る入口(``mlib.ls`` 等)は、Mayaと同じ長短の名前を受け付け、長短の一方だけを指定します。
署名の ``_UNSET``・``Ellipsis`` は省略判定用の内部値です。

引数の渡し方
------------

同じ名前の引数は、どのメソッドでも同じ働き・同じ渡し方・同じ既定値です。
名前ごとの決まりと、使えるメソッドの一覧は :doc:`arguments` にまとめています。

位置で渡せるのは、必須の引数・最初の引数(そのメソッドの主な値)・``worldSpace``・``state`` だけです。
既定値つきのほかの引数は、``maya.cmds`` のフラグと同じくキーワードで渡します。数や bool を位置で並べると
読み違えるためで、位置で渡すと ``TypeError`` になります。

.. code-block:: python

   node.setTranslation((1, 2, 3), worldSpace=True)   # 主な値と worldSpace は位置でも渡せる
   node.setTranslation((1, 2, 3), ws=True)           # worldSpace の短縮名(同時には指定できない)
   node.setVisibility(False)                         # オン・オフの値は state(既定 True)
   node.rename("ctl", ignoreShape=True)              # 指定はキーワードで渡す
   node.matchTransform(target, rotation=False)       # matchTransform(target, True, False) とは書けない
   shape = node.getShape(index=1)                    # 番号・種類を選ぶ引数もキーワード
   node.getType(inherited=True)
   curve = mlib.createCurve(points, degree=1)        # 作成関数も、対象のあとはキーワード
   matrix = mlib.Matrix.compose((1, 2, 3), rotate=(0, 0, 90), scale=(2, 2, 2))
   node.setTranslation(5.0, at=1)                    # translateY だけ

値を書き込むメソッドに共通の引数は、次の3つです。どれもキーワード専用で、既定は ``False`` です。

.. list-table::
   :header-rows: 1
   :widths: 12 88

   * - 引数
     - 働き
   * - ``fast``
     - Undoに記録しないOpenMayaの書き込みにします。大量の書き込みを速くしたいときに使います。
   * - ``check``
     - 書き込む前に、値が有限か・書き込めるか(ロック・入力の接続)を確かめ、問題があれば何も書かずに例外にします。
       既定では確かめずに書き、Mayaが拒否したときだけ例外になります。
   * - ``safe``
     - 失敗しても例外にしません。Transformの値では書ける成分だけを書き、``Plug.set`` は失敗した数を返します。

「すでに目的の状態なら何もしない」は ``skipExisting=True``、「接続があるノードは消さない」は ``skipConnected=True`` です
(``safe`` とは別の引数です)。``bool`` の引数に ``0``・``1``・``None`` を渡すと ``TypeError`` になり、
意味が通らない引数の組み合わせも ``TypeError`` になります。取り違えたときに、黙って別の結果にはなりません。

種類を選ぶ引数は名前で分けてあります。対象の種類は ``kind``、取得するものは ``what``、
返すコンポーネントやノードの型は ``type`` です。1つでなく全部が欲しいときは ``all=True`` を指定します。

.. code-block:: python

   mesh.getSetNames(kind="color")                    # 対象の種類(UVセットかカラーセットか)
   curve.getAtParam(0.5, what="tangent")             # 取得するもの
   mesh.getBorder(type="vertex")                     # 返すコンポーネントの種類
   node.getShape(all=True)                           # 全部

名前・選択・型から取得する
--------------------------

``maya.cmds.ls`` と同じように、``mlib.ls`` で名前・選択・型から対象を検索します。
名前の文字列ではなく、対象に対応するNode・Plug・Componentの集まりを返します。
次の例は ``pCube1`` が存在するシーンが前提です。

.. code-block:: python

   import mlib

   nodes = mlib.ls("pCube*")
   selected = mlib.ls(selection=True)
   joints = mlib.ls(type="joint")
   plugs = mlib.ls("pCube1.tx")
   vertices = mlib.ls("pCube1.vtx[0:3]", type="vertex")

   for node in nodes:
       print(node.getName())

戻り値は結果の種類に応じた集まりです。ノードだけなら :class:`~mlib.nodes.node.Nodes`
(``type="joint"`` は :class:`~mlib.nodes.joint.Joints`、``type="skinCluster"`` は
:class:`~mlib.nodes.skinCluster.SkinClusters`)、アトリビュートだけなら :class:`~mlib.plugs.plug.Plugs`、
同じシェイプの同じ種類のコンポーネントだけなら :class:`~mlib.components.vertex.Vertices`・
:class:`~mlib.components.edge.Edges`・:class:`~mlib.components.face.Faces`・:class:`~mlib.components.uv.UVs`・
:class:`~mlib.components.cv.CVs` です。ノードとアトリビュートなど種類が混在する場合だけ list を返します。
ノードの要素がすべてジョイントなら ``Joints``、すべてskinClusterなら ``SkinClusters`` になります
(``getChildren()`` などの一覧を返すメソッドも同じです)。
どの集まりも ``len``・``for``・添字・``bool``・``in``・``+``・``==``・``sort()`` と、Pythonのlistと同じ ``append``・``extend``・
``insert``・``remove``・``pop``・``index``・``count``・``clear``・``reverse`` に対応し、そのまま ``maya.cmds`` へ渡せます。
同じ要素は1つしか持たないので、すでにある要素を ``append`` しても何も変わりません。
1件だけ取り出す場合も、結果があることを確認して ``nodes[0]`` のように取得します。
一致する対象がなければ空の ``Nodes`` になります。検索はノードの作成や選択変更を行いません。
集まりは同じ対象の重複を除き、上の ``vertices`` は4つの頂点を持つ ``Vertices`` です。
``type="vertex"`` は頂点だけを抽出する指定で、ノードやフェースを頂点へ変換する指定ではありません。
取得したノードのアトリビュートは ``node.getPlug("名前")`` でも参照できます。

目的から使い方を探す
--------------------

目的に近い入口から、引数と操作対象を確認してください。

.. list-table::
   :header-rows: 1

   * - 目的
     - 基本の書き方
     - API
   * - 名前や条件で既存対象を探す
     - ``mlib.ls("名前やパターン")``、``mlib.ls(selection=True)``
     - :doc:`autoapi/mlib/cmds/index`
   * - 値・単位・接続を扱う
     - ``node.getPlug("translateX").get()``、``plug.getConnections(input=True)``
     - :class:`~mlib.plugs.plug.Plug`
   * - ノードの型を調べ、Mayaの継承で判定する
     - ``node.getType()``、``node.isType("shape")``、``node.getType(inherited=True)``
     - :meth:`~mlib.nodes.node.Node.isType`、:ref:`dynamic-node-classes`
   * - ユーザー定義アトリビュートを列挙する
     - ``node.getPlugs(userDefined=True)``。名前は ``[p.getAttributeName() for p in plugs]``。
       ``userDefined=True`` は ``cmds.listAttr`` のフラグと併用できません(TypeError)
     - :meth:`~mlib.nodes.node.Node.getPlugs`
   * - 選択した頂点をShapeごとにまとめる
     - ``Selection.capture().filter("vertex").getComponents()``
     - :class:`~mlib.common.selection.Selection`
   * - Meshやカーブの要素を取得する
     - Transformから ``getShape()``、Meshは ``getVertices()``、NurbsCurveは ``getCVs()``
     - :doc:`autoapi/mlib/components/index`
   * - 選択頂点のスキンウェイトを再配分する
     - ``skin.redistributeWeights(mlib.ls(selection=True, type="vertex"))``
     - :meth:`~mlib.nodes.skinCluster.SkinCluster.redistributeWeights`
   * - 選択を保持して復元する
     - ``Selection.capture()`` で保持し、その ``select()`` で選択に反映
     - :class:`~mlib.common.selection.Selection`
   * - プラグインや拡張の状態を調べる
     - ``package.tryLoad()``、``extensions.getDiagnostics()``
     - :class:`~mlib.common.pluginPackage.PluginPackage`、:mod:`mlib.core.extensions`

表中の ``Selection``・``PluginPackage`` は ``from mlib.common import ...`` で取得します。
``package`` はPluginPackageのインスタンスです。
``extensions`` は ``from mlib.core import extensions`` で取得します。
形状・デフォーマの例では、対象Shapeや所属頂点を各APIの条件に合わせて指定してください。

クラスを直接importして使う
--------------------------

クラスは所属するサブパッケージからimportします。``Node``・``Joint``・``Matrix`` などを
``mlib`` 直下へ再公開する入口はありません。

.. code-block:: python

   from mlib.nodes import Node, Joint, Transform
   from mlib.maths import Matrix

   joint = Joint("joint1")  # 既存のJoint
   node = Node("pCube1")    # 実際のnodeTypeに対応するラッパー
   matrix = Matrix()       # 単位マトリクス

具象クラスによる既存取得は、そのクラスまたは派生型を受理します。
``Joint("transform1")`` はTypeError、``Transform("joint1")`` はJointを返します。
名前や型からまとめて検索する場合は ``mlib.ls`` を使います。

ノードの作成は :func:`~mlib.cmds.createNode.createNode`\ (``mlib.createNode``。``cmds.createNode`` 相当)
だけで行います。クラスのconstructorは既存ノードの取得専用で、作成を指示する引数や
クラスメソッドはありません。

.. code-block:: python

   joint = mlib.createNode("joint", name="newJoint")           # Joint
   control = mlib.createNode("transform", name="newControl")   # Transform
   shape = mlib.createNode("mesh", parent=control)             # Mesh。親を省略するとtransformが自動で作られます
   quick = mlib.createNode("multiplyDivide", fast=True)        # OpenMayaで直接作成。Undoに記録されません

戻り値は作成したノードの実際のnodeTypeに対応するラッパーです。指定名が既にある場合は
Mayaの規則で連番化されます。``name``・``parent``・``shared``・``skipSelect`` と
その短縮名は ``cmds.createNode`` と同じ意味で、追加のMayaフラグもそのまま渡せます。
詳細は :func:`~mlib.cmds.createNode.createNode` を参照してください。

複数形(``Joints``・``SkinClusters`` 等)は、重複を除いたノード参照を保持順に持つ容器です。
よく使う書込み(``setAttrFlags``・``resetAttrs``・``setLocked``・``setColor``・``setColors``・``setVisibility``・
``setParent``、``Joints`` では ``setRadius``・``setSegmentScaleCompensate`` も)は
容器から全要素へまとめて適用でき、1回のUndoで戻ります。それ以外の単数のメソッドも、同じ名前で容器から呼べます
(``nodes.getTranslation()`` や ``plugs.get()`` は、各要素の戻り値を並べたlistを返します)。

.. code-block:: python

   joints = mlib.ls(type="joint")
   joints.setRadius(1)
   for joint in joints:
       print(joint.getName(short=True), joint.getDepth())

.. _dynamic-node-classes:

動的ノードクラス
----------------

``mlib.nodes`` に手書きクラスが無いnodeType(``pointLight``・``airField``・``wrap`` など)のノードも、
``mlib.ls``・``mlib.getNode``・``mlib.createNode`` の結果は ``Node`` 固定ではなく、
そのnodeTypeに対応するクラスのインスタンスになります。クラスは最初に要求されたときに
型名の先頭を大文字にした名前(``pointLight`` なら ``PointLight``)で自動生成され、
``mlib.PointLight`` のように ``mlib.nodes.<TypeName>`` でも取得できます。
``getType()`` はラッパーのクラス名ではなくMayaのnodeType名をそのまま返します。

.. code-block:: python

   import mlib

   light = mlib.createNode("pointLight", name="mlibLightShape")
   print(type(light).__name__)                      # PointLight
   print(isinstance(light, mlib.PointLight))  # True
   print(isinstance(light, mlib.Shape))       # True。基底は最寄りの登録クラス
   print(light.getType())                           # pointLight
   print(light.isType("light"))                     # True。Mayaの継承チェーンで判定

   same = mlib.PointLight("mlibLightShape")   # 具象クラスを明示した取得も可能

基底はMayaの継承チェーン(``cmds.nodeType(inherited=True)``)上で最も近い登録クラスで、
``pointLight`` なら ``Shape``、``wrap``\ ・\ ``deltaMush`` なら ``GeometryFilter``\ (
デフォーマーの共通の基底として手書きで登録)、``symmetryConstraint`` なら
``Constraint`` です。登録クラスと生成対象の間にある抽象型(``weightGeometryFilter``\ ・
``containerBase``・``entity`` など)のクラスは作られず、生成クラス同士が親子になることも
ありません。生成クラスについて保証するのは「最寄りの登録クラスの派生である」ことだけです。

手書きクラスも同様で、``SkinCluster`` は ``GeometryFilter`` の直接の派生、``Container`` は
``Node`` の直接の派生です。したがって ``isinstance`` はMayaの抽象祖先を含む継承関係を
表しません。Mayaの継承に基づく判定は ``isType()`` か ``getType(inherited=True)``\ (基底型から
自身への順の ``list[str]``)で行います。``type(node) is mlib.Node`` のような厳密な型比較も、
未登録型が生成クラスになるため ``isinstance`` か ``isType()`` に置き換えてください。

.. code-block:: python

   container = mlib.ls(type="container")[0]
   print(container.isType("containerBase"))                  # True
   print("containerBase" in container.getType(inherited=True))  # True
   print(isinstance(container, mlib.ContainerBase))    # False。手書きクラスは抽象祖先を継承しない

``mlib.ContainerBase`` のように抽象型を要求した場合も同じ規則でクラスが生成されますが、
対応するインスタンスが無いため ``isinstance`` には使えません。Mayaが認識しない型名
(プラグイン未ロードを含む)は ``AttributeError``、``mlib.nodes.pointLight`` のような
先頭小文字の綴りも ``AttributeError`` です。生成クラスは ``mlib.nodes.__all__`` と
APIリファレンスには載りません。

生成クラスは要求時に作られてキャッシュされ、次の3つの契機で廃棄されます。
廃棄後の取得では作り直されるため、保持していたクラス参照に対する ``isinstance`` は偽になり、
そのクラスを明示した取得は ``TypeError`` になります。保持中の生成クラスは
``mlib.nodes.<TypeName>`` で取り直してください。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 契機
     - 内容
   * - 型登録表の変更
     - ``register``・``replace``・``clear`` による登録の追加・置換と、拡張(``mlib_*``)の登録・解除
   * - ``mlib.reload()``
     - 型登録表を作り直すため、生成クラスもすべて廃棄する
   * - プラグインのロード/アンロード
     - :class:`~mlib.common.plugin.Plugin` の ``load()``・``unload()``\ (``PluginPackage`` 経由を含む)で
       継承キャッシュと生成クラスを廃棄する。``cmds.loadPlugin`` の直接呼出しやPlug-in Managerの操作には追従しない

再読み込み
----------

.. code-block:: python

   import mlib
   mlib.reload()

本体を再読み込みし、拡張を再探索して型登録を作り直します。
import済みのクラスや保持したラッパーは自動では置き換わらないため、必要な参照を取得し直します。
詳細は :func:`~mlib.reload` を参照してください。

次に読むページ
--------------

* :doc:`whymlib` — 参照と値に分ける考え方
* :doc:`modules` — 用途ごとのモジュールとAPI
* :doc:`autoapi/mlib/index` — 公開パッケージと7つのコマンド入口
