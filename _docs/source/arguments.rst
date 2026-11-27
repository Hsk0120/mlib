.. このページは _tools/check_mlib_arguments.py が引数の表(ARGUMENTS)から作る。手で編集しない。

引数の一覧
==========

2か所以上のメソッド・関数で使う引数の名前と、その決まりの一覧です。
同じ名前の引数は、どのメソッドでも同じ働き・同じ受け方(位置で渡せるか、キーワード専用か)・同じ既定値にしてあります。
そうでないものは、各引数の「例外」に理由を書いています。

決まり
------

- 位置で渡すのは、そのメソッドの主な値(書き込む値・対象)と ``worldSpace``・``state`` だけです。
  ほかの指定はキーワードで渡します(``node.rename("a", ignoreShape=True)``)。
- オン・オフを選ぶ bool の引数は、``worldSpace``・``state`` を除いてキーワード専用です。
  bool の引数に ``0``・``1``・``None`` を渡すと TypeError になります。
- ``fast``・``check``・``safe`` は、キーワード専用の引数の最後にこの順で並びます。
- ``worldSpace`` を受けるメソッドは、短縮名 ``ws`` も受けます(同時には指定できません)。
- 角度は ``unit``、時間は ``timeUnit``、距離は ``distanceUnit`` で単位を選びます。

早見表
------

.. list-table::
   :header-rows: 1
   :widths: 18 14 14 54

   * - 引数
     - 受け方
     - 既定値
     - 働き
   * - :ref:`add <argument-add>`
     - キーワード専用
     - ``False``
     - 置き換えずに、今あるものへ加える。
   * - :ref:`aimAxis <argument-aimAxis>`
     - キーワード専用
     - ``'x'``
     - 向ける軸。
   * - :ref:`all <argument-all>`
     - キーワード専用
     - ``False``
     - 1つでなく全部を対象にする。
   * - :ref:`allDescendents <argument-allDescendents>`
     - キーワード専用
     - ``False``
     - 子孫まで含める。
   * - :ref:`asNode <argument-asNode>`
     - キーワード専用
     - ``False``
     - Plug でなくノードで返す。
   * - :ref:`asPair <argument-asPair>`
     - キーワード専用
     - ``False``
     - 相手との組で返す。
   * - :ref:`asPlug <argument-asPlug>`
     - キーワード専用
     - ``False``
     - ノードでなく Plug で返す。
   * - :ref:`at <argument-at>`
     - 位置でも渡せる
     - メソッドごと
     - 値を書く・読むアトリビュートの段(``Transform``)、またはアトリビュートの名前(Maya のフラグ)。
   * - :ref:`axis <argument-axis>`
     - 位置でも渡せる
     - メソッドごと
     - 軸(``"x"``/``"y"``/``"z"``・0/1/2、またはベクトル)。
   * - :ref:`base <argument-base>`
     - 位置でも渡せる
     - ``None``
     - blendShape のベースの形状。None は最初のベース。
   * - :ref:`channelBox <argument-channelBox>`
     - キーワード専用
     - ``None``
     - チャンネルボックスに出すかの状態(None は変えない)。
   * - :ref:`check <argument-check>`
     - キーワード専用
     - ``False``
     - 書き込む前に、値と書き込み先を確かめる。
   * - :ref:`children <argument-children>`
     - キーワード専用
     - ``True``
     - 子も対象にする。
   * - :ref:`colorSet <argument-colorSet>`
     - キーワード専用
     - ``None``
     - カラーセットの名前。None は今のカラーセット。
   * - :ref:`curve <argument-curve>`
     - 位置でも渡せる
     - メソッドごと
     - カーブ(ノード)、またはイージングの種類の名前。
   * - :ref:`degree <argument-degree>`
     - 位置でも渡せる
     - ``3``
     - カーブ・サーフェスの次数。
   * - :ref:`destination <argument-destination>`
     - 位置でも渡せる
     - メソッドごと
     - 出力側を対象にする指定(bool)、または移す先。
   * - :ref:`distanceUnit <argument-distanceUnit>`
     - キーワード専用
     - ``'cm'``
     - 距離の数値の単位。None は今のUIの距離単位。
   * - :ref:`faceVertices <argument-faceVertices>`
     - キーワード専用
     - ``None``
     - 対象の面頂点。None は全部。
   * - :ref:`failed <argument-failed>`
     - キーワード専用
     - メソッドごと
     - 失敗した Edit を対象にする。
   * - :ref:`fast <argument-fast>`
     - キーワード専用
     - ``False``
     - TrueはUndoなしのOpenMaya更新。
   * - :ref:`force <argument-force>`
     - キーワード専用
     - ``False``
     - 障害があっても実行する(Maya の force と同じ意味)。
   * - :ref:`full <argument-full>`
     - キーワード専用
     - ``False``
     - DAG のフルパスの名前にする。
   * - :ref:`fullWeight <argument-fullWeight>`
     - キーワード専用
     - ``1.0``
     - ウェイトが1のときの値。
   * - :ref:`geometry <argument-geometry>`
     - 位置でも渡せる
     - 
     - 対象の形状。
   * - :ref:`geometryIndex <argument-geometryIndex>`
     - キーワード専用
     - ``None``
     - デフォーマーの形状の番号。None は最初の形状。
   * - :ref:`get <argument-get>`
     - キーワード専用
     - ``False``
     - 書き込まずに、書き込む予定の値を返す。
   * - :ref:`includeSelf <argument-includeSelf>`
     - キーワード専用
     - メソッドごと
     - 自身を結果に含める。
   * - :ref:`index <argument-index>`
     - キーワード専用
     - メソッドごと
     - 番号。
   * - :ref:`influence <argument-influence>`
     - キーワード専用
     - 
     - インフルエンス(対象として渡すとき)、またはインフルエンスとして使う側を調べる指定(bool)。
   * - :ref:`influenceAssociation <argument-influenceAssociation>`
     - キーワード専用
     - メソッドごと
     - インフルエンスを対応付ける方法の並び。
   * - :ref:`input <argument-input>`
     - キーワード専用
     - 
     - 入力側を対象にする(``AnimCurve`` ではカーブの入力の位置で、主な値として位置で渡す)。
   * - :ref:`inTangentType <argument-inTangentType>`
     - 位置でも渡せる
     - ``None``
     - 入る側の接線の種類。None は Maya の設定のまま。
   * - :ref:`intermediates <argument-intermediates>`
     - キーワード専用
     - ``False``
     - 中間オブジェクトも含める。
   * - :ref:`items <argument-items>`
     - 位置でも渡せる
     - ``None``
     - 対象の並び。None は指定なし。
   * - :ref:`jointOrient <argument-jointOrient>`
     - キーワード専用
     - メソッドごと
     - jointOrient の値、または jointOrient を対象にする指定。
   * - :ref:`keyable <argument-keyable>`
     - キーワード専用
     - ``None``
     - キーを打てるかの状態(None は変えない)。
   * - :ref:`kind <argument-kind>`
     - キーワード専用
     - メソッドごと
     - 対象の種類を名前で選ぶ。
   * - :ref:`layer <argument-layer>`
     - 位置でも渡せる
     - 
     - アニメーションレイヤー。None はレイヤーを通さない。
   * - :ref:`leaves <argument-leaves>`
     - キーワード専用
     - ``False``
     - コンパウンドアトリビュートの末端の子まで対象にする。
   * - :ref:`locked <argument-locked>`
     - キーワード専用
     - ``None``
     - ロックの状態(None は変えない・絞り込まない)。
   * - :ref:`maintain <argument-maintain>`
     - キーワード専用
     - メソッドごと
     - 上限を保つ。
   * - :ref:`maxDistance <argument-maxDistance>`
     - 位置でも渡せる
     - ``None``
     - 探す距離の上限。None は制限なし。
   * - :ref:`members <argument-members>`
     - 位置でも渡せる
     - ``None``
     - 対象のメンバーの並び。None は指定なし。
   * - :ref:`method <argument-method>`
     - キーワード専用
     - メソッドごと
     - 処理の方法を名前で選ぶ。
   * - :ref:`missing <argument-missing>`
     - キーワード専用
     - 
     - 無くなった対象の扱い。
   * - :ref:`mode <argument-mode>`
     - キーワード専用
     - メソッドごと
     - 書き込み方・合わせ方を名前で選ぶ。
   * - :ref:`name <argument-name>`
     - 位置でも渡せる
     - メソッドごと
     - 名前。作るものの名前は None で Maya に任せる。
   * - :ref:`nameMap <argument-nameMap>`
     - キーワード専用
     - ``None``
     - 名前空間を除いた名前の対応表。
   * - :ref:`names <argument-names>`
     - 位置でも渡せる
     - ``None``
     - 名前の並び。None は指定なし。
   * - :ref:`namespace <argument-namespace>`
     - 位置でも渡せる
     - ``None``
     - 名前空間。None は今のまま・付けない。
   * - :ref:`namespaceMap <argument-namespaceMap>`
     - キーワード専用
     - ``None``
     - 名前空間の対応。
   * - :ref:`ndigits <argument-ndigits>`
     - 位置でも渡せる
     - ``None``
     - 丸める小数の桁数。None は整数へ丸める(round と同じ)。
   * - :ref:`nodes <argument-nodes>`
     - 位置でも渡せる
     - ``None``
     - 対象のノードの並び。None は指定なし。
   * - :ref:`normal <argument-normal>`
     - 位置でも渡せる
     - メソッドごと
     - 法線の向き。
   * - :ref:`normalize <argument-normalize>`
     - キーワード専用
     - ``True``
     - ウェイトを正規化する。
   * - :ref:`order <argument-order>`
     - 位置でも渡せる
     - メソッドごと
     - 回転順序。
   * - :ref:`outliner <argument-outliner>`
     - キーワード専用
     - ``False``
     - 描画色でなく、アウトライナーの色を扱う。
   * - :ref:`output <argument-output>`
     - キーワード専用
     - メソッドごと
     - 出力側を対象にする(``ShadingEngine.setShader`` はシェーダーの出力のアトリビュート)。
   * - :ref:`outTangentType <argument-outTangentType>`
     - 位置でも渡せる
     - ``None``
     - 出る側の接線の種類。None は Maya の設定のまま。
   * - :ref:`parent <argument-parent>`
     - 位置でも渡せる
     - メソッドごと
     - 親。None はワールド直下・指定しない。
   * - :ref:`path <argument-path>`
     - 
     - 
     - ファイルのパス。
   * - :ref:`perFace <argument-perFace>`
     - キーワード専用
     - ``False``
     - 頂点ごとでなく、面頂点ごとに扱う。
   * - :ref:`position <argument-position>`
     - 位置でも渡せる
     - メソッドごと
     - 位置の値、または位置を対象にする指定。
   * - :ref:`preserve <argument-preserve>`
     - キーワード専用
     - メソッドごと
     - 変えたあとも見た目(ワールドの姿勢)を保つ。
   * - :ref:`radius <argument-radius>`
     - 位置でも渡せる
     - 
     - 半径。
   * - :ref:`relative <argument-relative>`
     - キーワード専用
     - ``False``
     - 今の値からの相対で変える。
   * - :ref:`removeInfluence <argument-removeInfluence>`
     - キーワード専用
     - 
     - skinCluster のインフルエンスから外してから削除する。
   * - :ref:`removeNamespace <argument-removeNamespace>`
     - キーワード専用
     - ``False``
     - 名前空間を取り除く。
   * - :ref:`repair <argument-repair>`
     - キーワード専用
     - ``False``
     - 不正なウェイトを直してから処理する。
   * - :ref:`replace <argument-replace>`
     - キーワード専用
     - ``None``
     - 順に当てる文字列の置き換え(``select`` では今の選択を置き換える指定)。
   * - :ref:`rotate <argument-rotate>`
     - 位置でも渡せる
     - メソッドごと
     - 回転の値、または回転を対象にする指定。
   * - :ref:`rotateAxis <argument-rotateAxis>`
     - キーワード専用
     - メソッドごと
     - rotateAxis の値、または rotateAxis を対象にする指定。
   * - :ref:`safe <argument-safe>`
     - キーワード専用
     - ``False``
     - 失敗しても例外にしない。
   * - :ref:`scale <argument-scale>`
     - 位置でも渡せる
     - メソッドごと
     - スケールの値、またはスケールを対象にする指定。
   * - :ref:`shear <argument-shear>`
     - 位置でも渡せる
     - メソッドごと
     - シアーの値、またはシアーを対象にする指定。
   * - :ref:`skipConnected <argument-skipConnected>`
     - キーワード専用
     - ``False``
     - 接続があるノードは削除しない。
   * - :ref:`skipExisting <argument-skipExisting>`
     - キーワード専用
     - ``False``
     - すでに目的の状態なら何もしない。
   * - :ref:`sortBy <argument-sortBy>`
     - キーワード専用
     - メソッドごと
     - 並べる順。
   * - :ref:`source <argument-source>`
     - 位置でも渡せる
     - メソッドごと
     - 入力側を対象にする指定(bool)、または元になるもの。
   * - :ref:`start <argument-start>`
     - 位置でも渡せる
     - メソッドごと
     - 始まりの番号・値。
   * - :ref:`state <argument-state>`
     - 位置でも渡せる
     - ``True``
     - オン・オフを設定する値。
   * - :ref:`threshold <argument-threshold>`
     - 位置でも渡せる
     - メソッドごと
     - しきい値。
   * - :ref:`time <argument-time>`
     - キーワード専用
     - ``None``
     - 時刻・時刻の範囲。None は絞らない。
   * - :ref:`timeOffset <argument-timeOffset>`
     - キーワード専用
     - ``0``
     - 時刻へ足す値。
   * - :ref:`timeUnit <argument-timeUnit>`
     - キーワード専用
     - ``'frame'``
     - 時間の数値の単位(``"frame"`` は今のUIの時間単位のフレーム、``"sec"`` は秒)。
   * - :ref:`to <argument-to>`
     - 位置でも渡せる
     - 
     - 終わりのノード・移す先。
   * - :ref:`tolerance <argument-tolerance>`
     - キーワード専用
     - メソッドごと
     - 同じとみなす誤差。
   * - :ref:`toShape <argument-toShape>`
     - キーワード専用
     - ``False``
     - Transform でなく、その Shape の色を扱う。
   * - :ref:`transferToParent <argument-transferToParent>`
     - キーワード専用
     - ``True``
     - 外すインフルエンスのウェイトを親へ移す。
   * - :ref:`translate <argument-translate>`
     - 位置でも渡せる
     - メソッドごと
     - 移動の値、または移動を対象にする指定。
   * - :ref:`type <argument-type>`
     - キーワード専用
     - メソッドごと
     - ノード型・アトリビュートの型・返すコンポーネントの種類。
   * - :ref:`uiUnits <argument-uiUnits>`
     - キーワード専用
     - ``False``
     - 今のUIの単位の数値で受け渡しする。
   * - :ref:`unit <argument-unit>`
     - キーワード専用
     - ``'deg'``
     - 角度の数値の単位(``"deg"`` は度、``"rad"`` はラジアン)。
   * - :ref:`unlock <argument-unlock>`
     - キーワード専用
     - ``False``
     - ロックを一時的に外してから処理する。
   * - :ref:`unused <argument-unused>`
     - キーワード専用
     - メソッドごと
     - 使っていないものを対象にする。
   * - :ref:`up <argument-up>`
     - 位置でも渡せる
     - メソッドごと
     - 上の向きのベクトル。
   * - :ref:`upAxis <argument-upAxis>`
     - キーワード専用
     - ``'y'``
     - 上へ向ける軸。
   * - :ref:`uvSet <argument-uvSet>`
     - キーワード専用
     - ``None``
     - UVセットの名前。None は今のUVセット。
   * - :ref:`value <argument-value>`
     - 位置でも渡せる
     - メソッドごと
     - 書き込む値。
   * - :ref:`valueOffset <argument-valueOffset>`
     - キーワード専用
     - ``0``
     - 値へ足す値。
   * - :ref:`vertices <argument-vertices>`
     - キーワード専用
     - ``None``
     - 対象の頂点。None は全部。
   * - :ref:`weights <argument-weights>`
     - 位置でも渡せる
     - ``None``
     - ウェイトの値、またはウェイトのファイル。
   * - :ref:`what <argument-what>`
     - キーワード専用
     - メソッドごと
     - 取得するものを名前で選ぶ。
   * - :ref:`width <argument-width>`
     - 位置でも渡せる
     - メソッドごと
     - 幅。
   * - :ref:`worldSpace <argument-worldSpace>`
     - 位置でも渡せる
     - ``False``
     - Trueはワールド空間、Falseはローカル(オブジェクト)空間。
   * - :ref:`ws <argument-ws>`
     - キーワード専用
     - 
     - worldSpace の短縮名。
   * - :ref:`zeroScaleOrient <argument-zeroScaleOrient>`
     - キーワード専用
     - 
     - scaleOrient を0にする。

引数ごとの決まり
----------------

.. _argument-add:

``add``
~~~~~~~

置き換えずに、今あるものへ加える。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(10): :meth:`Keyframe.select <mlib.common.keyframe.Keyframe.select>`、:meth:`Keyframes.select <mlib.common.keyframe.Keyframes.select>`、:meth:`Node.select <mlib.nodes.node.Node.select>`、:meth:`Nodes.select <mlib.nodes.node.Nodes.select>`、:meth:`Nodes.setParent <mlib.nodes.node.Nodes.setParent>`、:meth:`Selection.select <mlib.common.selection.Selection.select>`、:meth:`Shape.setParent <mlib.nodes.shape.Shape.setParent>`、:meth:`SkinCluster.transferWeights <mlib.nodes.skinCluster.SkinCluster.transferWeights>`、:meth:`Transform.setParent <mlib.nodes.transform.Transform.setParent>`、:func:`select <mlib.cmds.select.select>`

.. _argument-aimAxis:

``aimAxis``
~~~~~~~~~~~

向ける軸。

- 受け方: キーワード専用
- 既定値: ``'x'``
- 使う所(6): :meth:`Matrix.fromAim <mlib.maths.matrix.Matrix.fromAim>`、:meth:`NurbsCurve.getMatricesAlong <mlib.nodes.nurbsCurve.NurbsCurve.getMatricesAlong>`、:meth:`NurbsSurface.getAtParam <mlib.nodes.nurbsSurface.NurbsSurface.getAtParam>`、:meth:`Quaternion.asRollBend <mlib.maths.quaternion.Quaternion.asRollBend>`、:meth:`Quaternion.fromRollBend <mlib.maths.quaternion.Quaternion.fromRollBend>`、:func:`createJointChain <mlib.cmds.createJointChain.createJointChain>`

.. _argument-all:

``all``
~~~~~~~

1つでなく全部を対象にする。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(14): :meth:`Container.removeMembers <mlib.nodes.container.Container.removeMembers>`、:meth:`DagContainer.removeMembers <mlib.nodes.dagContainer.DagContainer.removeMembers>`、:meth:`DagNode.getParent <mlib.nodes.dagNode.DagNode.getParent>`、:meth:`DagNode.getShape <mlib.nodes.dagNode.DagNode.getShape>`、:meth:`DagPose.removeMembers <mlib.nodes.dagPose.DagPose.removeMembers>`、:meth:`DisplayLayer.removeMembers <mlib.nodes.displayLayer.DisplayLayer.removeMembers>`、:meth:`GeometryFilter.dumpDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.dumpDeformerWeights>`、:meth:`GeometryFilter.getGeometry <mlib.nodes.geometryFilter.GeometryFilter.getGeometry>`、:meth:`Namespace.getParent <mlib.common.namespace.Namespace.getParent>`、:meth:`NurbsSurface.removeKnot <mlib.nodes.nurbsSurface.NurbsSurface.removeKnot>`、:meth:`ObjectSet.removeMembers <mlib.nodes.objectSet.ObjectSet.removeMembers>`、:meth:`Plug.getParent <mlib.plugs.plug.Plug.getParent>`、:meth:`Transform.getShape <mlib.nodes.transform.Transform.getShape>`、:func:`select <mlib.cmds.select.select>`

.. _argument-allDescendents:

``allDescendents``
~~~~~~~~~~~~~~~~~~

子孫まで含める。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(4): :meth:`DagNode.getChildren <mlib.nodes.dagNode.DagNode.getChildren>`、:meth:`Namespace.getChildren <mlib.common.namespace.Namespace.getChildren>`、:meth:`Namespace.getNodes <mlib.common.namespace.Namespace.getNodes>`、:meth:`Transform.getChildren <mlib.nodes.transform.Transform.getChildren>`

.. _argument-asNode:

``asNode``
~~~~~~~~~~

Plug でなくノードで返す。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(2): :meth:`Node.getConnections <mlib.nodes.node.Node.getConnections>`、:meth:`Plug.getConnections <mlib.plugs.plug.Plug.getConnections>`

.. _argument-asPair:

``asPair``
~~~~~~~~~~

相手との組で返す。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(2): :meth:`Node.getConnections <mlib.nodes.node.Node.getConnections>`、:meth:`Plug.getConnections <mlib.plugs.plug.Plug.getConnections>`

.. _argument-asPlug:

``asPlug``
~~~~~~~~~~

ノードでなく Plug で返す。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(1): :meth:`ShadingEngine.getShader <mlib.nodes.shadingEngine.ShadingEngine.getShader>`

.. _argument-at:

``at``
~~~~~~

値を書く・読むアトリビュートの段(``Transform``)、またはアトリビュートの名前(Maya のフラグ)。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(Transform の段の番号と、Maya のフラグの短縮名)
- 使う所(4): :meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`Transform.getTranslation <mlib.nodes.transform.Transform.getTranslation>`、:meth:`Transform.setTranslation <mlib.nodes.transform.Transform.setTranslation>`、:func:`bakeResults <mlib.cmds.bakeResults.bakeResults>`

.. _argument-axis:

``axis``
~~~~~~~~

軸(``"x"``/``"y"``/``"z"``・0/1/2、またはベクトル)。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(軸の名前を受けるものと、向きのベクトルを受けるものがある)
- 使う所(23): :meth:`BlendShape.mirrorTarget <mlib.nodes.blendShape.BlendShape.mirrorTarget>`、:meth:`EulerRotate.mirror <mlib.maths.eulerRotate.EulerRotate.mirror>`、:meth:`Matrix.getAxis <mlib.maths.matrix.Matrix.getAxis>`、:meth:`Matrix.mirror <mlib.maths.matrix.Matrix.mirror>`、:meth:`Mesh.getMirrorVertexMap <mlib.nodes.mesh.Mesh.getMirrorVertexMap>`、:meth:`PointComponent.setPosition <mlib.components.pointComponent.PointComponent.setPosition>`、:meth:`PointComponents.mirror <mlib.components.pointComponent.PointComponents.mirror>`、:meth:`PointComponents.setPosition <mlib.components.pointComponent.PointComponents.setPosition>`、:meth:`Quaternion.asSwingTwist <mlib.maths.quaternion.Quaternion.asSwingTwist>`、:meth:`Quaternion.fromAxisAngle <mlib.maths.quaternion.Quaternion.fromAxisAngle>`、:meth:`Quaternion.mirror <mlib.maths.quaternion.Quaternion.mirror>`、:meth:`Transform.mirrorGeometry <mlib.nodes.transform.Transform.mirrorGeometry>`、:meth:`Transform.mirrorTransform <mlib.nodes.transform.Transform.mirrorTransform>`、:meth:`UV.setPosition <mlib.components.uv.UV.setPosition>`、:meth:`UVs.setPosition <mlib.components.uv.UVs.setPosition>`、:meth:`Vector.fromAxis <mlib.maths.vector.Vector.fromAxis>`、:meth:`Vector.mirror <mlib.maths.vector.Vector.mirror>`、:meth:`Vector.orthogonal <mlib.maths.vector.Vector.orthogonal>`、:meth:`Vector.projected <mlib.maths.vector.Vector.projected>`、``_ControlPointShape.mirror``、:func:`createNurbsPlane <mlib.cmds.createNurbsPlane.createNurbsPlane>`、:func:`createPoly <mlib.cmds.createPoly.createPoly>`、:func:`mirrorArguments <mlib.util.mirrorArguments>`

.. _argument-base:

``base``
~~~~~~~~

blendShape のベースの形状。None は最初のベース。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 使う所(13): :meth:`BlendShape.addTarget <mlib.nodes.blendShape.BlendShape.addTarget>`、:meth:`BlendShape.getInBetweenWeights <mlib.nodes.blendShape.BlendShape.getInBetweenWeights>`、:meth:`BlendShape.getTargetDeltas <mlib.nodes.blendShape.BlendShape.getTargetDeltas>`、:meth:`BlendShape.getTargetGeometry <mlib.nodes.blendShape.BlendShape.getTargetGeometry>`、:meth:`BlendShape.getTargetItemIndices <mlib.nodes.blendShape.BlendShape.getTargetItemIndices>`、:meth:`BlendShape.getTargetVertices <mlib.nodes.blendShape.BlendShape.getTargetVertices>`、:meth:`BlendShape.getTargetWeights <mlib.nodes.blendShape.BlendShape.getTargetWeights>`、:meth:`BlendShape.mirrorTarget <mlib.nodes.blendShape.BlendShape.mirrorTarget>`、:meth:`BlendShape.replaceTarget <mlib.nodes.blendShape.BlendShape.replaceTarget>`、:meth:`BlendShape.resetTargetVertices <mlib.nodes.blendShape.BlendShape.resetTargetVertices>`、:meth:`BlendShape.setTargetDeltas <mlib.nodes.blendShape.BlendShape.setTargetDeltas>`、:meth:`BlendShape.setTargetWeights <mlib.nodes.blendShape.BlendShape.setTargetWeights>`、:func:`createBlendShape <mlib.cmds.createBlendShape.createBlendShape>`

.. _argument-channelBox:

``channelBox``
~~~~~~~~~~~~~~

チャンネルボックスに出すかの状態(None は変えない)。

- 受け方: キーワード専用
- 既定値: ``None``
- 既定値の例外: ``Node.addAttr`` — 作るときの指定なので、変えないという値が無い
- 使う所(3): :meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`Node.setAttrFlags <mlib.nodes.node.Node.setAttrFlags>`、:meth:`Plug.setFlags <mlib.plugs.plug.Plug.setFlags>`

.. _argument-check:

``check``
~~~~~~~~~

書き込む前に、値と書き込み先を確かめる。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 説明の決まり文句: Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。
- 使う所(88): :meth:`AimConstraint.setRestRotate <mlib.nodes.aimConstraint.AimConstraint.setRestRotate>`、:meth:`AnimCurve.addKey <mlib.nodes.animCurve.AnimCurve.addKey>`、:meth:`AnimCurve.addKeys <mlib.nodes.animCurve.AnimCurve.addKeys>`、:meth:`AnimCurve.setInfinity <mlib.nodes.animCurve.AnimCurve.setInfinity>`、:meth:`BlendShape.resetTargetVertices <mlib.nodes.blendShape.BlendShape.resetTargetVertices>`、:meth:`BlendShape.setTargetDeltas <mlib.nodes.blendShape.BlendShape.setTargetDeltas>`、:meth:`BlendShape.setTargetWeights <mlib.nodes.blendShape.BlendShape.setTargetWeights>`、:meth:`Camera.copyViewFrom <mlib.nodes.camera.Camera.copyViewFrom>`、:meth:`Camera.setPoint <mlib.nodes.camera.Camera.setPoint>`、:meth:`Camera.setView <mlib.nodes.camera.Camera.setView>`、:meth:`Constraint.setWeight <mlib.nodes.constraint.Constraint.setWeight>`、:meth:`DagNode.setColor <mlib.nodes.dagNode.DagNode.setColor>`、:meth:`DagNode.setDisplayType <mlib.nodes.dagNode.DagNode.setDisplayType>`、:meth:`DagNode.setShadingOverride <mlib.nodes.dagNode.DagNode.setShadingOverride>`、:meth:`DagNode.setVisibility <mlib.nodes.dagNode.DagNode.setVisibility>`、:meth:`Double3Plug.set <mlib.plugs.double3Plug.Double3Plug.set>`、:meth:`DrivenKey.setKey <mlib.common.drivenKey.DrivenKey.setKey>`、:meth:`GeometryFilter.copyDeformerWeightsTo <mlib.nodes.geometryFilter.GeometryFilter.copyDeformerWeightsTo>`、:meth:`GeometryFilter.loadDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.loadDeformerWeights>`、:meth:`GeometryFilter.setDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.setDeformerWeights>`、:meth:`Joint.resetAttrs <mlib.nodes.joint.Joint.resetAttrs>`、:meth:`Joint.setDegreesOfFreedom <mlib.nodes.joint.Joint.setDegreesOfFreedom>`、:meth:`Joint.setInfluenceLocked <mlib.nodes.joint.Joint.setInfluenceLocked>`、:meth:`Joint.setJointOrient <mlib.nodes.joint.Joint.setJointOrient>`、:meth:`Joint.setPreferredAngle <mlib.nodes.joint.Joint.setPreferredAngle>`、:meth:`Joint.setRadius <mlib.nodes.joint.Joint.setRadius>`、:meth:`Joint.setSegmentScaleCompensate <mlib.nodes.joint.Joint.setSegmentScaleCompensate>`、:meth:`Joints.setRadius <mlib.nodes.joint.Joints.setRadius>`、:meth:`Joints.setSegmentScaleCompensate <mlib.nodes.joint.Joints.setSegmentScaleCompensate>`、:meth:`Keyframe.delete <mlib.common.keyframe.Keyframe.delete>`、:meth:`Keyframe.setTangent <mlib.common.keyframe.Keyframe.setTangent>`、:meth:`Keyframe.setValue <mlib.common.keyframe.Keyframe.setValue>`、:meth:`Keyframes.delete <mlib.common.keyframe.Keyframes.delete>`、:meth:`Keyframes.setTangent <mlib.common.keyframe.Keyframes.setTangent>`、:meth:`Keyframes.setValue <mlib.common.keyframe.Keyframes.setValue>`、:meth:`Mesh.setFaceVertexNormals <mlib.nodes.mesh.Mesh.setFaceVertexNormals>`、:meth:`Mesh.setNormals <mlib.nodes.mesh.Mesh.setNormals>`、:meth:`Mesh.setVertexColors <mlib.nodes.mesh.Mesh.setVertexColors>`、:meth:`Node.resetAttrs <mlib.nodes.node.Node.resetAttrs>`、:meth:`Node.setAttrFlags <mlib.nodes.node.Node.setAttrFlags>`、:meth:`Node.setLocked <mlib.nodes.node.Node.setLocked>`、:meth:`Nodes.resetAttrs <mlib.nodes.node.Nodes.resetAttrs>`、:meth:`Nodes.setColor <mlib.nodes.node.Nodes.setColor>`、:meth:`Nodes.setColors <mlib.nodes.node.Nodes.setColors>`、:meth:`Nodes.setParent <mlib.nodes.node.Nodes.setParent>`、:meth:`Nodes.setVisibility <mlib.nodes.node.Nodes.setVisibility>`、:meth:`Plug.reset <mlib.plugs.plug.Plug.reset>`、:meth:`Plug.set <mlib.plugs.plug.Plug.set>`、:meth:`Plug.setIfChanged <mlib.plugs.plug.Plug.setIfChanged>`、:meth:`PointComponent.setPosition <mlib.components.pointComponent.PointComponent.setPosition>`、:meth:`PointComponents.mirror <mlib.components.pointComponent.PointComponents.mirror>`、:meth:`PointComponents.setPosition <mlib.components.pointComponent.PointComponents.setPosition>`、:meth:`Shape.scaleGeometry <mlib.nodes.shape.Shape.scaleGeometry>`、:meth:`Shape.setParent <mlib.nodes.shape.Shape.setParent>`、:meth:`SkinCluster.importWeights <mlib.nodes.skinCluster.SkinCluster.importWeights>`、:meth:`SkinCluster.limitInfluences <mlib.nodes.skinCluster.SkinCluster.limitInfluences>`、:meth:`SkinCluster.normalizeWeights <mlib.nodes.skinCluster.SkinCluster.normalizeWeights>`、:meth:`SkinCluster.pruneWeights <mlib.nodes.skinCluster.SkinCluster.pruneWeights>`、:meth:`SkinCluster.removeInvalidWeights <mlib.nodes.skinCluster.SkinCluster.removeInvalidWeights>`、:meth:`SkinCluster.roundWeights <mlib.nodes.skinCluster.SkinCluster.roundWeights>`、:meth:`SkinCluster.setBlendWeights <mlib.nodes.skinCluster.SkinCluster.setBlendWeights>`、:meth:`SkinCluster.setInfluencesLocked <mlib.nodes.skinCluster.SkinCluster.setInfluencesLocked>`、:meth:`SkinCluster.setMaxInfluences <mlib.nodes.skinCluster.SkinCluster.setMaxInfluences>`、:meth:`SkinCluster.setWeights <mlib.nodes.skinCluster.SkinCluster.setWeights>`、:meth:`SkinCluster.setWeightsData <mlib.nodes.skinCluster.SkinCluster.setWeightsData>`、:meth:`SkinCluster.transferWeights <mlib.nodes.skinCluster.SkinCluster.transferWeights>`、:meth:`Transform.centerPivot <mlib.nodes.transform.Transform.centerPivot>`、:meth:`Transform.mirrorGeometry <mlib.nodes.transform.Transform.mirrorGeometry>`、:meth:`Transform.mirrorTransform <mlib.nodes.transform.Transform.mirrorTransform>`、:meth:`Transform.scaleGeometry <mlib.nodes.transform.Transform.scaleGeometry>`、:meth:`Transform.setMatrix <mlib.nodes.transform.Transform.setMatrix>`、:meth:`Transform.setOffsetParentMatrix <mlib.nodes.transform.Transform.setOffsetParentMatrix>`、:meth:`Transform.setParent <mlib.nodes.transform.Transform.setParent>`、:meth:`Transform.setPivot <mlib.nodes.transform.Transform.setPivot>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、:meth:`Transform.setRotate <mlib.nodes.transform.Transform.setRotate>`、:meth:`Transform.setRotateOrder <mlib.nodes.transform.Transform.setRotateOrder>`、:meth:`Transform.setScale <mlib.nodes.transform.Transform.setScale>`、:meth:`Transform.setShear <mlib.nodes.transform.Transform.setShear>`、:meth:`Transform.setTransformation <mlib.nodes.transform.Transform.setTransformation>`、:meth:`Transform.setTranslation <mlib.nodes.transform.Transform.setTranslation>`、:meth:`UV.setPosition <mlib.components.uv.UV.setPosition>`、:meth:`UVs.setPosition <mlib.components.uv.UVs.setPosition>`、:meth:`Vertex.setColor <mlib.components.vertex.Vertex.setColor>`、:meth:`VertexFace.setColor <mlib.components.vertexFace.VertexFace.setColor>`、:meth:`VertexFace.setNormal <mlib.components.vertexFace.VertexFace.setNormal>`、``_ControlPointShape.mirror``、``_ControlPointShape.setPoints``

.. _argument-children:

``children``
~~~~~~~~~~~~

子も対象にする。

- 受け方: キーワード専用
- 既定値: ``True``
- 型: ``bool``
- 既定値の例外: ``Node.setAttrFlags`` — フラグの設定は、指定したアトリビュートだけが既定(Maya と同じ)
- 既定値の例外: ``Plug.setFlags`` — フラグの設定は、指定したアトリビュートだけが既定(Maya と同じ)
- 使う所(6): :meth:`Joint.assumePreferredAngles <mlib.nodes.joint.Joint.assumePreferredAngles>`、:meth:`Joint.orient <mlib.nodes.joint.Joint.orient>`、:meth:`Joints.orient <mlib.nodes.joint.Joints.orient>`、:meth:`Node.getPlugs <mlib.nodes.node.Node.getPlugs>`、:meth:`Node.setAttrFlags <mlib.nodes.node.Node.setAttrFlags>`、:meth:`Plug.setFlags <mlib.plugs.plug.Plug.setFlags>`

.. _argument-colorSet:

``colorSet``
~~~~~~~~~~~~

カラーセットの名前。None は今のカラーセット。

- 受け方: キーワード専用
- 既定値: ``None``
- 型: ``str | None``
- 使う所(9): :meth:`Face.getColor <mlib.components.face.Face.getColor>`、:meth:`Mesh.getVertexColors <mlib.nodes.mesh.Mesh.getVertexColors>`、:meth:`Mesh.removeFaceVertexColors <mlib.nodes.mesh.Mesh.removeFaceVertexColors>`、:meth:`Mesh.setVertexColors <mlib.nodes.mesh.Mesh.setVertexColors>`、:meth:`Vertex.getColor <mlib.components.vertex.Vertex.getColor>`、:meth:`Vertex.setColor <mlib.components.vertex.Vertex.setColor>`、:meth:`VertexFace.getColor <mlib.components.vertexFace.VertexFace.getColor>`、:meth:`VertexFace.removeColor <mlib.components.vertexFace.VertexFace.removeColor>`、:meth:`VertexFace.setColor <mlib.components.vertexFace.VertexFace.setColor>`

.. _argument-curve:

``curve``
~~~~~~~~~

カーブ(ノード)、またはイージングの種類の名前。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(ノードを受けるものと、イージングの名前を受けるものがある)
- 使う所(6): :meth:`Faces.extrude <mlib.components.face.Faces.extrude>`、``Keyframe.__init__``、:meth:`Keyframes.getIndices <mlib.common.keyframe.Keyframes.getIndices>`、:meth:`SkinCluster.redistributeWeights <mlib.nodes.skinCluster.SkinCluster.redistributeWeights>`、:func:`createIkHandle <mlib.cmds.createIkHandle.createIkHandle>`、:func:`ease <mlib.maths.easing.ease>`

.. _argument-degree:

``degree``
~~~~~~~~~~

カーブ・サーフェスの次数。

- 受け方: 位置でも渡せる
- 既定値: ``3``
- 既定値の例外: ``NurbsCurve.rebuild`` — None は今の次数のまま
- 使う所(4): :meth:`NurbsCurve.rebuild <mlib.nodes.nurbsCurve.NurbsCurve.rebuild>`、:func:`createCircle <mlib.cmds.createCircle.createCircle>`、:func:`createCurve <mlib.cmds.createCurve.createCurve>`、:func:`createNurbsPlane <mlib.cmds.createNurbsPlane.createNurbsPlane>`

.. _argument-destination:

``destination``
~~~~~~~~~~~~~~~

出力側を対象にする指定(bool)、または移す先。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(接続の向きの bool と、移す先の指定)
- 使う所(7): :meth:`Namespace.delete <mlib.common.namespace.Namespace.delete>`、:meth:`Node.getConnections <mlib.nodes.node.Node.getConnections>`、:meth:`Plug.connectTo <mlib.plugs.plug.Plug.connectTo>`、:meth:`Plug.disconnectAll <mlib.plugs.plug.Plug.disconnectAll>`、:meth:`Plug.getConnections <mlib.plugs.plug.Plug.getConnections>`、:meth:`Plug.isConnected <mlib.plugs.plug.Plug.isConnected>`、:func:`bakeDeformer <mlib.cmds.bakeDeformer.bakeDeformer>`

.. _argument-distanceUnit:

``distanceUnit``
~~~~~~~~~~~~~~~~

距離の数値の単位。None は今のUIの距離単位。

- 受け方: キーワード専用
- 既定値: ``'cm'``
- 型: ``str``
- 使う所(3): :meth:`Edge.getLength <mlib.components.edge.Edge.getLength>`、:meth:`NurbsCurve.getLength <mlib.nodes.nurbsCurve.NurbsCurve.getLength>`、:meth:`NurbsCurve.getParam <mlib.nodes.nurbsCurve.NurbsCurve.getParam>`

.. _argument-faceVertices:

``faceVertices``
~~~~~~~~~~~~~~~~

対象の面頂点。None は全部。

- 受け方: キーワード専用
- 既定値: ``None``
- 使う所(6): :meth:`Mesh.getFaceVertexTangents <mlib.nodes.mesh.Mesh.getFaceVertexTangents>`、:meth:`Mesh.getVertexColors <mlib.nodes.mesh.Mesh.getVertexColors>`、:meth:`Mesh.getVertexNormals <mlib.nodes.mesh.Mesh.getVertexNormals>`、:meth:`Mesh.removeFaceVertexColors <mlib.nodes.mesh.Mesh.removeFaceVertexColors>`、:meth:`Mesh.setFaceVertexNormals <mlib.nodes.mesh.Mesh.setFaceVertexNormals>`、:meth:`Mesh.setVertexColors <mlib.nodes.mesh.Mesh.setVertexColors>`

.. _argument-failed:

``failed``
~~~~~~~~~~

失敗した Edit を対象にする。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(Maya の referenceQuery・referenceEdit の既定と同じ(getEdits は False、removeEdits は True))
- 使う所(2): :meth:`Reference.getEdits <mlib.nodes.reference.Reference.getEdits>`、:meth:`Reference.removeEdits <mlib.nodes.reference.Reference.removeEdits>`

.. _argument-fast:

``fast``
~~~~~~~~

TrueはUndoなしのOpenMaya更新。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 説明の決まり文句: TrueはUndoなしのOpenMaya更新。既定False。
- 使う所(123): :meth:`AimConstraint.setRestRotate <mlib.nodes.aimConstraint.AimConstraint.setRestRotate>`、:meth:`AnimCurve.addKey <mlib.nodes.animCurve.AnimCurve.addKey>`、:meth:`AnimCurve.setInfinity <mlib.nodes.animCurve.AnimCurve.setInfinity>`、:meth:`AnimationSnapshot.apply <mlib.json.animationSnapshot.AnimationSnapshot.apply>`、:meth:`BlendShape.resetTargetVertices <mlib.nodes.blendShape.BlendShape.resetTargetVertices>`、:meth:`BlendShape.setTargetDeltas <mlib.nodes.blendShape.BlendShape.setTargetDeltas>`、:meth:`BlendShape.setTargetWeights <mlib.nodes.blendShape.BlendShape.setTargetWeights>`、:meth:`BoolPlug.toggle <mlib.plugs.boolPlug.BoolPlug.toggle>`、:meth:`Camera.copyViewFrom <mlib.nodes.camera.Camera.copyViewFrom>`、:meth:`Camera.setPoint <mlib.nodes.camera.Camera.setPoint>`、:meth:`Camera.setView <mlib.nodes.camera.Camera.setView>`、:meth:`Constraint.setWeight <mlib.nodes.constraint.Constraint.setWeight>`、:meth:`DagNode.setColor <mlib.nodes.dagNode.DagNode.setColor>`、:meth:`DagNode.setDisplayType <mlib.nodes.dagNode.DagNode.setDisplayType>`、:meth:`DagNode.setShadingOverride <mlib.nodes.dagNode.DagNode.setShadingOverride>`、:meth:`DagNode.setVisibility <mlib.nodes.dagNode.DagNode.setVisibility>`、:meth:`Double3Plug.set <mlib.plugs.double3Plug.Double3Plug.set>`、:meth:`DrivenKey.setKey <mlib.common.drivenKey.DrivenKey.setKey>`、:meth:`GeometryFilter.copyDeformerWeightsTo <mlib.nodes.geometryFilter.GeometryFilter.copyDeformerWeightsTo>`、:meth:`GeometryFilter.loadDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.loadDeformerWeights>`、:meth:`GeometryFilter.setDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.setDeformerWeights>`、:meth:`Joint.connectInverseScale <mlib.nodes.joint.Joint.connectInverseScale>`、:meth:`Joint.delete <mlib.nodes.joint.Joint.delete>`、:meth:`Joint.disconnectInverseScale <mlib.nodes.joint.Joint.disconnectInverseScale>`、:meth:`Joint.resetAttrs <mlib.nodes.joint.Joint.resetAttrs>`、:meth:`Joint.setDegreesOfFreedom <mlib.nodes.joint.Joint.setDegreesOfFreedom>`、:meth:`Joint.setInfluenceLocked <mlib.nodes.joint.Joint.setInfluenceLocked>`、:meth:`Joint.setJointOrient <mlib.nodes.joint.Joint.setJointOrient>`、:meth:`Joint.setPreferredAngle <mlib.nodes.joint.Joint.setPreferredAngle>`、:meth:`Joint.setRadius <mlib.nodes.joint.Joint.setRadius>`、:meth:`Joint.setSegmentScaleCompensate <mlib.nodes.joint.Joint.setSegmentScaleCompensate>`、:meth:`Joints.delete <mlib.nodes.joint.Joints.delete>`、:meth:`Joints.setRadius <mlib.nodes.joint.Joints.setRadius>`、:meth:`Joints.setSegmentScaleCompensate <mlib.nodes.joint.Joints.setSegmentScaleCompensate>`、:meth:`Keyframe.delete <mlib.common.keyframe.Keyframe.delete>`、:meth:`Keyframe.setTangent <mlib.common.keyframe.Keyframe.setTangent>`、:meth:`Keyframe.setValue <mlib.common.keyframe.Keyframe.setValue>`、:meth:`Keyframes.delete <mlib.common.keyframe.Keyframes.delete>`、:meth:`Keyframes.setTangent <mlib.common.keyframe.Keyframes.setTangent>`、:meth:`Keyframes.setValue <mlib.common.keyframe.Keyframes.setValue>`、:meth:`Mesh.removeFaceVertexColors <mlib.nodes.mesh.Mesh.removeFaceVertexColors>`、:meth:`Mesh.reorderVertices <mlib.nodes.mesh.Mesh.reorderVertices>`、:meth:`Mesh.setFaceVertexNormals <mlib.nodes.mesh.Mesh.setFaceVertexNormals>`、:meth:`Mesh.setNormals <mlib.nodes.mesh.Mesh.setNormals>`、:meth:`Mesh.setUVData <mlib.nodes.mesh.Mesh.setUVData>`、:meth:`Mesh.setVertexColors <mlib.nodes.mesh.Mesh.setVertexColors>`、:meth:`MultiPlug.appendMessage <mlib.plugs.multiPlug.MultiPlug.appendMessage>`、:meth:`MultiPlug.removeElement <mlib.plugs.multiPlug.MultiPlug.removeElement>`、:meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`Node.delete <mlib.nodes.node.Node.delete>`、:meth:`Node.rename <mlib.nodes.node.Node.rename>`、:meth:`Node.resetAttrs <mlib.nodes.node.Node.resetAttrs>`、:meth:`Node.setAttrFlags <mlib.nodes.node.Node.setAttrFlags>`、:meth:`Node.setLocked <mlib.nodes.node.Node.setLocked>`、:meth:`Node.setNamespace <mlib.nodes.node.Node.setNamespace>`、:meth:`Nodes.resetAttrs <mlib.nodes.node.Nodes.resetAttrs>`、:meth:`Nodes.setColor <mlib.nodes.node.Nodes.setColor>`、:meth:`Nodes.setColors <mlib.nodes.node.Nodes.setColors>`、:meth:`Nodes.setParent <mlib.nodes.node.Nodes.setParent>`、:meth:`Nodes.setVisibility <mlib.nodes.node.Nodes.setVisibility>`、:meth:`NurbsSurface.setUVData <mlib.nodes.nurbsSurface.NurbsSurface.setUVData>`、:meth:`Place2dTexture.connectTexture <mlib.nodes.place2dTexture.Place2dTexture.connectTexture>`、:meth:`Plug.connect <mlib.plugs.plug.Plug.connect>`、:meth:`Plug.connectTo <mlib.plugs.plug.Plug.connectTo>`、:meth:`Plug.delete <mlib.plugs.plug.Plug.delete>`、:meth:`Plug.disconnect <mlib.plugs.plug.Plug.disconnect>`、:meth:`Plug.disconnectAll <mlib.plugs.plug.Plug.disconnectAll>`、:meth:`Plug.reset <mlib.plugs.plug.Plug.reset>`、:meth:`Plug.set <mlib.plugs.plug.Plug.set>`、:meth:`Plug.setAlias <mlib.plugs.plug.Plug.setAlias>`、:meth:`Plug.setDefault <mlib.plugs.plug.Plug.setDefault>`、:meth:`Plug.setFlags <mlib.plugs.plug.Plug.setFlags>`、:meth:`Plug.setIfChanged <mlib.plugs.plug.Plug.setIfChanged>`、:meth:`Plug.setLocked <mlib.plugs.plug.Plug.setLocked>`、:meth:`PointComponent.setPosition <mlib.components.pointComponent.PointComponent.setPosition>`、:meth:`PointComponents.mirror <mlib.components.pointComponent.PointComponents.mirror>`、:meth:`PointComponents.setPosition <mlib.components.pointComponent.PointComponents.setPosition>`、:meth:`ScalarGraph.condition <mlib.common.scalarGraph.ScalarGraph.condition>`、:meth:`ScalarGraph.multiply <mlib.common.scalarGraph.ScalarGraph.multiply>`、:meth:`ScalarGraph.sum <mlib.common.scalarGraph.ScalarGraph.sum>`、:meth:`ShadingEngine.setShader <mlib.nodes.shadingEngine.ShadingEngine.setShader>`、:meth:`Shape.scaleGeometry <mlib.nodes.shape.Shape.scaleGeometry>`、:meth:`Shape.setParent <mlib.nodes.shape.Shape.setParent>`、:meth:`SkinCluster.importWeights <mlib.nodes.skinCluster.SkinCluster.importWeights>`、:meth:`SkinCluster.limitInfluences <mlib.nodes.skinCluster.SkinCluster.limitInfluences>`、:meth:`SkinCluster.normalizeWeights <mlib.nodes.skinCluster.SkinCluster.normalizeWeights>`、:meth:`SkinCluster.pruneWeights <mlib.nodes.skinCluster.SkinCluster.pruneWeights>`、:meth:`SkinCluster.removeInvalidWeights <mlib.nodes.skinCluster.SkinCluster.removeInvalidWeights>`、:meth:`SkinCluster.roundWeights <mlib.nodes.skinCluster.SkinCluster.roundWeights>`、:meth:`SkinCluster.setBlendWeights <mlib.nodes.skinCluster.SkinCluster.setBlendWeights>`、:meth:`SkinCluster.setInfluencesLocked <mlib.nodes.skinCluster.SkinCluster.setInfluencesLocked>`、:meth:`SkinCluster.setMaxInfluences <mlib.nodes.skinCluster.SkinCluster.setMaxInfluences>`、:meth:`SkinCluster.setWeights <mlib.nodes.skinCluster.SkinCluster.setWeights>`、:meth:`SkinCluster.setWeightsData <mlib.nodes.skinCluster.SkinCluster.setWeightsData>`、:meth:`SkinCluster.transferWeights <mlib.nodes.skinCluster.SkinCluster.transferWeights>`、:meth:`Transform.addShape <mlib.nodes.transform.Transform.addShape>`、:meth:`Transform.centerPivot <mlib.nodes.transform.Transform.centerPivot>`、:meth:`Transform.deleteConstraints <mlib.nodes.transform.Transform.deleteConstraints>`、:meth:`Transform.deleteUnusedIntermediateShapes <mlib.nodes.transform.Transform.deleteUnusedIntermediateShapes>`、:meth:`Transform.mirrorGeometry <mlib.nodes.transform.Transform.mirrorGeometry>`、:meth:`Transform.mirrorTransform <mlib.nodes.transform.Transform.mirrorTransform>`、:meth:`Transform.scaleGeometry <mlib.nodes.transform.Transform.scaleGeometry>`、:meth:`Transform.setMatrix <mlib.nodes.transform.Transform.setMatrix>`、:meth:`Transform.setOffsetParentMatrix <mlib.nodes.transform.Transform.setOffsetParentMatrix>`、:meth:`Transform.setParent <mlib.nodes.transform.Transform.setParent>`、:meth:`Transform.setPivot <mlib.nodes.transform.Transform.setPivot>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、:meth:`Transform.setRotate <mlib.nodes.transform.Transform.setRotate>`、:meth:`Transform.setRotateOrder <mlib.nodes.transform.Transform.setRotateOrder>`、:meth:`Transform.setScale <mlib.nodes.transform.Transform.setScale>`、:meth:`Transform.setShear <mlib.nodes.transform.Transform.setShear>`、:meth:`Transform.setTransformation <mlib.nodes.transform.Transform.setTransformation>`、:meth:`Transform.setTranslation <mlib.nodes.transform.Transform.setTranslation>`、:meth:`UV.setPosition <mlib.components.uv.UV.setPosition>`、:meth:`UVs.setPosition <mlib.components.uv.UVs.setPosition>`、:meth:`Vertex.setColor <mlib.components.vertex.Vertex.setColor>`、:meth:`VertexFace.removeColor <mlib.components.vertexFace.VertexFace.removeColor>`、:meth:`VertexFace.setColor <mlib.components.vertexFace.VertexFace.setColor>`、:meth:`VertexFace.setNormal <mlib.components.vertexFace.VertexFace.setNormal>`、``_ControlPointShape.mirror``、``_ControlPointShape.setPoints``、:func:`createNode <mlib.cmds.createNode.createNode>`、:func:`delete <mlib.cmds.delete.delete>`

.. _argument-force:

``force``
~~~~~~~~~

障害があっても実行する(Maya の force と同じ意味)。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(11): :meth:`Container.removeMembers <mlib.nodes.container.Container.removeMembers>`、:meth:`DagContainer.removeMembers <mlib.nodes.dagContainer.DagContainer.removeMembers>`、:meth:`Joint.connectInverseScale <mlib.nodes.joint.Joint.connectInverseScale>`、:meth:`Place2dTexture.connectTexture <mlib.nodes.place2dTexture.Place2dTexture.connectTexture>`、:meth:`Plug.connect <mlib.plugs.plug.Plug.connect>`、:meth:`Plugin.unload <mlib.common.plugin.Plugin.unload>`、:meth:`Scene.export <mlib.common.scene.Scene.export>`、:meth:`Scene.newFile <mlib.common.scene.Scene.newFile>`、:meth:`Scene.openFile <mlib.common.scene.Scene.openFile>`、:meth:`Scene.save <mlib.common.scene.Scene.save>`、:meth:`SkinCluster.normalizeWeights <mlib.nodes.skinCluster.SkinCluster.normalizeWeights>`

.. _argument-full:

``full``
~~~~~~~~

DAG のフルパスの名前にする。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(6): :meth:`Component.getName <mlib.components.component.Component.getName>`、:meth:`Components.getNames <mlib.components.component.Components.getNames>`、:meth:`Node.getName <mlib.nodes.node.Node.getName>`、:meth:`Nodes.getNames <mlib.nodes.node.Nodes.getNames>`、:meth:`Plug.getName <mlib.plugs.plug.Plug.getName>`、:meth:`Plugs.getNames <mlib.plugs.plug.Plugs.getNames>`

.. _argument-fullWeight:

``fullWeight``
~~~~~~~~~~~~~~

ウェイトが1のときの値。

- 受け方: キーワード専用
- 既定値: ``1.0``
- 使う所(8): :meth:`BlendShape.addTarget <mlib.nodes.blendShape.BlendShape.addTarget>`、:meth:`BlendShape.getTargetDeltas <mlib.nodes.blendShape.BlendShape.getTargetDeltas>`、:meth:`BlendShape.getTargetVertices <mlib.nodes.blendShape.BlendShape.getTargetVertices>`、:meth:`BlendShape.regenerateTarget <mlib.nodes.blendShape.BlendShape.regenerateTarget>`、:meth:`BlendShape.replaceTarget <mlib.nodes.blendShape.BlendShape.replaceTarget>`、:meth:`BlendShape.resetTargetVertices <mlib.nodes.blendShape.BlendShape.resetTargetVertices>`、:meth:`BlendShape.setTargetDeltas <mlib.nodes.blendShape.BlendShape.setTargetDeltas>`、:meth:`BlendShape.targetEdit <mlib.nodes.blendShape.BlendShape.targetEdit>`

.. _argument-geometry:

``geometry``
~~~~~~~~~~~~

対象の形状。

- 受け方: 位置でも渡せる
- 使う所(6): :meth:`BlendShape.addBaseGeometry <mlib.nodes.blendShape.BlendShape.addBaseGeometry>`、:meth:`BlendShape.replaceTarget <mlib.nodes.blendShape.BlendShape.replaceTarget>`、:meth:`GeometryFilter.getGeometryIndices <mlib.nodes.geometryFilter.GeometryFilter.getGeometryIndices>`、:meth:`SkinCluster.deforms <mlib.nodes.skinCluster.SkinCluster.deforms>`、:func:`bindSkin <mlib.cmds.bindSkin.bindSkin>`、:func:`ls <mlib.cmds.ls.ls>`

.. _argument-geometryIndex:

``geometryIndex``
~~~~~~~~~~~~~~~~~

デフォーマーの形状の番号。None は最初の形状。

- 受け方: キーワード専用
- 既定値: ``None``
- 使う所(9): :meth:`GeometryFilter.copyDeformerWeightsTo <mlib.nodes.geometryFilter.GeometryFilter.copyDeformerWeightsTo>`、:meth:`GeometryFilter.dumpDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.dumpDeformerWeights>`、:meth:`GeometryFilter.getDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.getDeformerWeights>`、:meth:`GeometryFilter.getGeometry <mlib.nodes.geometryFilter.GeometryFilter.getGeometry>`、:meth:`GeometryFilter.getGeometryComponents <mlib.nodes.geometryFilter.GeometryFilter.getGeometryComponents>`、:meth:`GeometryFilter.setDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.setDeformerWeights>`、:meth:`SkinCluster.getWeights <mlib.nodes.skinCluster.SkinCluster.getWeights>`、:meth:`SkinCluster.setWeights <mlib.nodes.skinCluster.SkinCluster.setWeights>`、:meth:`SkinCluster.smoothWeights <mlib.nodes.skinCluster.SkinCluster.smoothWeights>`

.. _argument-get:

``get``
~~~~~~~

書き込まずに、書き込む予定の値を返す。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(6): :meth:`Transform.setMatrix <mlib.nodes.transform.Transform.setMatrix>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、:meth:`Transform.setRotate <mlib.nodes.transform.Transform.setRotate>`、:meth:`Transform.setScale <mlib.nodes.transform.Transform.setScale>`、:meth:`Transform.setShear <mlib.nodes.transform.Transform.setShear>`、:meth:`Transform.setTranslation <mlib.nodes.transform.Transform.setTranslation>`

.. _argument-includeSelf:

``includeSelf``
~~~~~~~~~~~~~~~

自身を結果に含める。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(インスタンスの一覧は自身を含む(getInstances は True)、子の一覧は含まない(getChildren は False)のがふつう)
- 型: ``bool``
- 使う所(3): :meth:`DagNode.getChildren <mlib.nodes.dagNode.DagNode.getChildren>`、:meth:`DagNode.getInstances <mlib.nodes.dagNode.DagNode.getInstances>`、:meth:`Transform.getChildren <mlib.nodes.transform.Transform.getChildren>`

.. _argument-index:

``index``
~~~~~~~~~

番号。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(None は全部・自動、番号の既定は対象ごと)
- 受け方の例外: ``Components.pop`` — list.pop と同じ
- 受け方の例外: ``MultiPlug.getElement`` — 主な値(要素の番号)
- 使う所(15): :meth:`AnimCurve.scaleKey <mlib.nodes.animCurve.AnimCurve.scaleKey>`、:meth:`BlendShape.addTarget <mlib.nodes.blendShape.BlendShape.addTarget>`、``Component.__init__``、:meth:`Components.insert <mlib.components.component.Components.insert>`、:meth:`Components.pop <mlib.components.component.Components.pop>`、:meth:`DagNode.getShape <mlib.nodes.dagNode.DagNode.getShape>`、:meth:`DagNode.reorder <mlib.nodes.dagNode.DagNode.reorder>`、``Keyframe.__init__``、:meth:`MultiPlug.getElement <mlib.plugs.multiPlug.MultiPlug.getElement>`、:meth:`MultiPlug.removeElement <mlib.plugs.multiPlug.MultiPlug.removeElement>`、:meth:`Node.getConnections <mlib.nodes.node.Node.getConnections>`、:meth:`Plug.getConnections <mlib.plugs.plug.Plug.getConnections>`、:meth:`Transform.getShape <mlib.nodes.transform.Transform.getShape>`、``_Directories.move``、``_Directories.parentOf``

.. _argument-influence:

``influence``
~~~~~~~~~~~~~

インフルエンス(対象として渡すとき)、またはインフルエンスとして使う側を調べる指定(bool)。

- 受け方: キーワード専用
- 使う所(7): :meth:`DagNode.getBindPoses <mlib.nodes.dagNode.DagNode.getBindPoses>`、:meth:`DagNode.getSkinClusters <mlib.nodes.dagNode.DagNode.getSkinClusters>`、:meth:`Nodes.getSkinClusters <mlib.nodes.node.Nodes.getSkinClusters>`、:meth:`SkinCluster.getInfluenceIndex <mlib.nodes.skinCluster.SkinCluster.getInfluenceIndex>`、:meth:`SkinCluster.getInfluenceVertices <mlib.nodes.skinCluster.SkinCluster.getInfluenceVertices>`、:meth:`SkinCluster.hasInfluence <mlib.nodes.skinCluster.SkinCluster.hasInfluence>`、:meth:`SkinCluster.setDropoffRate <mlib.nodes.skinCluster.SkinCluster.setDropoffRate>`

.. _argument-influenceAssociation:

``influenceAssociation``
~~~~~~~~~~~~~~~~~~~~~~~~

インフルエンスを対応付ける方法の並び。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(コピーとミラーで Maya の既定が違う)
- 使う所(2): :meth:`SkinCluster.copyWeightsTo <mlib.nodes.skinCluster.SkinCluster.copyWeightsTo>`、:meth:`SkinCluster.mirrorWeights <mlib.nodes.skinCluster.SkinCluster.mirrorWeights>`

.. _argument-input:

``input``
~~~~~~~~~

入力側を対象にする(``AnimCurve`` ではカーブの入力の位置で、主な値として位置で渡す)。

- 受け方: キーワード専用
- 使う所(7): :meth:`AnimCurve.addKey <mlib.nodes.animCurve.AnimCurve.addKey>`、:meth:`AnimCurve.evaluate <mlib.nodes.animCurve.AnimCurve.evaluate>`、:meth:`AnimCurve.findClosestIndex <mlib.nodes.animCurve.AnimCurve.findClosestIndex>`、:meth:`GeometryFilter.getGeometry <mlib.nodes.geometryFilter.GeometryFilter.getGeometry>`、:meth:`Keyframe.getValue <mlib.common.keyframe.Keyframe.getValue>`、:meth:`Keyframes.getValues <mlib.common.keyframe.Keyframes.getValues>`、:meth:`Plug.getConnections <mlib.plugs.plug.Plug.getConnections>`

.. _argument-inTangentType:

``inTangentType``
~~~~~~~~~~~~~~~~~

入る側の接線の種類。None は Maya の設定のまま。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 既定値の例外: ``DrivenKey.setKey`` — ドリブンキーは Maya の設定に左右されない linear が既定
- 使う所(4): :meth:`AnimCurve.addKey <mlib.nodes.animCurve.AnimCurve.addKey>`、:meth:`DrivenKey.setKey <mlib.common.drivenKey.DrivenKey.setKey>`、:meth:`Node.setKeyTangent <mlib.nodes.node.Node.setKeyTangent>`、:meth:`Plug.setKeyTangent <mlib.plugs.plug.Plug.setKeyTangent>`

.. _argument-intermediates:

``intermediates``
~~~~~~~~~~~~~~~~~

中間オブジェクトも含める。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(4): :meth:`DagNode.getChildren <mlib.nodes.dagNode.DagNode.getChildren>`、:meth:`DagNode.getShape <mlib.nodes.dagNode.DagNode.getShape>`、:meth:`Transform.getChildren <mlib.nodes.transform.Transform.getChildren>`、:meth:`Transform.getShape <mlib.nodes.transform.Transform.getShape>`

.. _argument-items:

``items``
~~~~~~~~~

対象の並び。None は指定なし。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 使う所(2): ``Selection.__init__``、:meth:`SelectionSnapshot.capture <mlib.json.selectionSnapshot.SelectionSnapshot.capture>`

.. _argument-jointOrient:

``jointOrient``
~~~~~~~~~~~~~~~

jointOrient の値、または jointOrient を対象にする指定。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(値を受けるものと、対象にするかの bool を受けるものがある)
- 使う所(4): :meth:`Transform.getQuaternion <mlib.nodes.transform.Transform.getQuaternion>`、:meth:`Transform.makeIdentity <mlib.nodes.transform.Transform.makeIdentity>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、``Transformation.__init__``

.. _argument-keyable:

``keyable``
~~~~~~~~~~~

キーを打てるかの状態(None は変えない)。

- 受け方: キーワード専用
- 既定値: ``None``
- 使う所(3): :meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`Node.setAttrFlags <mlib.nodes.node.Node.setAttrFlags>`、:meth:`Plug.setFlags <mlib.plugs.plug.Plug.setFlags>`

.. _argument-kind:

``kind``
~~~~~~~~

対象の種類を名前で選ぶ。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(種類を選ぶ引数で、選べる種類と既定はメソッドごとに違う)
- 型: ``str``
- 使う所(26): :meth:`Camera.getDirection <mlib.nodes.camera.Camera.getDirection>`、:meth:`Camera.getFrustum <mlib.nodes.camera.Camera.getFrustum>`、:meth:`Camera.getPoint <mlib.nodes.camera.Camera.getPoint>`、:meth:`Camera.getProjectionMatrix <mlib.nodes.camera.Camera.getProjectionMatrix>`、:meth:`Camera.setDirection <mlib.nodes.camera.Camera.setDirection>`、:meth:`Camera.setPoint <mlib.nodes.camera.Camera.setPoint>`、:meth:`DagNode.getDrawColor <mlib.nodes.dagNode.DagNode.getDrawColor>`、:meth:`DagNode.setDisplayType <mlib.nodes.dagNode.DagNode.setDisplayType>`、:meth:`Face.isKind <mlib.components.face.Face.isKind>`、:meth:`Mesh.copySet <mlib.nodes.mesh.Mesh.copySet>`、:meth:`Mesh.createSet <mlib.nodes.mesh.Mesh.createSet>`、:meth:`Mesh.deleteSet <mlib.nodes.mesh.Mesh.deleteSet>`、:meth:`Mesh.getCurrentSet <mlib.nodes.mesh.Mesh.getCurrentSet>`、:meth:`Mesh.getSetNames <mlib.nodes.mesh.Mesh.getSetNames>`、:meth:`Mesh.renameSet <mlib.nodes.mesh.Mesh.renameSet>`、:meth:`Mesh.setCurrentSet <mlib.nodes.mesh.Mesh.setCurrentSet>`、:meth:`Node.getDgTimer <mlib.nodes.node.Node.getDgTimer>`、:meth:`Plug.getAttributeName <mlib.plugs.plug.Plug.getAttributeName>`、:meth:`ShadingEngine.getShader <mlib.nodes.shadingEngine.ShadingEngine.getShader>`、:meth:`ShadingEngine.setShader <mlib.nodes.shadingEngine.ShadingEngine.setShader>`、:meth:`SkinCluster.getMode <mlib.nodes.skinCluster.SkinCluster.getMode>`、:meth:`SkinCluster.setMode <mlib.nodes.skinCluster.SkinCluster.setMode>`、:meth:`Transform.getPivot <mlib.nodes.transform.Transform.getPivot>`、:meth:`Transform.setPivot <mlib.nodes.transform.Transform.setPivot>`、:func:`createDeformer <mlib.cmds.createDeformer.createDeformer>`、:func:`createPoly <mlib.cmds.createPoly.createPoly>`

.. _argument-layer:

``layer``
~~~~~~~~~

アニメーションレイヤー。None はレイヤーを通さない。

- 受け方: 位置でも渡せる
- 使う所(3): :meth:`Plug.getAnimCurve <mlib.plugs.plug.Plug.getAnimCurve>`、:meth:`Plug.getLayeredPlug <mlib.plugs.plug.Plug.getLayeredPlug>`、:meth:`Transform.addConstraint <mlib.nodes.transform.Transform.addConstraint>`

.. _argument-leaves:

``leaves``
~~~~~~~~~~

コンパウンドアトリビュートの末端の子まで対象にする。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(5): :meth:`DagNode.getChildren <mlib.nodes.dagNode.DagNode.getChildren>`、:meth:`Plug.getDescendants <mlib.plugs.plug.Plug.getDescendants>`、:meth:`Plug.setFlags <mlib.plugs.plug.Plug.setFlags>`、:meth:`Plug.setLocked <mlib.plugs.plug.Plug.setLocked>`、:meth:`Transform.getChildren <mlib.nodes.transform.Transform.getChildren>`

.. _argument-locked:

``locked``
~~~~~~~~~~

ロックの状態(None は変えない・絞り込まない)。

- 受け方: キーワード専用
- 既定値: ``None``
- 使う所(5): :meth:`Mesh.setFaceVertexNormals <mlib.nodes.mesh.Mesh.setFaceVertexNormals>`、:meth:`Node.setAttrFlags <mlib.nodes.node.Node.setAttrFlags>`、:meth:`Plug.setFlags <mlib.plugs.plug.Plug.setFlags>`、:meth:`SkinCluster.getInfluences <mlib.nodes.skinCluster.SkinCluster.getInfluences>`、:meth:`VertexFace.setNormal <mlib.components.vertexFace.VertexFace.setNormal>`

.. _argument-maintain:

``maintain``
~~~~~~~~~~~~

上限を保つ。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(None は今の設定のまま(setMaxInfluences))
- 使う所(2): :meth:`SkinCluster.getMaxInfluences <mlib.nodes.skinCluster.SkinCluster.getMaxInfluences>`、:meth:`SkinCluster.setMaxInfluences <mlib.nodes.skinCluster.SkinCluster.setMaxInfluences>`

.. _argument-maxDistance:

``maxDistance``
~~~~~~~~~~~~~~~

探す距離の上限。None は制限なし。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 使う所(2): :meth:`Mesh.intersect <mlib.nodes.mesh.Mesh.intersect>`、``_PointGrid.nearest``

.. _argument-members:

``members``
~~~~~~~~~~~

対象のメンバーの並び。None は指定なし。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 使う所(3): :meth:`DagPose.reset <mlib.nodes.dagPose.DagPose.reset>`、:func:`createContainer <mlib.cmds.createContainer.createContainer>`、:func:`createDagPose <mlib.cmds.createDagPose.createDagPose>`

.. _argument-method:

``method``
~~~~~~~~~~

処理の方法を名前で選ぶ。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(種類を選ぶ引数で、選べる種類と既定はメソッドごとに違う)
- 使う所(5): :meth:`Mesh.reorderVertices <mlib.nodes.mesh.Mesh.reorderVertices>`、:meth:`Nodes.callEach <mlib.nodes.node.Nodes.callEach>`、:meth:`SkinCluster.importWeights <mlib.nodes.skinCluster.SkinCluster.importWeights>`、:meth:`SkinCluster.setWeightsData <mlib.nodes.skinCluster.SkinCluster.setWeightsData>`、:func:`bindSkin <mlib.cmds.bindSkin.bindSkin>`

.. _argument-missing:

``missing``
~~~~~~~~~~~

無くなった対象の扱い。

- 受け方: キーワード専用
- 使う所(1): :meth:`Selection.select <mlib.common.selection.Selection.select>`

.. _argument-mode:

``mode``
~~~~~~~~

書き込み方・合わせ方を名前で選ぶ。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(種類を選ぶ引数で、選べる種類と既定はメソッドごとに違う)
- 使う所(5): :meth:`AnimationSnapshot.apply <mlib.json.animationSnapshot.AnimationSnapshot.apply>`、:meth:`AnimationSnapshot.validate <mlib.json.animationSnapshot.AnimationSnapshot.validate>`、:meth:`BlendShape.importTargets <mlib.nodes.blendShape.BlendShape.importTargets>`、:meth:`BlendShape.setTargetsData <mlib.nodes.blendShape.BlendShape.setTargetsData>`、:meth:`ObjectSet.combine <mlib.nodes.objectSet.ObjectSet.combine>`

.. _argument-name:

``name``
~~~~~~~~

名前。作るものの名前は None で Maya に任せる。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(名前空間は ``":"`` (ルート)が既定)
- 使う所(56): :meth:`BlendShape.addTarget <mlib.nodes.blendShape.BlendShape.addTarget>`、:meth:`Container.bindAttr <mlib.nodes.container.Container.bindAttr>`、:meth:`Container.createNode <mlib.nodes.container.Container.createNode>`、:meth:`Container.publishAndBind <mlib.nodes.container.Container.publishAndBind>`、:meth:`Container.publishName <mlib.nodes.container.Container.publishName>`、:meth:`Container.unbindAttr <mlib.nodes.container.Container.unbindAttr>`、:meth:`Container.unpublishName <mlib.nodes.container.Container.unpublishName>`、:meth:`DagContainer.bindAttr <mlib.nodes.dagContainer.DagContainer.bindAttr>`、:meth:`DagContainer.createNode <mlib.nodes.dagContainer.DagContainer.createNode>`、:meth:`DagContainer.publishAndBind <mlib.nodes.dagContainer.DagContainer.publishAndBind>`、:meth:`DagContainer.publishName <mlib.nodes.dagContainer.DagContainer.publishName>`、:meth:`DagContainer.unbindAttr <mlib.nodes.dagContainer.DagContainer.unbindAttr>`、:meth:`DagContainer.unpublishName <mlib.nodes.dagContainer.DagContainer.unpublishName>`、:meth:`Mesh.createSet <mlib.nodes.mesh.Mesh.createSet>`、:meth:`Mesh.deleteSet <mlib.nodes.mesh.Mesh.deleteSet>`、:meth:`Mesh.renameSet <mlib.nodes.mesh.Mesh.renameSet>`、:meth:`Mesh.setCurrentSet <mlib.nodes.mesh.Mesh.setCurrentSet>`、:meth:`NameMapping.convert <mlib.json.nameMapping.NameMapping.convert>`、``Namespace.__init__``、:meth:`Namespace.create <mlib.common.namespace.Namespace.create>`、:meth:`Namespace.getNode <mlib.common.namespace.Namespace.getNode>`、:meth:`Namespace.rename <mlib.common.namespace.Namespace.rename>`、:meth:`Node.duplicate <mlib.nodes.node.Node.duplicate>`、:meth:`Node.getPlug <mlib.nodes.node.Node.getPlug>`、:meth:`Node.hasAttr <mlib.nodes.node.Node.hasAttr>`、:meth:`Node.moveAttrOrder <mlib.nodes.node.Node.moveAttrOrder>`、:meth:`Node.rename <mlib.nodes.node.Node.rename>`、``NodeRef.__init__``、:meth:`Plug.getEnumNames <mlib.plugs.plug.Plug.getEnumNames>`、:meth:`Plug.setAlias <mlib.plugs.plug.Plug.setAlias>`、:meth:`Plug.setNiceName <mlib.plugs.plug.Plug.setNiceName>`、``PluginPackage.__init__``、:meth:`SkinCluster.invertShape <mlib.nodes.skinCluster.SkinCluster.invertShape>`、:meth:`Transform.addConstraint <mlib.nodes.transform.Transform.addConstraint>`、``_LayerResolver.resolve``、``_UndoChunk.__init__``、``_VersionedItem.__init__``、:func:`createBlendShape <mlib.cmds.createBlendShape.createBlendShape>`、:func:`createCircle <mlib.cmds.createCircle.createCircle>`、:func:`createContainer <mlib.cmds.createContainer.createContainer>`、:func:`createCurve <mlib.cmds.createCurve.createCurve>`、:func:`createDagPose <mlib.cmds.createDagPose.createDagPose>`、:func:`createDeformer <mlib.cmds.createDeformer.createDeformer>`、:func:`createExpression <mlib.cmds.createExpression.createExpression>`、:func:`createGroup <mlib.cmds.createGroup.createGroup>`、:func:`createIkHandle <mlib.cmds.createIkHandle.createIkHandle>`、:func:`createLocator <mlib.cmds.createLocator.createLocator>`、:func:`createMotionTrail <mlib.cmds.createMotionTrail.createMotionTrail>`、:func:`createNode <mlib.cmds.createNode.createNode>`、:func:`createNurbsPlane <mlib.cmds.createNurbsPlane.createNurbsPlane>`、:func:`createPoly <mlib.cmds.createPoly.createPoly>`、:func:`createShadingEngine <mlib.cmds.createShadingEngine.createShadingEngine>`、:func:`duplicate <mlib.cmds.duplicate.duplicate>`、:func:`legalizeName <mlib.util.legalizeName>`、:func:`undoChunk <mlib.decorator.undoChunk>`、:func:`undoTransaction <mlib.decorator.undoTransaction>`

.. _argument-nameMap:

``nameMap``
~~~~~~~~~~~

名前空間を除いた名前の対応表。

- 受け方: キーワード専用
- 既定値: ``None``
- 型: ``dict[str, str] | None``
- 受け方の例外: ``NameMapping.__init__`` — この3つの指定を持つクラスの作り方
- 使う所(10): :meth:`AnimationSnapshot.apply <mlib.json.animationSnapshot.AnimationSnapshot.apply>`、:meth:`AnimationSnapshot.validate <mlib.json.animationSnapshot.AnimationSnapshot.validate>`、:meth:`BlendShape.importTargets <mlib.nodes.blendShape.BlendShape.importTargets>`、:meth:`BlendShape.setTargetsData <mlib.nodes.blendShape.BlendShape.setTargetsData>`、``NameMapping.__init__``、:meth:`SkinCluster.importWeights <mlib.nodes.skinCluster.SkinCluster.importWeights>`、:meth:`SkinCluster.setWeightsData <mlib.nodes.skinCluster.SkinCluster.setWeightsData>`、:meth:`Snapshot.apply <mlib.json.snapshot.Snapshot.apply>`、:meth:`Snapshot.validate <mlib.json.snapshot.Snapshot.validate>`、:func:`bindSkin <mlib.cmds.bindSkin.bindSkin>`

.. _argument-names:

``names``
~~~~~~~~~

名前の並び。None は指定なし。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 使う所(4): ``Nodes.__init__``、:meth:`Plug.setEnumNames <mlib.plugs.plug.Plug.setEnumNames>`、:meth:`Plugin.removeUnknown <mlib.common.plugin.Plugin.removeUnknown>`、:func:`createJointChain <mlib.cmds.createJointChain.createJointChain>`

.. _argument-namespace:

``namespace``
~~~~~~~~~~~~~

名前空間。None は今のまま・付けない。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 使う所(4): :meth:`Node.setNamespace <mlib.nodes.node.Node.setNamespace>`、:meth:`Scene.importFile <mlib.common.scene.Scene.importFile>`、:meth:`Scene.reference <mlib.common.scene.Scene.reference>`、:func:`createReference <mlib.common.references.createReference>`

.. _argument-namespaceMap:

``namespaceMap``
~~~~~~~~~~~~~~~~

名前空間の対応。

- 受け方: キーワード専用
- 既定値: ``None``
- 型: ``dict[str, str] | None``
- 受け方の例外: ``NameMapping.__init__`` — この3つの指定を持つクラスの作り方
- 使う所(10): :meth:`AnimationSnapshot.apply <mlib.json.animationSnapshot.AnimationSnapshot.apply>`、:meth:`AnimationSnapshot.validate <mlib.json.animationSnapshot.AnimationSnapshot.validate>`、:meth:`BlendShape.importTargets <mlib.nodes.blendShape.BlendShape.importTargets>`、:meth:`BlendShape.setTargetsData <mlib.nodes.blendShape.BlendShape.setTargetsData>`、``NameMapping.__init__``、:meth:`SkinCluster.importWeights <mlib.nodes.skinCluster.SkinCluster.importWeights>`、:meth:`SkinCluster.setWeightsData <mlib.nodes.skinCluster.SkinCluster.setWeightsData>`、:meth:`Snapshot.apply <mlib.json.snapshot.Snapshot.apply>`、:meth:`Snapshot.validate <mlib.json.snapshot.Snapshot.validate>`、:func:`bindSkin <mlib.cmds.bindSkin.bindSkin>`

.. _argument-ndigits:

``ndigits``
~~~~~~~~~~~

丸める小数の桁数。None は整数へ丸める(round と同じ)。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 既定値の例外: ``SkinCluster.roundWeights`` — ウェイトを整数へ丸める使い方は無いので、小数3桁が既定
- 使う所(4): :meth:`EulerRotate.round <mlib.maths.eulerRotate.EulerRotate.round>`、:meth:`SkinCluster.normalizeWeights <mlib.nodes.skinCluster.SkinCluster.normalizeWeights>`、:meth:`SkinCluster.roundWeights <mlib.nodes.skinCluster.SkinCluster.roundWeights>`、:meth:`Vector.round <mlib.maths.vector.Vector.round>`

.. _argument-nodes:

``nodes``
~~~~~~~~~

対象のノードの並び。None は指定なし。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 使う所(10): :meth:`AnimationSnapshot.capture <mlib.json.animationSnapshot.AnimationSnapshot.capture>`、:meth:`AttributesSnapshot.capture <mlib.json.attributesSnapshot.AttributesSnapshot.capture>`、:meth:`DrivenKeysSnapshot.capture <mlib.json.drivenKeysSnapshot.DrivenKeysSnapshot.capture>`、:meth:`PoseSnapshot.capture <mlib.json.poseSnapshot.PoseSnapshot.capture>`、:meth:`Scene.export <mlib.common.scene.Scene.export>`、:func:`bakeResults <mlib.cmds.bakeResults.bakeResults>`、:func:`createGroup <mlib.cmds.createGroup.createGroup>`、:func:`delete <mlib.cmds.delete.delete>`、:func:`findCycles <mlib.cmds.findCycles.findCycles>`、:func:`select <mlib.cmds.select.select>`

.. _argument-normal:

``normal``
~~~~~~~~~~

法線の向き。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(作る円の向きと、書き込む法線)
- 使う所(3): :meth:`Transform.makeIdentity <mlib.nodes.transform.Transform.makeIdentity>`、:meth:`VertexFace.setNormal <mlib.components.vertexFace.VertexFace.setNormal>`、:func:`createCircle <mlib.cmds.createCircle.createCircle>`

.. _argument-normalize:

``normalize``
~~~~~~~~~~~~~

ウェイトを正規化する。

- 受け方: キーワード専用
- 既定値: ``True``
- 型: ``bool``
- 使う所(4): :meth:`SkinCluster.copyWeightsTo <mlib.nodes.skinCluster.SkinCluster.copyWeightsTo>`、:meth:`SkinCluster.mirrorWeights <mlib.nodes.skinCluster.SkinCluster.mirrorWeights>`、:meth:`SkinCluster.pruneWeights <mlib.nodes.skinCluster.SkinCluster.pruneWeights>`、:meth:`SkinCluster.setWeights <mlib.nodes.skinCluster.SkinCluster.setWeights>`

.. _argument-order:

``order``
~~~~~~~~~

回転順序。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(None は今の回転順序のまま)
- 使う所(5): :meth:`EulerRotate.fromYawPitch <mlib.maths.eulerRotate.EulerRotate.fromYawPitch>`、:meth:`Quaternion.asDecomposedEulerRotate <mlib.maths.quaternion.Quaternion.asDecomposedEulerRotate>`、:meth:`Transform.getRotate <mlib.nodes.transform.Transform.getRotate>`、:meth:`Transform.setRotateOrder <mlib.nodes.transform.Transform.setRotateOrder>`、:func:`orderIndex <mlib.maths.eulerRotate.orderIndex>`

.. _argument-outliner:

``outliner``
~~~~~~~~~~~~

描画色でなく、アウトライナーの色を扱う。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(5): :meth:`DagNode.getColor <mlib.nodes.dagNode.DagNode.getColor>`、:meth:`DagNode.setColor <mlib.nodes.dagNode.DagNode.setColor>`、:meth:`Nodes.getColor <mlib.nodes.node.Nodes.getColor>`、:meth:`Nodes.setColor <mlib.nodes.node.Nodes.setColor>`、:meth:`Nodes.setColors <mlib.nodes.node.Nodes.setColors>`

.. _argument-output:

``output``
~~~~~~~~~~

出力側を対象にする(``ShadingEngine.setShader`` はシェーダーの出力のアトリビュート)。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(bool の指定と、出力のアトリビュートの名前)
- 使う所(2): :meth:`Plug.getConnections <mlib.plugs.plug.Plug.getConnections>`、:meth:`ShadingEngine.setShader <mlib.nodes.shadingEngine.ShadingEngine.setShader>`

.. _argument-outTangentType:

``outTangentType``
~~~~~~~~~~~~~~~~~~

出る側の接線の種類。None は Maya の設定のまま。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 既定値の例外: ``DrivenKey.setKey`` — ドリブンキーは Maya の設定に左右されない linear が既定
- 使う所(4): :meth:`AnimCurve.addKey <mlib.nodes.animCurve.AnimCurve.addKey>`、:meth:`DrivenKey.setKey <mlib.common.drivenKey.DrivenKey.setKey>`、:meth:`Node.setKeyTangent <mlib.nodes.node.Node.setKeyTangent>`、:meth:`Plug.setKeyTangent <mlib.plugs.plug.Plug.setKeyTangent>`

.. _argument-parent:

``parent``
~~~~~~~~~~

親。None はワールド直下・指定しない。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(名前空間は ``":"`` (ルート)が既定)
- 使う所(15): :meth:`Namespace.create <mlib.common.namespace.Namespace.create>`、:meth:`Namespace.setParent <mlib.common.namespace.Namespace.setParent>`、:meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`Nodes.setParent <mlib.nodes.node.Nodes.setParent>`、``ScriptJob.__init__``、:meth:`Shape.setParent <mlib.nodes.shape.Shape.setParent>`、:meth:`Transform.setParent <mlib.nodes.transform.Transform.setParent>`、:func:`createCircle <mlib.cmds.createCircle.createCircle>`、:func:`createCurve <mlib.cmds.createCurve.createCurve>`、:func:`createGroup <mlib.cmds.createGroup.createGroup>`、:func:`createJointChain <mlib.cmds.createJointChain.createJointChain>`、:func:`createLocator <mlib.cmds.createLocator.createLocator>`、:func:`createNode <mlib.cmds.createNode.createNode>`、:func:`createNurbsPlane <mlib.cmds.createNurbsPlane.createNurbsPlane>`、:func:`createPoly <mlib.cmds.createPoly.createPoly>`

.. _argument-path:

``path``
~~~~~~~~

ファイルのパス。

- 型: ``str | os.PathLike``
- 使う所(12): :meth:`BlendShape.exportTargets <mlib.nodes.blendShape.BlendShape.exportTargets>`、:meth:`BlendShape.importTargets <mlib.nodes.blendShape.BlendShape.importTargets>`、:meth:`GeometryFilter.dumpDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.dumpDeformerWeights>`、:meth:`GeometryFilter.loadDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.loadDeformerWeights>`、:meth:`Reference.replaceFile <mlib.nodes.reference.Reference.replaceFile>`、:meth:`SkinCluster.exportWeights <mlib.nodes.skinCluster.SkinCluster.exportWeights>`、:meth:`SkinCluster.importWeights <mlib.nodes.skinCluster.SkinCluster.importWeights>`、:meth:`Snapshot.load <mlib.json.snapshot.Snapshot.load>`、:meth:`Snapshot.save <mlib.json.snapshot.Snapshot.save>`、:meth:`Transform.exportCurveShapes <mlib.nodes.transform.Transform.exportCurveShapes>`、:meth:`Transform.importCurveShapes <mlib.nodes.transform.Transform.importCurveShapes>`、:func:`createReference <mlib.common.references.createReference>`

.. _argument-perFace:

``perFace``
~~~~~~~~~~~

頂点ごとでなく、面頂点ごとに扱う。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(4): :meth:`Mesh.getShadingEngines <mlib.nodes.mesh.Mesh.getShadingEngines>`、:meth:`Mesh.getVertexColors <mlib.nodes.mesh.Mesh.getVertexColors>`、:meth:`Mesh.getVertexNormals <mlib.nodes.mesh.Mesh.getVertexNormals>`、:meth:`Mesh.setVertexColors <mlib.nodes.mesh.Mesh.setVertexColors>`

.. _argument-position:

``position``
~~~~~~~~~~~~

位置の値、または位置を対象にする指定。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(値を受けるものと、対象にするかの bool を受けるものがある)
- 使う所(4): :meth:`Matrix.fromAim <mlib.maths.matrix.Matrix.fromAim>`、:meth:`Matrix.fromAxes <mlib.maths.matrix.Matrix.fromAxes>`、:meth:`RampPlug.getValueAt <mlib.plugs.rampPlug.RampPlug.getValueAt>`、:meth:`Transform.matchTransform <mlib.nodes.transform.Transform.matchTransform>`

.. _argument-preserve:

``preserve``
~~~~~~~~~~~~

変えたあとも見た目(ワールドの姿勢)を保つ。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(setRotateOrder は省けない(回転順序だけ変えるのか向きを保つのかで結果が大きく違う)、setQuaternion は False)
- 使う所(3): :meth:`Transform.setPivot <mlib.nodes.transform.Transform.setPivot>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、:meth:`Transform.setRotateOrder <mlib.nodes.transform.Transform.setRotateOrder>`

.. _argument-radius:

``radius``
~~~~~~~~~~

半径。

- 受け方: 位置でも渡せる
- 使う所(2): :func:`createCircle <mlib.cmds.createCircle.createCircle>`、:func:`createPoly <mlib.cmds.createPoly.createPoly>`

.. _argument-relative:

``relative``
~~~~~~~~~~~~

今の値からの相対で変える。

- 受け方: キーワード専用
- 既定値: ``False``
- 既定値の例外: ``DagNode.reorder`` — cmds.reorder -relative のフラグ名(動かす数)
- 使う所(14): :meth:`BlendShape.addTarget <mlib.nodes.blendShape.BlendShape.addTarget>`、:meth:`DagNode.reorder <mlib.nodes.dagNode.DagNode.reorder>`、:meth:`Nodes.setParent <mlib.nodes.node.Nodes.setParent>`、:meth:`PointComponent.setPosition <mlib.components.pointComponent.PointComponent.setPosition>`、:meth:`PointComponents.setPosition <mlib.components.pointComponent.PointComponents.setPosition>`、:meth:`Shape.setParent <mlib.nodes.shape.Shape.setParent>`、:meth:`Transform.setParent <mlib.nodes.transform.Transform.setParent>`、:meth:`Transform.setRotate <mlib.nodes.transform.Transform.setRotate>`、:meth:`Transform.setScale <mlib.nodes.transform.Transform.setScale>`、:meth:`Transform.setShear <mlib.nodes.transform.Transform.setShear>`、:meth:`Transform.setTranslation <mlib.nodes.transform.Transform.setTranslation>`、:meth:`UV.setPosition <mlib.components.uv.UV.setPosition>`、:meth:`UVs.setPosition <mlib.components.uv.UVs.setPosition>`、:func:`createDeformer <mlib.cmds.createDeformer.createDeformer>`

.. _argument-removeInfluence:

``removeInfluence``
~~~~~~~~~~~~~~~~~~~

skinCluster のインフルエンスから外してから削除する。

- 受け方: キーワード専用
- 使う所(3): :meth:`Joint.delete <mlib.nodes.joint.Joint.delete>`、:meth:`Joints.delete <mlib.nodes.joint.Joints.delete>`、:meth:`Node.delete <mlib.nodes.node.Node.delete>`

.. _argument-removeNamespace:

``removeNamespace``
~~~~~~~~~~~~~~~~~~~

名前空間を取り除く。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(7): :meth:`Component.getName <mlib.components.component.Component.getName>`、:meth:`Components.getNames <mlib.components.component.Components.getNames>`、:meth:`Node.getName <mlib.nodes.node.Node.getName>`、:meth:`Nodes.getNames <mlib.nodes.node.Nodes.getNames>`、:meth:`Plug.getName <mlib.plugs.plug.Plug.getName>`、:meth:`Plugs.getNames <mlib.plugs.plug.Plugs.getNames>`、:meth:`Reference.importContents <mlib.nodes.reference.Reference.importContents>`

.. _argument-repair:

``repair``
~~~~~~~~~~

不正なウェイトを直してから処理する。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(6): :meth:`Joint.delete <mlib.nodes.joint.Joint.delete>`、:meth:`Joint.removeInfluence <mlib.nodes.joint.Joint.removeInfluence>`、:meth:`Joints.delete <mlib.nodes.joint.Joints.delete>`、:meth:`Joints.removeInfluence <mlib.nodes.joint.Joints.removeInfluence>`、:meth:`Node.delete <mlib.nodes.node.Node.delete>`、:meth:`SkinCluster.removeInfluences <mlib.nodes.skinCluster.SkinCluster.removeInfluences>`

.. _argument-replace:

``replace``
~~~~~~~~~~~

順に当てる文字列の置き換え(``select`` では今の選択を置き換える指定)。

- 受け方: キーワード専用
- 既定値: ``None``
- 受け方の例外: ``NameMapping.__init__`` — この3つの指定を持つクラスの作り方
- 使う所(11): :meth:`AnimationSnapshot.apply <mlib.json.animationSnapshot.AnimationSnapshot.apply>`、:meth:`AnimationSnapshot.validate <mlib.json.animationSnapshot.AnimationSnapshot.validate>`、:meth:`BlendShape.importTargets <mlib.nodes.blendShape.BlendShape.importTargets>`、:meth:`BlendShape.setTargetsData <mlib.nodes.blendShape.BlendShape.setTargetsData>`、``NameMapping.__init__``、:meth:`SkinCluster.importWeights <mlib.nodes.skinCluster.SkinCluster.importWeights>`、:meth:`SkinCluster.setWeightsData <mlib.nodes.skinCluster.SkinCluster.setWeightsData>`、:meth:`Snapshot.apply <mlib.json.snapshot.Snapshot.apply>`、:meth:`Snapshot.validate <mlib.json.snapshot.Snapshot.validate>`、:func:`bindSkin <mlib.cmds.bindSkin.bindSkin>`、:func:`select <mlib.cmds.select.select>`

.. _argument-rotate:

``rotate``
~~~~~~~~~~

回転の値、または回転を対象にする指定。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(値を受けるものと、対象にするかの bool を受けるものがある)
- 使う所(6): ``Matrix.__init__``、:meth:`Matrix.compose <mlib.maths.matrix.Matrix.compose>`、:meth:`Transform.getQuaternion <mlib.nodes.transform.Transform.getQuaternion>`、:meth:`Transform.makeIdentity <mlib.nodes.transform.Transform.makeIdentity>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、``Transformation.__init__``

.. _argument-rotateAxis:

``rotateAxis``
~~~~~~~~~~~~~~

rotateAxis の値、または rotateAxis を対象にする指定。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(値を受けるものと、対象にするかの bool を受けるものがある)
- 使う所(3): :meth:`Transform.getQuaternion <mlib.nodes.transform.Transform.getQuaternion>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、``Transformation.__init__``

.. _argument-safe:

``safe``
~~~~~~~~

失敗しても例外にしない。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 説明の決まり文句: Trueなら、失敗しても例外にしない。既定はFalse。
- 使う所(8): :meth:`Double3Plug.set <mlib.plugs.double3Plug.Double3Plug.set>`、:meth:`Plug.set <mlib.plugs.plug.Plug.set>`、:meth:`Transform.setMatrix <mlib.nodes.transform.Transform.setMatrix>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、:meth:`Transform.setRotate <mlib.nodes.transform.Transform.setRotate>`、:meth:`Transform.setScale <mlib.nodes.transform.Transform.setScale>`、:meth:`Transform.setShear <mlib.nodes.transform.Transform.setShear>`、:meth:`Transform.setTranslation <mlib.nodes.transform.Transform.setTranslation>`

.. _argument-scale:

``scale``
~~~~~~~~~

スケールの値、またはスケールを対象にする指定。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(値を受けるものと、対象にするかの bool を受けるものがある)
- 使う所(7): ``Matrix.__init__``、:meth:`Matrix.compose <mlib.maths.matrix.Matrix.compose>`、:meth:`Shape.scaleGeometry <mlib.nodes.shape.Shape.scaleGeometry>`、:meth:`Transform.makeIdentity <mlib.nodes.transform.Transform.makeIdentity>`、:meth:`Transform.matchTransform <mlib.nodes.transform.Transform.matchTransform>`、:meth:`Transform.scaleGeometry <mlib.nodes.transform.Transform.scaleGeometry>`、``Transformation.__init__``

.. _argument-shear:

``shear``
~~~~~~~~~

シアーの値、またはシアーを対象にする指定。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(値を受けるものと、対象にするかの bool を受けるものがある)
- 使う所(3): ``Matrix.__init__``、:meth:`Matrix.compose <mlib.maths.matrix.Matrix.compose>`、``Transformation.__init__``

.. _argument-skipConnected:

``skipConnected``
~~~~~~~~~~~~~~~~~

接続があるノードは削除しない。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 説明の決まり文句: Trueなら、接続があるノードは削除しない。既定はFalse。
- 使う所(3): :meth:`Joint.delete <mlib.nodes.joint.Joint.delete>`、:meth:`Joints.delete <mlib.nodes.joint.Joints.delete>`、:meth:`Node.delete <mlib.nodes.node.Node.delete>`

.. _argument-skipExisting:

``skipExisting``
~~~~~~~~~~~~~~~~

すでに目的の状態なら何もしない。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 説明の決まり文句: Trueなら、すでに目的の状態のときは何もしない。既定はFalse。
- 使う所(5): :meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`Plug.connect <mlib.plugs.plug.Plug.connect>`、:meth:`Plug.connectTo <mlib.plugs.plug.Plug.connectTo>`、:meth:`Plug.setAlias <mlib.plugs.plug.Plug.setAlias>`、:meth:`Plugin.load <mlib.common.plugin.Plugin.load>`

.. _argument-sortBy:

``sortBy``
~~~~~~~~~~

並べる順。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(選べる順がメソッドごとに違う)
- 使う所(3): :meth:`DagNode.getChildren <mlib.nodes.dagNode.DagNode.getChildren>`、:meth:`Transform.getChildren <mlib.nodes.transform.Transform.getChildren>`、:func:`listReferences <mlib.common.references.listReferences>`

.. _argument-source:

``source``
~~~~~~~~~~

入力側を対象にする指定(bool)、または元になるもの。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(接続の向きの bool と、元になるものの指定)
- 使う所(9): :meth:`Joint.connectInverseScale <mlib.nodes.joint.Joint.connectInverseScale>`、:meth:`Mesh.copySet <mlib.nodes.mesh.Mesh.copySet>`、:meth:`Node.getConnections <mlib.nodes.node.Node.getConnections>`、:meth:`Plug.connect <mlib.plugs.plug.Plug.connect>`、:meth:`Plug.disconnectAll <mlib.plugs.plug.Plug.disconnectAll>`、:meth:`Plug.getConnections <mlib.plugs.plug.Plug.getConnections>`、:meth:`Plug.isConnected <mlib.plugs.plug.Plug.isConnected>`、:meth:`Transform.replaceShapes <mlib.nodes.transform.Transform.replaceShapes>`、:func:`bakeDeformer <mlib.cmds.bakeDeformer.bakeDeformer>`

.. _argument-start:

``start``
~~~~~~~~~

始まりの番号・値。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(list.index の始まりと、空きを探し始める番号)
- 使う所(4): :meth:`Components.index <mlib.components.component.Components.index>`、:meth:`MultiPlug.getNextAvailable <mlib.plugs.multiPlug.MultiPlug.getNextAvailable>`、:meth:`Time.setRange <mlib.common.sceneTime.Time.setRange>`、``_InterpCacheConstraint.createCache``

.. _argument-state:

``state``
~~~~~~~~~

オン・オフを設定する値。

- 受け方: 位置でも渡せる
- 既定値: ``True``
- 使う所(20): :meth:`BlendShape.targetEdit <mlib.nodes.blendShape.BlendShape.targetEdit>`、:meth:`Camera.setVerticalLocked <mlib.nodes.camera.Camera.setVerticalLocked>`、:meth:`DagNode.setShadingOverride <mlib.nodes.dagNode.DagNode.setShadingOverride>`、:meth:`DagNode.setVisibility <mlib.nodes.dagNode.DagNode.setVisibility>`、:meth:`Edge.setSmooth <mlib.components.edge.Edge.setSmooth>`、:meth:`Joint.setInfluenceLocked <mlib.nodes.joint.Joint.setInfluenceLocked>`、:meth:`Joint.setSegmentScaleCompensate <mlib.nodes.joint.Joint.setSegmentScaleCompensate>`、:meth:`Joints.setSegmentScaleCompensate <mlib.nodes.joint.Joints.setSegmentScaleCompensate>`、:meth:`Keyframe.setBreakdown <mlib.common.keyframe.Keyframe.setBreakdown>`、:meth:`Keyframes.setBreakdown <mlib.common.keyframe.Keyframes.setBreakdown>`、:meth:`Node.setDgTimer <mlib.nodes.node.Node.setDgTimer>`、:meth:`Node.setDgTimingEnabled <mlib.nodes.node.Node.setDgTimingEnabled>`、:meth:`Node.setLocked <mlib.nodes.node.Node.setLocked>`、:meth:`Nodes.setVisibility <mlib.nodes.node.Nodes.setVisibility>`、:meth:`Plug.setLocked <mlib.plugs.plug.Plug.setLocked>`、:meth:`Plug.setMuted <mlib.plugs.plug.Plug.setMuted>`、:meth:`Reference.setLoaded <mlib.nodes.reference.Reference.setLoaded>`、:meth:`Reference.setReferenceLocked <mlib.nodes.reference.Reference.setReferenceLocked>`、:meth:`SkinCluster.setInfluencesLocked <mlib.nodes.skinCluster.SkinCluster.setInfluencesLocked>`、:meth:`SkinCluster.setMoveJointsMode <mlib.nodes.skinCluster.SkinCluster.setMoveJointsMode>`

.. _argument-threshold:

``threshold``
~~~~~~~~~~~~~

しきい値。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(比べるものがメソッドごとに違う)
- 使う所(3): :meth:`SkinCluster.getInfluenceVertices <mlib.nodes.skinCluster.SkinCluster.getInfluenceVertices>`、:meth:`SkinCluster.pruneWeights <mlib.nodes.skinCluster.SkinCluster.pruneWeights>`、:meth:`SkinCluster.smoothWeights <mlib.nodes.skinCluster.SkinCluster.smoothWeights>`

.. _argument-time:

``time``
~~~~~~~~

時刻・時刻の範囲。None は絞らない。

- 受け方: キーワード専用
- 既定値: ``None``
- 受け方の例外: ``bakeResults`` — cmds.bakeResults の主な値(対象・アトリビュート・範囲)を順に受ける
- 使う所(16): :meth:`AnimCurve.getKeyframes <mlib.nodes.animCurve.AnimCurve.getKeyframes>`、:meth:`AnimCurve.reduceKeys <mlib.nodes.animCurve.AnimCurve.reduceKeys>`、:meth:`AnimCurve.scaleKey <mlib.nodes.animCurve.AnimCurve.scaleKey>`、:meth:`AnimationSnapshot.capture <mlib.json.animationSnapshot.AnimationSnapshot.capture>`、:meth:`CompoundPlug.get <mlib.plugs.compoundPlug.CompoundPlug.get>`、:meth:`Double3Plug.get <mlib.plugs.double3Plug.Double3Plug.get>`、:meth:`MatrixPlug.get <mlib.plugs.matrixPlug.MatrixPlug.get>`、:meth:`MultiPlug.get <mlib.plugs.multiPlug.MultiPlug.get>`、:meth:`Node.moveKey <mlib.nodes.node.Node.moveKey>`、:meth:`Node.removeKey <mlib.nodes.node.Node.removeKey>`、:meth:`Node.setKeyTangent <mlib.nodes.node.Node.setKeyTangent>`、:meth:`Plug.get <mlib.plugs.plug.Plug.get>`、:meth:`Plug.moveKey <mlib.plugs.plug.Plug.moveKey>`、:meth:`Plug.removeKey <mlib.plugs.plug.Plug.removeKey>`、:meth:`Plug.setKeyTangent <mlib.plugs.plug.Plug.setKeyTangent>`、:func:`bakeResults <mlib.cmds.bakeResults.bakeResults>`

.. _argument-timeOffset:

``timeOffset``
~~~~~~~~~~~~~~

時刻へ足す値。

- 受け方: キーワード専用
- 既定値: ``0``
- 使う所(6): :meth:`AnimationSnapshot.apply <mlib.json.animationSnapshot.AnimationSnapshot.apply>`、:meth:`AnimationSnapshot.validate <mlib.json.animationSnapshot.AnimationSnapshot.validate>`、:meth:`Keyframe.move <mlib.common.keyframe.Keyframe.move>`、:meth:`Keyframes.move <mlib.common.keyframe.Keyframes.move>`、:meth:`Node.moveKey <mlib.nodes.node.Node.moveKey>`、:meth:`Plug.moveKey <mlib.plugs.plug.Plug.moveKey>`

.. _argument-timeUnit:

``timeUnit``
~~~~~~~~~~~~

時間の数値の単位(``"frame"`` は今のUIの時間単位のフレーム、``"sec"`` は秒)。

- 受け方: キーワード専用
- 既定値: ``'frame'``
- 型: ``str``
- 既定値の例外: ``CompoundPlug.get``・``Double3Plug.get``・``Double3Plug.set``・``MatrixPlug.get``・``MultiPlug.get``・``Plug.get``・``Plug.getDefault``・``Plug.getRange``・``Plug.moveKey``・``Plug.removeKey``・``Plug.set``・``Plug.setKey``・``Plug.setKeyTangent``・``Plug.setRange`` — None は「指定しない」。アトリビュートが時間ならフレーム(時間でないのに指定したら TypeError にするため)
- 使う所(42): :meth:`AnimCurve.addKey <mlib.nodes.animCurve.AnimCurve.addKey>`、:meth:`AnimCurve.addKeys <mlib.nodes.animCurve.AnimCurve.addKeys>`、:meth:`AnimCurve.evaluate <mlib.nodes.animCurve.AnimCurve.evaluate>`、:meth:`AnimCurve.findClosestIndex <mlib.nodes.animCurve.AnimCurve.findClosestIndex>`、:meth:`AnimCurve.getKeyInputs <mlib.nodes.animCurve.AnimCurve.getKeyInputs>`、:meth:`AnimCurve.getKeyValues <mlib.nodes.animCurve.AnimCurve.getKeyValues>`、:meth:`AnimCurve.getKeyframes <mlib.nodes.animCurve.AnimCurve.getKeyframes>`、:meth:`AnimCurve.reduceKeys <mlib.nodes.animCurve.AnimCurve.reduceKeys>`、:meth:`AnimCurve.replaceKeys <mlib.nodes.animCurve.AnimCurve.replaceKeys>`、:meth:`AnimCurve.scaleKey <mlib.nodes.animCurve.AnimCurve.scaleKey>`、:meth:`Callbacks.addTimeChangeCallback <mlib.common.callbacks.Callbacks.addTimeChangeCallback>`、:meth:`CompoundPlug.get <mlib.plugs.compoundPlug.CompoundPlug.get>`、:meth:`Double3Plug.get <mlib.plugs.double3Plug.Double3Plug.get>`、:meth:`Double3Plug.set <mlib.plugs.double3Plug.Double3Plug.set>`、:meth:`DrivenKey.setKey <mlib.common.drivenKey.DrivenKey.setKey>`、:meth:`Keyframe.getValue <mlib.common.keyframe.Keyframe.getValue>`、:meth:`Keyframe.move <mlib.common.keyframe.Keyframe.move>`、:meth:`Keyframe.setValue <mlib.common.keyframe.Keyframe.setValue>`、:meth:`Keyframes.getValues <mlib.common.keyframe.Keyframes.getValues>`、:meth:`Keyframes.move <mlib.common.keyframe.Keyframes.move>`、:meth:`Keyframes.setValue <mlib.common.keyframe.Keyframes.setValue>`、:meth:`MatrixPlug.get <mlib.plugs.matrixPlug.MatrixPlug.get>`、:meth:`MultiPlug.get <mlib.plugs.multiPlug.MultiPlug.get>`、:meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`Node.moveKey <mlib.nodes.node.Node.moveKey>`、:meth:`Node.removeKey <mlib.nodes.node.Node.removeKey>`、:meth:`Node.setKey <mlib.nodes.node.Node.setKey>`、:meth:`Node.setKeyTangent <mlib.nodes.node.Node.setKeyTangent>`、:meth:`Plug.get <mlib.plugs.plug.Plug.get>`、:meth:`Plug.getDefault <mlib.plugs.plug.Plug.getDefault>`、:meth:`Plug.getRange <mlib.plugs.plug.Plug.getRange>`、:meth:`Plug.moveKey <mlib.plugs.plug.Plug.moveKey>`、:meth:`Plug.removeKey <mlib.plugs.plug.Plug.removeKey>`、:meth:`Plug.set <mlib.plugs.plug.Plug.set>`、:meth:`Plug.setKey <mlib.plugs.plug.Plug.setKey>`、:meth:`Plug.setKeyTangent <mlib.plugs.plug.Plug.setKeyTangent>`、:meth:`Plug.setRange <mlib.plugs.plug.Plug.setRange>`、:meth:`Time.getCurrent <mlib.common.sceneTime.Time.getCurrent>`、:meth:`Time.getRange <mlib.common.sceneTime.Time.getRange>`、:meth:`Time.setCurrent <mlib.common.sceneTime.Time.setCurrent>`、:meth:`Time.setRange <mlib.common.sceneTime.Time.setRange>`、``_InterpCacheConstraint.createCache``

.. _argument-to:

``to``
~~~~~~

終わりのノード・移す先。

- 受け方: 位置でも渡せる
- 使う所(2): :meth:`Joint.getChainFromHere <mlib.nodes.joint.Joint.getChainFromHere>`、:func:`duplicate <mlib.cmds.duplicate.duplicate>`

.. _argument-tolerance:

``tolerance``
~~~~~~~~~~~~~

同じとみなす誤差。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(比べるものが違う: 数学の値は 1e-10、Maya の関数へ渡すものは Maya の既定(1e-6・1e-7)、頂点の対応付けは形状の大きさ(0.01)。None と 0.0 は誤差で絞らない)
- 受け方の例外: ``EulerRotate.isEquivalent``・``EulerRotate.isGimbalLocked``・``Matrix.hasNonUniformScale``・``Matrix.isEquivalent``・``Matrix.isIdentity``・``Transformation.isEquivalent``・``Vector.isEquivalent``・``Vector.isPlanar``・``Vector.isZero`` — 数学型は om2 と同じ位置引数のまま
- 使う所(22): :meth:`BlendShape.getTargetVertices <mlib.nodes.blendShape.BlendShape.getTargetVertices>`、:meth:`BlendShape.resetTargetVertices <mlib.nodes.blendShape.BlendShape.resetTargetVertices>`、:meth:`EulerRotate.isEquivalent <mlib.maths.eulerRotate.EulerRotate.isEquivalent>`、:meth:`EulerRotate.isGimbalLocked <mlib.maths.eulerRotate.EulerRotate.isGimbalLocked>`、:meth:`Face.getPointAtUV <mlib.components.face.Face.getPointAtUV>`、:meth:`Face.isKind <mlib.components.face.Face.isKind>`、:meth:`Matrix.hasNonUniformScale <mlib.maths.matrix.Matrix.hasNonUniformScale>`、:meth:`Matrix.isEquivalent <mlib.maths.matrix.Matrix.isEquivalent>`、:meth:`Matrix.isIdentity <mlib.maths.matrix.Matrix.isIdentity>`、:meth:`Mesh.getMirrorVertexMap <mlib.nodes.mesh.Mesh.getMirrorVertexMap>`、:meth:`Mesh.getPointsAtUV <mlib.nodes.mesh.Mesh.getPointsAtUV>`、:meth:`Mesh.reorderVertices <mlib.nodes.mesh.Mesh.reorderVertices>`、:meth:`NurbsCurve.getCollocatedCVGroups <mlib.nodes.nurbsCurve.NurbsCurve.getCollocatedCVGroups>`、:meth:`NurbsCurve.getLength <mlib.nodes.nurbsCurve.NurbsCurve.getLength>`、:meth:`NurbsCurve.getParam <mlib.nodes.nurbsCurve.NurbsCurve.getParam>`、:meth:`NurbsCurve.isPointOnCurve <mlib.nodes.nurbsCurve.NurbsCurve.isPointOnCurve>`、:meth:`NurbsSurface.getRayIntersection <mlib.nodes.nurbsSurface.NurbsSurface.getRayIntersection>`、:meth:`NurbsSurface.isPointOnSurface <mlib.nodes.nurbsSurface.NurbsSurface.isPointOnSurface>`、:meth:`Transformation.isEquivalent <mlib.maths.transformation.Transformation.isEquivalent>`、:meth:`Vector.isEquivalent <mlib.maths.vector.Vector.isEquivalent>`、:meth:`Vector.isPlanar <mlib.maths.vector.Vector.isPlanar>`、:meth:`Vector.isZero <mlib.maths.vector.Vector.isZero>`

.. _argument-toShape:

``toShape``
~~~~~~~~~~~

Transform でなく、その Shape の色を扱う。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(5): :meth:`DagNode.getColor <mlib.nodes.dagNode.DagNode.getColor>`、:meth:`DagNode.setColor <mlib.nodes.dagNode.DagNode.setColor>`、:meth:`Nodes.getColor <mlib.nodes.node.Nodes.getColor>`、:meth:`Nodes.setColor <mlib.nodes.node.Nodes.setColor>`、:meth:`Nodes.setColors <mlib.nodes.node.Nodes.setColors>`

.. _argument-transferToParent:

``transferToParent``
~~~~~~~~~~~~~~~~~~~~

外すインフルエンスのウェイトを親へ移す。

- 受け方: キーワード専用
- 既定値: ``True``
- 型: ``bool``
- 使う所(6): :meth:`Joint.delete <mlib.nodes.joint.Joint.delete>`、:meth:`Joint.removeInfluence <mlib.nodes.joint.Joint.removeInfluence>`、:meth:`Joints.delete <mlib.nodes.joint.Joints.delete>`、:meth:`Joints.removeInfluence <mlib.nodes.joint.Joints.removeInfluence>`、:meth:`Node.delete <mlib.nodes.node.Node.delete>`、:meth:`SkinCluster.removeInfluences <mlib.nodes.skinCluster.SkinCluster.removeInfluences>`

.. _argument-translate:

``translate``
~~~~~~~~~~~~~

移動の値、または移動を対象にする指定。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(値を受けるものと、対象にするかの bool を受けるものがある)
- 使う所(4): ``Matrix.__init__``、:meth:`Matrix.compose <mlib.maths.matrix.Matrix.compose>`、:meth:`Transform.makeIdentity <mlib.nodes.transform.Transform.makeIdentity>`、``Transformation.__init__``

.. _argument-type:

``type``
~~~~~~~~

ノード型・アトリビュートの型・返すコンポーネントの種類。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(絞り込みの None と、返す種類の既定がメソッドごとに違う)
- 受け方の例外: ``Node.addAttr`` — Maya のフラグをそのまま受ける入口。名前と型を続けて書く
- 受け方の例外: ``NodeRef.__init__`` — 保存する値を並べる作り方
- 使う所(24): ``ComponentRef.__init__``、:meth:`Container.createNode <mlib.nodes.container.Container.createNode>`、:meth:`DagContainer.createNode <mlib.nodes.dagContainer.DagContainer.createNode>`、:meth:`DagNode.getChildren <mlib.nodes.dagNode.DagNode.getChildren>`、:meth:`Edge.getConnected <mlib.components.edge.Edge.getConnected>`、:meth:`Face.getConnected <mlib.components.face.Face.getConnected>`、:meth:`Mesh.getBorder <mlib.nodes.mesh.Mesh.getBorder>`、:meth:`Namespace.getNodes <mlib.common.namespace.Namespace.getNodes>`、:meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`Node.getConnections <mlib.nodes.node.Node.getConnections>`、:meth:`Node.getHistory <mlib.nodes.node.Node.getHistory>`、:meth:`Node.getSets <mlib.nodes.node.Node.getSets>`、:meth:`Node.isType <mlib.nodes.node.Node.isType>`、``NodeRef.__init__``、:meth:`Plug.getConnections <mlib.plugs.plug.Plug.getConnections>`、:meth:`Plugin.ensureNodePlugin <mlib.common.plugin.Plugin.ensureNodePlugin>`、:meth:`Selection.filter <mlib.common.selection.Selection.filter>`、:meth:`Selection.getNodes <mlib.common.selection.Selection.getNodes>`、:meth:`Transform.addConstraint <mlib.nodes.transform.Transform.addConstraint>`、:meth:`Transform.getChildren <mlib.nodes.transform.Transform.getChildren>`、:meth:`Vertex.getConnected <mlib.components.vertex.Vertex.getConnected>`、:func:`createNode <mlib.cmds.createNode.createNode>`、:func:`isNodeType <mlib.cmds.isNodeType.isNodeType>`、:func:`ls <mlib.cmds.ls.ls>`

.. _argument-uiUnits:

``uiUnits``
~~~~~~~~~~~

今のUIの単位の数値で受け渡しする。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(12): :meth:`CompoundPlug.get <mlib.plugs.compoundPlug.CompoundPlug.get>`、:meth:`Double3Plug.get <mlib.plugs.double3Plug.Double3Plug.get>`、:meth:`Double3Plug.set <mlib.plugs.double3Plug.Double3Plug.set>`、:meth:`MatrixPlug.get <mlib.plugs.matrixPlug.MatrixPlug.get>`、:meth:`MultiPlug.get <mlib.plugs.multiPlug.MultiPlug.get>`、:meth:`Node.setKey <mlib.nodes.node.Node.setKey>`、:meth:`Plug.get <mlib.plugs.plug.Plug.get>`、:meth:`Plug.getDefault <mlib.plugs.plug.Plug.getDefault>`、:meth:`Plug.getRange <mlib.plugs.plug.Plug.getRange>`、:meth:`Plug.set <mlib.plugs.plug.Plug.set>`、:meth:`Plug.setDefault <mlib.plugs.plug.Plug.setDefault>`、:meth:`Plug.setKey <mlib.plugs.plug.Plug.setKey>`

.. _argument-unit:

``unit``
~~~~~~~~

角度の数値の単位(``"deg"`` は度、``"rad"`` はラジアン)。

- 受け方: キーワード専用
- 既定値: ``'deg'``
- 型: ``str``
- 既定値の例外: ``Quaternion.asRollBend``・``Quaternion.fromAxisAngle``・``Quaternion.fromRollBend`` — クォータニオンは中身も om2 もラジアン。数学型は om2 に合わせる
- 既定値の例外: ``Node.setKey`` — None は「指定しない」。アトリビュートが角度なら度(角度でないのに指定したら TypeError にするため)
- 既定値の例外: ``CompoundPlug.get``・``Double3Plug.get``・``Double3Plug.set``・``MatrixPlug.get``・``MultiPlug.get``・``Plug.get``・``Plug.getDefault``・``Plug.getRange``・``Plug.moveKey``・``Plug.set``・``Plug.setDefault``・``Plug.setKey``・``Plug.setRange`` — None は「指定しない」。アトリビュートが角度なら度(角度でないのに指定したら TypeError にするため)
- 使う所(46): :meth:`AimConstraint.setRestRotate <mlib.nodes.aimConstraint.AimConstraint.setRestRotate>`、:meth:`AnimCurve.addKey <mlib.nodes.animCurve.AnimCurve.addKey>`、:meth:`AnimCurve.addKeys <mlib.nodes.animCurve.AnimCurve.addKeys>`、:meth:`AnimCurve.evaluate <mlib.nodes.animCurve.AnimCurve.evaluate>`、:meth:`AnimCurve.getKeyValues <mlib.nodes.animCurve.AnimCurve.getKeyValues>`、:meth:`AnimCurve.reduceKeys <mlib.nodes.animCurve.AnimCurve.reduceKeys>`、:meth:`AnimCurve.replaceKeys <mlib.nodes.animCurve.AnimCurve.replaceKeys>`、:meth:`AnimCurve.scaleKey <mlib.nodes.animCurve.AnimCurve.scaleKey>`、:meth:`Camera.getFieldOfView <mlib.nodes.camera.Camera.getFieldOfView>`、:meth:`Camera.setFieldOfView <mlib.nodes.camera.Camera.setFieldOfView>`、:meth:`Camera.setView <mlib.nodes.camera.Camera.setView>`、:meth:`CompoundPlug.get <mlib.plugs.compoundPlug.CompoundPlug.get>`、:meth:`Double3Plug.get <mlib.plugs.double3Plug.Double3Plug.get>`、:meth:`Double3Plug.set <mlib.plugs.double3Plug.Double3Plug.set>`、:meth:`DrivenKey.setKey <mlib.common.drivenKey.DrivenKey.setKey>`、:meth:`EulerRotate.round <mlib.maths.eulerRotate.EulerRotate.round>`、:meth:`Joint.setJointOrient <mlib.nodes.joint.Joint.setJointOrient>`、:meth:`Joint.setPreferredAngle <mlib.nodes.joint.Joint.setPreferredAngle>`、:meth:`Keyframe.getTangent <mlib.common.keyframe.Keyframe.getTangent>`、:meth:`Keyframe.getValue <mlib.common.keyframe.Keyframe.getValue>`、:meth:`Keyframe.move <mlib.common.keyframe.Keyframe.move>`、:meth:`Keyframe.setTangent <mlib.common.keyframe.Keyframe.setTangent>`、:meth:`Keyframe.setValue <mlib.common.keyframe.Keyframe.setValue>`、:meth:`Keyframes.getValues <mlib.common.keyframe.Keyframes.getValues>`、:meth:`Keyframes.move <mlib.common.keyframe.Keyframes.move>`、:meth:`Keyframes.setTangent <mlib.common.keyframe.Keyframes.setTangent>`、:meth:`Keyframes.setValue <mlib.common.keyframe.Keyframes.setValue>`、:meth:`MatrixPlug.get <mlib.plugs.matrixPlug.MatrixPlug.get>`、:meth:`MultiPlug.get <mlib.plugs.multiPlug.MultiPlug.get>`、:meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`Node.moveKey <mlib.nodes.node.Node.moveKey>`、:meth:`Node.setKey <mlib.nodes.node.Node.setKey>`、:meth:`Plug.get <mlib.plugs.plug.Plug.get>`、:meth:`Plug.getDefault <mlib.plugs.plug.Plug.getDefault>`、:meth:`Plug.getRange <mlib.plugs.plug.Plug.getRange>`、:meth:`Plug.moveKey <mlib.plugs.plug.Plug.moveKey>`、:meth:`Plug.set <mlib.plugs.plug.Plug.set>`、:meth:`Plug.setDefault <mlib.plugs.plug.Plug.setDefault>`、:meth:`Plug.setKey <mlib.plugs.plug.Plug.setKey>`、:meth:`Plug.setRange <mlib.plugs.plug.Plug.setRange>`、:meth:`Quaternion.asRollBend <mlib.maths.quaternion.Quaternion.asRollBend>`、:meth:`Quaternion.fromAxisAngle <mlib.maths.quaternion.Quaternion.fromAxisAngle>`、:meth:`Quaternion.fromRollBend <mlib.maths.quaternion.Quaternion.fromRollBend>`、:meth:`Transform.getLimits <mlib.nodes.transform.Transform.getLimits>`、:meth:`Transform.setLimits <mlib.nodes.transform.Transform.setLimits>`、:meth:`Transform.setRotate <mlib.nodes.transform.Transform.setRotate>`

.. _argument-unlock:

``unlock``
~~~~~~~~~~

ロックを一時的に外してから処理する。

- 受け方: キーワード専用
- 既定値: ``False``
- 型: ``bool``
- 使う所(4): :meth:`Plug.connect <mlib.plugs.plug.Plug.connect>`、:meth:`Plug.delete <mlib.plugs.plug.Plug.delete>`、:meth:`Plug.disconnect <mlib.plugs.plug.Plug.disconnect>`、:meth:`Plug.setIfChanged <mlib.plugs.plug.Plug.setIfChanged>`

.. _argument-unused:

``unused``
~~~~~~~~~~

使っていないものを対象にする。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(None は絞り込まない(getInfluences)、False は対象にしない(removeInfluences))
- 使う所(2): :meth:`SkinCluster.getInfluences <mlib.nodes.skinCluster.SkinCluster.getInfluences>`、:meth:`SkinCluster.removeInfluences <mlib.nodes.skinCluster.SkinCluster.removeInfluences>`

.. _argument-up:

``up``
~~~~~~

上の向きのベクトル。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(None は自動で決める)
- 使う所(4): :meth:`Camera.setView <mlib.nodes.camera.Camera.setView>`、:meth:`Matrix.fromAim <mlib.maths.matrix.Matrix.fromAim>`、:meth:`NurbsCurve.getMatricesAlong <mlib.nodes.nurbsCurve.NurbsCurve.getMatricesAlong>`、:func:`createJointChain <mlib.cmds.createJointChain.createJointChain>`

.. _argument-upAxis:

``upAxis``
~~~~~~~~~~

上へ向ける軸。

- 受け方: キーワード専用
- 既定値: ``'y'``
- 使う所(6): :meth:`Matrix.fromAim <mlib.maths.matrix.Matrix.fromAim>`、:meth:`NurbsCurve.getMatricesAlong <mlib.nodes.nurbsCurve.NurbsCurve.getMatricesAlong>`、:meth:`NurbsSurface.getAtParam <mlib.nodes.nurbsSurface.NurbsSurface.getAtParam>`、:meth:`Quaternion.asRollBend <mlib.maths.quaternion.Quaternion.asRollBend>`、:meth:`Quaternion.fromRollBend <mlib.maths.quaternion.Quaternion.fromRollBend>`、:func:`createJointChain <mlib.cmds.createJointChain.createJointChain>`

.. _argument-uvSet:

``uvSet``
~~~~~~~~~

UVセットの名前。None は今のUVセット。

- 受け方: キーワード専用
- 既定値: ``None``
- 型: ``str | None``
- 使う所(12): :meth:`Face.getArea <mlib.components.face.Face.getArea>`、:meth:`Face.getPointAtUV <mlib.components.face.Face.getPointAtUV>`、:meth:`Face.getUVAtPoint <mlib.components.face.Face.getUVAtPoint>`、:meth:`Face.isKind <mlib.components.face.Face.isKind>`、:meth:`Mesh.getClosestPoint <mlib.nodes.mesh.Mesh.getClosestPoint>`、:meth:`Mesh.getFaceVertexTangents <mlib.nodes.mesh.Mesh.getFaceVertexTangents>`、:meth:`Mesh.getPointsAtUV <mlib.nodes.mesh.Mesh.getPointsAtUV>`、:meth:`Mesh.getShells <mlib.nodes.mesh.Mesh.getShells>`、:meth:`Mesh.getUVData <mlib.nodes.mesh.Mesh.getUVData>`、:meth:`Mesh.reorderVertices <mlib.nodes.mesh.Mesh.reorderVertices>`、:meth:`Mesh.setUVData <mlib.nodes.mesh.Mesh.setUVData>`、:meth:`VertexFace.getTangent <mlib.components.vertexFace.VertexFace.getTangent>`

.. _argument-value:

``value``
~~~~~~~~~

書き込む値。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(そのメソッドの主な値。何を指すかはメソッドごとに違う)
- 使う所(44): :meth:`AimConstraint.setRestRotate <mlib.nodes.aimConstraint.AimConstraint.setRestRotate>`、:meth:`AnimCurve.addKey <mlib.nodes.animCurve.AnimCurve.addKey>`、:meth:`Camera.setAspectRatio <mlib.nodes.camera.Camera.setAspectRatio>`、:meth:`Components.append <mlib.components.component.Components.append>`、:meth:`Components.count <mlib.components.component.Components.count>`、:meth:`Components.index <mlib.components.component.Components.index>`、:meth:`Components.insert <mlib.components.component.Components.insert>`、:meth:`Components.remove <mlib.components.component.Components.remove>`、:meth:`Double3Plug.set <mlib.plugs.double3Plug.Double3Plug.set>`、:meth:`DrivenKey.setKey <mlib.common.drivenKey.DrivenKey.setKey>`、:meth:`Joint.setJointOrient <mlib.nodes.joint.Joint.setJointOrient>`、:meth:`Joint.setPreferredAngle <mlib.nodes.joint.Joint.setPreferredAngle>`、:meth:`Joint.setRadius <mlib.nodes.joint.Joint.setRadius>`、:meth:`Joints.setRadius <mlib.nodes.joint.Joints.setRadius>`、:meth:`Keyframe.setValue <mlib.common.keyframe.Keyframe.setValue>`、:meth:`Keyframes.setValue <mlib.common.keyframe.Keyframes.setValue>`、:meth:`Matrix.transformPoint <mlib.maths.matrix.Matrix.transformPoint>`、:meth:`Matrix.transformVector <mlib.maths.matrix.Matrix.transformVector>`、:meth:`Plug.getEnumNames <mlib.plugs.plug.Plug.getEnumNames>`、:meth:`Plug.set <mlib.plugs.plug.Plug.set>`、:meth:`Plug.setDefault <mlib.plugs.plug.Plug.setDefault>`、:meth:`Plug.setIfChanged <mlib.plugs.plug.Plug.setIfChanged>`、:meth:`PointComponent.setPosition <mlib.components.pointComponent.PointComponent.setPosition>`、:meth:`PointComponents.setPosition <mlib.components.pointComponent.PointComponents.setPosition>`、:meth:`SkinCluster.setDropoffRate <mlib.nodes.skinCluster.SkinCluster.setDropoffRate>`、:meth:`SkinCluster.setMode <mlib.nodes.skinCluster.SkinCluster.setMode>`、:meth:`Time.setCurrent <mlib.common.sceneTime.Time.setCurrent>`、:meth:`Transform.setPivot <mlib.nodes.transform.Transform.setPivot>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、:meth:`Transform.setRotate <mlib.nodes.transform.Transform.setRotate>`、:meth:`Transform.setScale <mlib.nodes.transform.Transform.setScale>`、:meth:`Transform.setShear <mlib.nodes.transform.Transform.setShear>`、:meth:`Transform.setTransformation <mlib.nodes.transform.Transform.setTransformation>`、:meth:`Transform.setTranslation <mlib.nodes.transform.Transform.setTranslation>`、``Transformation.__init__``、:meth:`UV.setPosition <mlib.components.uv.UV.setPosition>`、:meth:`UVs.setPosition <mlib.components.uv.UVs.setPosition>`、``Version.__init__``、:meth:`Version.parse <mlib.common.version.Version.parse>`、:func:`convertAngle <mlib.common.units.convertAngle>`、:func:`convertDistance <mlib.common.units.convertDistance>`、:func:`convertTime <mlib.common.units.convertTime>`、:func:`getNode <mlib.cmds.getNode.getNode>`、:func:`getPlug <mlib.cmds.getPlug.getPlug>`

.. _argument-valueOffset:

``valueOffset``
~~~~~~~~~~~~~~~

値へ足す値。

- 受け方: キーワード専用
- 既定値: ``0``
- 使う所(4): :meth:`Keyframe.move <mlib.common.keyframe.Keyframe.move>`、:meth:`Keyframes.move <mlib.common.keyframe.Keyframes.move>`、:meth:`Node.moveKey <mlib.nodes.node.Node.moveKey>`、:meth:`Plug.moveKey <mlib.plugs.plug.Plug.moveKey>`

.. _argument-vertices:

``vertices``
~~~~~~~~~~~~

対象の頂点。None は全部。

- 受け方: キーワード専用
- 既定値: ``None``
- 受け方の例外: ``BlendShape.resetTargetVertices`` — 主な値を2通りで受ける(vertices か tolerance=)
- 使う所(12): :meth:`BlendShape.resetTargetVertices <mlib.nodes.blendShape.BlendShape.resetTargetVertices>`、:meth:`GeometryFilter.setDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.setDeformerWeights>`、:meth:`Mesh.setVertexColors <mlib.nodes.mesh.Mesh.setVertexColors>`、:meth:`SkinCluster.getBlendWeights <mlib.nodes.skinCluster.SkinCluster.getBlendWeights>`、:meth:`SkinCluster.getWeights <mlib.nodes.skinCluster.SkinCluster.getWeights>`、:meth:`SkinCluster.limitInfluences <mlib.nodes.skinCluster.SkinCluster.limitInfluences>`、:meth:`SkinCluster.redistributeWeights <mlib.nodes.skinCluster.SkinCluster.redistributeWeights>`、:meth:`SkinCluster.roundWeights <mlib.nodes.skinCluster.SkinCluster.roundWeights>`、:meth:`SkinCluster.setBlendWeights <mlib.nodes.skinCluster.SkinCluster.setBlendWeights>`、:meth:`SkinCluster.setWeights <mlib.nodes.skinCluster.SkinCluster.setWeights>`、:meth:`SkinCluster.smoothWeights <mlib.nodes.skinCluster.SkinCluster.smoothWeights>`、:meth:`SkinCluster.transferWeights <mlib.nodes.skinCluster.SkinCluster.transferWeights>`

.. _argument-weights:

``weights``
~~~~~~~~~~~

ウェイトの値、またはウェイトのファイル。

- 受け方: 位置でも渡せる
- 既定値: ``None``
- 使う所(5): :meth:`BlendShape.setTargetWeights <mlib.nodes.blendShape.BlendShape.setTargetWeights>`、:meth:`GeometryFilter.setDeformerWeights <mlib.nodes.geometryFilter.GeometryFilter.setDeformerWeights>`、:meth:`SkinCluster.setBlendWeights <mlib.nodes.skinCluster.SkinCluster.setBlendWeights>`、:meth:`SkinCluster.setWeights <mlib.nodes.skinCluster.SkinCluster.setWeights>`、:func:`bindSkin <mlib.cmds.bindSkin.bindSkin>`

.. _argument-what:

``what``
~~~~~~~~

取得するものを名前で選ぶ。

- 受け方: キーワード専用
- 既定値: メソッドごとに違う(種類を選ぶ引数で、選べる種類と既定はメソッドごとに違う)
- 型: ``str``
- 使う所(5): :meth:`Matrix.extract <mlib.maths.matrix.Matrix.extract>`、:meth:`Mesh.getClosestPoint <mlib.nodes.mesh.Mesh.getClosestPoint>`、:meth:`NurbsCurve.getAtParam <mlib.nodes.nurbsCurve.NurbsCurve.getAtParam>`、:meth:`NurbsSurface.getAtParam <mlib.nodes.nurbsSurface.NurbsSurface.getAtParam>`、:meth:`Reference.getEdits <mlib.nodes.reference.Reference.getEdits>`

.. _argument-width:

``width``
~~~~~~~~~

幅。

- 受け方: 位置でも渡せる
- 既定値: メソッドごとに違う(形状の大きさと、進捗の表示の桁数)
- 使う所(5): ``_MainProgressBar.__init__``、``_ProgressLine.__init__``、:func:`createNurbsPlane <mlib.cmds.createNurbsPlane.createNurbsPlane>`、:func:`createPoly <mlib.cmds.createPoly.createPoly>`、:func:`progressBar <mlib.common.progress.progressBar>`

.. _argument-worldSpace:

``worldSpace``
~~~~~~~~~~~~~~

Trueはワールド空間、Falseはローカル(オブジェクト)空間。

- 受け方: 位置でも渡せる
- 既定値: ``False``
- 型: ``bool``
- 既定値の例外: ``Joint.getBoneSegments`` — ボーンの線分はワールドのマトリクスが元の値で、ローカルで使う場面がほぼ無い
- 既定値の例外: ``SkinCluster.restoreBindPose`` — バインドポーズはワールドのマトリクスで保存してある
- 使う所(75): :meth:`Camera.getDirection <mlib.nodes.camera.Camera.getDirection>`、:meth:`Camera.getPoint <mlib.nodes.camera.Camera.getPoint>`、:meth:`Camera.setPoint <mlib.nodes.camera.Camera.setPoint>`、:meth:`DagNode.getBoundingBox <mlib.nodes.dagNode.DagNode.getBoundingBox>`、:meth:`DagPose.getMatrix <mlib.nodes.dagPose.DagPose.getMatrix>`、:meth:`DagPose.restore <mlib.nodes.dagPose.DagPose.restore>`、:meth:`Edge.getCenter <mlib.components.edge.Edge.getCenter>`、:meth:`Edge.getLength <mlib.components.edge.Edge.getLength>`、:meth:`Face.getArea <mlib.components.face.Face.getArea>`、:meth:`Face.getCenter <mlib.components.face.Face.getCenter>`、:meth:`Face.getNormal <mlib.components.face.Face.getNormal>`、:meth:`Face.getPointAtUV <mlib.components.face.Face.getPointAtUV>`、:meth:`Face.getUVAtPoint <mlib.components.face.Face.getUVAtPoint>`、:meth:`Joint.getBoneSegments <mlib.nodes.joint.Joint.getBoneSegments>`、:meth:`Mesh.getClosestPoint <mlib.nodes.mesh.Mesh.getClosestPoint>`、:meth:`Mesh.getClosestVertices <mlib.nodes.mesh.Mesh.getClosestVertices>`、:meth:`Mesh.getFaceVertexTangents <mlib.nodes.mesh.Mesh.getFaceVertexTangents>`、:meth:`Mesh.getMirrorVertexMap <mlib.nodes.mesh.Mesh.getMirrorVertexMap>`、:meth:`Mesh.getNormalData <mlib.nodes.mesh.Mesh.getNormalData>`、:meth:`Mesh.getPointsAtUV <mlib.nodes.mesh.Mesh.getPointsAtUV>`、:meth:`Mesh.getTangentData <mlib.nodes.mesh.Mesh.getTangentData>`、:meth:`Mesh.getVertexAdjacency <mlib.nodes.mesh.Mesh.getVertexAdjacency>`、:meth:`Mesh.getVertexNormals <mlib.nodes.mesh.Mesh.getVertexNormals>`、:meth:`Mesh.intersect <mlib.nodes.mesh.Mesh.intersect>`、:meth:`Mesh.reorderVertices <mlib.nodes.mesh.Mesh.reorderVertices>`、:meth:`Mesh.setFaceVertexNormals <mlib.nodes.mesh.Mesh.setFaceVertexNormals>`、:meth:`Mesh.setNormals <mlib.nodes.mesh.Mesh.setNormals>`、:meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`NurbsCurve.getArea <mlib.nodes.nurbsCurve.NurbsCurve.getArea>`、:meth:`NurbsCurve.getAtParam <mlib.nodes.nurbsCurve.NurbsCurve.getAtParam>`、:meth:`NurbsCurve.getClosestPoint <mlib.nodes.nurbsCurve.NurbsCurve.getClosestPoint>`、:meth:`NurbsCurve.getCollocatedCVGroups <mlib.nodes.nurbsCurve.NurbsCurve.getCollocatedCVGroups>`、:meth:`NurbsCurve.getLength <mlib.nodes.nurbsCurve.NurbsCurve.getLength>`、:meth:`NurbsCurve.getMatricesAlong <mlib.nodes.nurbsCurve.NurbsCurve.getMatricesAlong>`、:meth:`NurbsCurve.getParam <mlib.nodes.nurbsCurve.NurbsCurve.getParam>`、:meth:`NurbsCurve.getParamsAlong <mlib.nodes.nurbsCurve.NurbsCurve.getParamsAlong>`、:meth:`NurbsCurve.isPointOnCurve <mlib.nodes.nurbsCurve.NurbsCurve.isPointOnCurve>`、:meth:`NurbsSurface.getArea <mlib.nodes.nurbsSurface.NurbsSurface.getArea>`、:meth:`NurbsSurface.getAtParam <mlib.nodes.nurbsSurface.NurbsSurface.getAtParam>`、:meth:`NurbsSurface.getClosestPoint <mlib.nodes.nurbsSurface.NurbsSurface.getClosestPoint>`、:meth:`NurbsSurface.getRayIntersection <mlib.nodes.nurbsSurface.NurbsSurface.getRayIntersection>`、:meth:`NurbsSurface.isPointOnSurface <mlib.nodes.nurbsSurface.NurbsSurface.isPointOnSurface>`、:meth:`PointComponent.getPosition <mlib.components.pointComponent.PointComponent.getPosition>`、:meth:`PointComponent.setPosition <mlib.components.pointComponent.PointComponent.setPosition>`、:meth:`PointComponents.getCenter <mlib.components.pointComponent.PointComponents.getCenter>`、:meth:`PointComponents.getPosition <mlib.components.pointComponent.PointComponents.getPosition>`、:meth:`PointComponents.mirror <mlib.components.pointComponent.PointComponents.mirror>`、:meth:`PointComponents.setPosition <mlib.components.pointComponent.PointComponents.setPosition>`、:meth:`Shape.scaleGeometry <mlib.nodes.shape.Shape.scaleGeometry>`、:meth:`SkinCluster.restoreBindPose <mlib.nodes.skinCluster.SkinCluster.restoreBindPose>`、:meth:`Transform.getMatrix <mlib.nodes.transform.Transform.getMatrix>`、:meth:`Transform.getPivot <mlib.nodes.transform.Transform.getPivot>`、:meth:`Transform.getQuaternion <mlib.nodes.transform.Transform.getQuaternion>`、:meth:`Transform.getRotate <mlib.nodes.transform.Transform.getRotate>`、:meth:`Transform.getScale <mlib.nodes.transform.Transform.getScale>`、:meth:`Transform.getShear <mlib.nodes.transform.Transform.getShear>`、:meth:`Transform.getTranslation <mlib.nodes.transform.Transform.getTranslation>`、:meth:`Transform.mirrorGeometry <mlib.nodes.transform.Transform.mirrorGeometry>`、:meth:`Transform.mirrorTransform <mlib.nodes.transform.Transform.mirrorTransform>`、:meth:`Transform.replaceShapes <mlib.nodes.transform.Transform.replaceShapes>`、:meth:`Transform.scaleGeometry <mlib.nodes.transform.Transform.scaleGeometry>`、:meth:`Transform.setMatrix <mlib.nodes.transform.Transform.setMatrix>`、:meth:`Transform.setPivot <mlib.nodes.transform.Transform.setPivot>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、:meth:`Transform.setRotate <mlib.nodes.transform.Transform.setRotate>`、:meth:`Transform.setScale <mlib.nodes.transform.Transform.setScale>`、:meth:`Transform.setShear <mlib.nodes.transform.Transform.setShear>`、:meth:`Transform.setTranslation <mlib.nodes.transform.Transform.setTranslation>`、:meth:`Vertex.getNormal <mlib.components.vertex.Vertex.getNormal>`、:meth:`VertexFace.getNormal <mlib.components.vertexFace.VertexFace.getNormal>`、:meth:`VertexFace.getTangent <mlib.components.vertexFace.VertexFace.getTangent>`、:meth:`VertexFace.setNormal <mlib.components.vertexFace.VertexFace.setNormal>`、``_ControlPointShape.getPoints``、``_ControlPointShape.mirror``、``_ControlPointShape.setPoints``

.. _argument-ws:

``ws``
~~~~~~

worldSpace の短縮名。

- 受け方: キーワード専用
- 型: ``bool``
- 説明の決まり文句: worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
- 使う所(75): :meth:`Camera.getDirection <mlib.nodes.camera.Camera.getDirection>`、:meth:`Camera.getPoint <mlib.nodes.camera.Camera.getPoint>`、:meth:`Camera.setPoint <mlib.nodes.camera.Camera.setPoint>`、:meth:`DagNode.getBoundingBox <mlib.nodes.dagNode.DagNode.getBoundingBox>`、:meth:`DagPose.getMatrix <mlib.nodes.dagPose.DagPose.getMatrix>`、:meth:`DagPose.restore <mlib.nodes.dagPose.DagPose.restore>`、:meth:`Edge.getCenter <mlib.components.edge.Edge.getCenter>`、:meth:`Edge.getLength <mlib.components.edge.Edge.getLength>`、:meth:`Face.getArea <mlib.components.face.Face.getArea>`、:meth:`Face.getCenter <mlib.components.face.Face.getCenter>`、:meth:`Face.getNormal <mlib.components.face.Face.getNormal>`、:meth:`Face.getPointAtUV <mlib.components.face.Face.getPointAtUV>`、:meth:`Face.getUVAtPoint <mlib.components.face.Face.getUVAtPoint>`、:meth:`Joint.getBoneSegments <mlib.nodes.joint.Joint.getBoneSegments>`、:meth:`Mesh.getClosestPoint <mlib.nodes.mesh.Mesh.getClosestPoint>`、:meth:`Mesh.getClosestVertices <mlib.nodes.mesh.Mesh.getClosestVertices>`、:meth:`Mesh.getFaceVertexTangents <mlib.nodes.mesh.Mesh.getFaceVertexTangents>`、:meth:`Mesh.getMirrorVertexMap <mlib.nodes.mesh.Mesh.getMirrorVertexMap>`、:meth:`Mesh.getNormalData <mlib.nodes.mesh.Mesh.getNormalData>`、:meth:`Mesh.getPointsAtUV <mlib.nodes.mesh.Mesh.getPointsAtUV>`、:meth:`Mesh.getTangentData <mlib.nodes.mesh.Mesh.getTangentData>`、:meth:`Mesh.getVertexAdjacency <mlib.nodes.mesh.Mesh.getVertexAdjacency>`、:meth:`Mesh.getVertexNormals <mlib.nodes.mesh.Mesh.getVertexNormals>`、:meth:`Mesh.intersect <mlib.nodes.mesh.Mesh.intersect>`、:meth:`Mesh.reorderVertices <mlib.nodes.mesh.Mesh.reorderVertices>`、:meth:`Mesh.setFaceVertexNormals <mlib.nodes.mesh.Mesh.setFaceVertexNormals>`、:meth:`Mesh.setNormals <mlib.nodes.mesh.Mesh.setNormals>`、:meth:`Node.addAttr <mlib.nodes.node.Node.addAttr>`、:meth:`NurbsCurve.getArea <mlib.nodes.nurbsCurve.NurbsCurve.getArea>`、:meth:`NurbsCurve.getAtParam <mlib.nodes.nurbsCurve.NurbsCurve.getAtParam>`、:meth:`NurbsCurve.getClosestPoint <mlib.nodes.nurbsCurve.NurbsCurve.getClosestPoint>`、:meth:`NurbsCurve.getCollocatedCVGroups <mlib.nodes.nurbsCurve.NurbsCurve.getCollocatedCVGroups>`、:meth:`NurbsCurve.getLength <mlib.nodes.nurbsCurve.NurbsCurve.getLength>`、:meth:`NurbsCurve.getMatricesAlong <mlib.nodes.nurbsCurve.NurbsCurve.getMatricesAlong>`、:meth:`NurbsCurve.getParam <mlib.nodes.nurbsCurve.NurbsCurve.getParam>`、:meth:`NurbsCurve.getParamsAlong <mlib.nodes.nurbsCurve.NurbsCurve.getParamsAlong>`、:meth:`NurbsCurve.isPointOnCurve <mlib.nodes.nurbsCurve.NurbsCurve.isPointOnCurve>`、:meth:`NurbsSurface.getArea <mlib.nodes.nurbsSurface.NurbsSurface.getArea>`、:meth:`NurbsSurface.getAtParam <mlib.nodes.nurbsSurface.NurbsSurface.getAtParam>`、:meth:`NurbsSurface.getClosestPoint <mlib.nodes.nurbsSurface.NurbsSurface.getClosestPoint>`、:meth:`NurbsSurface.getRayIntersection <mlib.nodes.nurbsSurface.NurbsSurface.getRayIntersection>`、:meth:`NurbsSurface.isPointOnSurface <mlib.nodes.nurbsSurface.NurbsSurface.isPointOnSurface>`、:meth:`PointComponent.getPosition <mlib.components.pointComponent.PointComponent.getPosition>`、:meth:`PointComponent.setPosition <mlib.components.pointComponent.PointComponent.setPosition>`、:meth:`PointComponents.getCenter <mlib.components.pointComponent.PointComponents.getCenter>`、:meth:`PointComponents.getPosition <mlib.components.pointComponent.PointComponents.getPosition>`、:meth:`PointComponents.mirror <mlib.components.pointComponent.PointComponents.mirror>`、:meth:`PointComponents.setPosition <mlib.components.pointComponent.PointComponents.setPosition>`、:meth:`Shape.scaleGeometry <mlib.nodes.shape.Shape.scaleGeometry>`、:meth:`SkinCluster.restoreBindPose <mlib.nodes.skinCluster.SkinCluster.restoreBindPose>`、:meth:`Transform.getMatrix <mlib.nodes.transform.Transform.getMatrix>`、:meth:`Transform.getPivot <mlib.nodes.transform.Transform.getPivot>`、:meth:`Transform.getQuaternion <mlib.nodes.transform.Transform.getQuaternion>`、:meth:`Transform.getRotate <mlib.nodes.transform.Transform.getRotate>`、:meth:`Transform.getScale <mlib.nodes.transform.Transform.getScale>`、:meth:`Transform.getShear <mlib.nodes.transform.Transform.getShear>`、:meth:`Transform.getTranslation <mlib.nodes.transform.Transform.getTranslation>`、:meth:`Transform.mirrorGeometry <mlib.nodes.transform.Transform.mirrorGeometry>`、:meth:`Transform.mirrorTransform <mlib.nodes.transform.Transform.mirrorTransform>`、:meth:`Transform.replaceShapes <mlib.nodes.transform.Transform.replaceShapes>`、:meth:`Transform.scaleGeometry <mlib.nodes.transform.Transform.scaleGeometry>`、:meth:`Transform.setMatrix <mlib.nodes.transform.Transform.setMatrix>`、:meth:`Transform.setPivot <mlib.nodes.transform.Transform.setPivot>`、:meth:`Transform.setQuaternion <mlib.nodes.transform.Transform.setQuaternion>`、:meth:`Transform.setRotate <mlib.nodes.transform.Transform.setRotate>`、:meth:`Transform.setScale <mlib.nodes.transform.Transform.setScale>`、:meth:`Transform.setShear <mlib.nodes.transform.Transform.setShear>`、:meth:`Transform.setTranslation <mlib.nodes.transform.Transform.setTranslation>`、:meth:`Vertex.getNormal <mlib.components.vertex.Vertex.getNormal>`、:meth:`VertexFace.getNormal <mlib.components.vertexFace.VertexFace.getNormal>`、:meth:`VertexFace.getTangent <mlib.components.vertexFace.VertexFace.getTangent>`、:meth:`VertexFace.setNormal <mlib.components.vertexFace.VertexFace.setNormal>`、``_ControlPointShape.getPoints``、``_ControlPointShape.mirror``、``_ControlPointShape.setPoints``

.. _argument-zeroScaleOrient:

``zeroScaleOrient``
~~~~~~~~~~~~~~~~~~~

scaleOrient を0にする。

- 受け方: キーワード専用
- 使う所(2): :meth:`Joint.orient <mlib.nodes.joint.Joint.orient>`、:meth:`Joints.orient <mlib.nodes.joint.Joints.orient>`
