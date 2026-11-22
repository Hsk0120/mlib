"""Maya のカメラシェイプを扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.OpenMaya as om1

from ..core.fastWrite import require_writable
from ..decorator import _pick_alias, _require_bool
from ..maths.matrix import Matrix
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _angle_unit, _finite, _finite_vector, _from_radians, _world_space
from .shape import Shape


class Camera(Shape):
    """Mayaのcameraシェイプノードを保持し、撮影条件と投影を扱う。

    手動クリップ設定の照会は ``getPlug("bestFitClippingPlanes").get()`` を使う。
    これはMFnCamera.isClippingPlanesの取得値に対応する。似た名前のclippingPlanesは未使用のアトリビュート。
    """

    def mfn(self):
        """このカメラのfunction set(``om2.MFnCamera``)を取得する。

        呼び出すたびに、このオブジェクトが持つDAGパスから新しく作る。

        Returns:
            om2.MFnCamera: このカメラのfunction set。
        """
        return om2.MFnCamera(self.mpath())

    def getUnnormalizedClippingPlanes(self):
        """カメラの非正規化ニア・ファークリップ距離を取得する。

        cameraSetの表示で共通化される前の、個々のカメラのクリップ距離。
        clippingPlanesアトリビュートの有効状態は判定しない。

        Returns:
            tuple[float, float]: (ニア, ファー)の距離(cm)。
        """
        fn = om1.MFnCamera(self._api1_path())
        return fn.unnormalizedNearClippingPlane(), fn.unnormalizedFarClippingPlane()

    def setView(self, eye, direction, up, fieldOfView, aspectRatio, *, unit="deg", fast=False):
        """ワールド空間の視点・視線・上方向と画角をまとめて変更する。

        MFnCamera.setを使い、親Transformとカメラの投影設定を変更する。
        fast=True専用でUndoには記録しない。Undo設定は変更しない。
        途中でMayaエラーが発生した場合、更新前への復元は保証しない。

        Args:
            eye (Iterable[float]): 視点のワールド座標(cm)。
            direction (Iterable[float]): ゼロでない視線方向。
            up (Iterable[float]): 視線と平行でない上方向。
            fieldOfView (float): 水平画角。0より大きく180度未満。
            aspectRatio (float): 正の横幅/高さ比。
            unit (str): 画角の単位。既定deg。radも指定できる。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 引数の型が不正な場合。
            ValueError: 座標・方向・画角・比率が不正な場合。
            RuntimeError: ロック・入力接続・参照がある場合、またはMayaが更新を拒否した場合。
            NotImplementedError: fast=False、または親が通常Transformでないかインスタンスの場合。
        """
        eye = om2.MPoint(_finite_vector(eye, 3, "eye"))
        direction = Vector(_finite_vector(direction, 3, "direction"))
        up = Vector(_finite_vector(up, 3, "up"))
        angle_unit = om2.MAngle.kDegrees if _angle_unit(unit) == "deg" else om2.MAngle.kRadians
        angle = om2.MAngle(_finite(fieldOfView, "fieldOfView"), angle_unit).asRadians()
        aspectRatio = _finite(aspectRatio, "aspectRatio")
        if not 0 < angle < 3.141592653589793 or aspectRatio <= 0 or (direction ^ up).length() < 1e-12:
            raise ValueError("画角・比率は範囲内、方向はゼロでなく互いに平行でない値で指定してください")
        self._require_view_edit(fast)
        self.mfn().set(eye, direction, up, angle, aspectRatio)

    def copyViewFrom(self, camera, *, fast=False):
        """別のカメラの視点・透視投影に関わる設定をコピーする。

        MFnCamera.copyViewFromの対象設定をコピーする。全アトリビュートの複製ではない。
        コピー先の親Transformも変わる。fast=True専用でUndoには記録しない。

        Args:
            camera (str | Camera): コピー元のカメラShape。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: cameraがカメラShapeでない場合、またはfastがboolでない場合。
            RuntimeError: ロック・入力接続・参照がある場合、またはカメラが無効な場合。
            NotImplementedError: fast=False、またはコピー先が対応しない階層の場合。
        """
        camera = Camera(camera)
        self._require_view_edit(fast)
        self.mfn().copyViewFrom(camera.mpath())

    def getDepthOfFieldRange(self):
        """被写界深度を再計算し、近側と遠側の合焦距離を取得する。

        MFnCamera.computeDepthOfFieldでMaya内部の計算結果を更新する。
        カメラのアトリビュートやUndo設定は変更しない。レンダラー独自の被写界深度は扱わない。

        Returns:
            tuple[float, float]: (近側, 遠側)の距離(cm)。Mayaの計算結果をそのまま返す。

        Raises:
            RuntimeError: カメラが無効、またはMayaが計算を拒否した場合。
        """
        fn = self.mfn()
        fn.computeDepthOfField()
        return fn.nearFocusDistance, fn.farFocusDistance

    def isVerticalLocked(self):
        """縦横比変更時に垂直フィルム開口を維持する設定か調べる。

        アトリビュートの編集ロックとは異なるMayaのカメラ設定。

        Returns:
            bool: 垂直フィルム開口を維持する場合はTrue。
        """
        return self.mfn().isVerticalLock

    def setVerticalLocked(self, state=True):
        """縦横比変更時に垂直フィルム開口を維持する設定を切り替える。

        アトリビュートの編集ロックは変更しない。
        fast引数は持たない(1回のcmdsで設定するため)。

        Args:
            state (bool): Trueなら垂直フィルム開口を維持する。既定True。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがbool以外の場合。
            RuntimeError: カメラが無効、またはMayaが変更を拒否した場合。
        """
        _require_bool(state, "state")
        self._require_valid("設定の変更")
        cmds.camera(self.getFullName(), edit=True, verticalLock=state)

    def getFocalLength(self):
        """焦点距離を取得する。

        Returns:
            float: Mayaの焦点距離。
        """
        return self.mfn().focalLength

    def getFieldOfView(self, *, unit="deg"):
        """水平と垂直の画角を取得する。

        ``MFnCamera.horizontalFieldOfView``・``verticalFieldOfView`` の値を返す。
        画角は、焦点距離とフィルムバック(``horizontalFilmAperture``・``verticalFilmAperture``)から次の式で求まる。
        Mayaは1mmを0.03937インチとして換算する。

        ``2 * atan(フィルムバック(インチ) / 0.03937 / 2 / 焦点距離(mm))``

        Film Fitや解像度の縦横比で切り取られる分は含まない。

        Args:
            unit (str): 戻り値の角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
                ``"degree"`` などの別名も使える。

        Returns:
            tuple[float, float]: (水平の画角, 垂直の画角)。

        Raises:
            TypeError: unitが文字列・None以外の場合。
            ValueError: unitに使えない単位名を指定した場合。
            RuntimeError: ノードが削除済みの場合。
        """
        angle_unit = _angle_unit(unit)
        fn = self.mfn()
        return (_from_radians(fn.horizontalFieldOfView(), angle_unit), _from_radians(fn.verticalFieldOfView(), angle_unit))

    def setFieldOfView(self, angle, *, vertical=False, unit="deg"):
        """水平または垂直の画角を変更する。

        Maya標準のcameraコマンドで焦点距離を補正する。フィルム開口を直接指定する操作ではない。
        fast引数は持たない(1回のcmdsで更新するため)。

        Args:
            angle (float): 0より大きく180度未満の画角。
            vertical (bool): Trueなら垂直、Falseなら水平の画角。既定False。
            unit (str): angleの単位。"deg"または"rad"。既定"deg"。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: verticalがbool以外の場合。
            ValueError: 画角が有限値でない、範囲外、または単位が不正の場合。
            RuntimeError: カメラが無効、またはMayaが更新を拒否した場合。
        """
        _require_bool(vertical, "vertical")
        value = _finite(angle, "angle")
        if _angle_unit(unit) == "rad":
            value = om2.MAngle(value).asDegrees()
        if not 0 < value < 180:
            raise ValueError("angleは0より大きく180度未満で指定してください")
        self._require_valid("画角の変更")
        if vertical:
            cmds.camera(self.getFullName(), edit=True, verticalFieldOfView=value)
        else:
            cmds.camera(self.getFullName(), edit=True, horizontalFieldOfView=value)

    def setNearFocusDistance(self, distance):
        """近側の合焦距離を指定して、カメラの焦点位置を補正する。

        Maya標準の補正に従い、反対側の合焦距離も変わる。クリップ面の設定ではない。
        fast引数は持たない(1回のcmdsで更新するため)。

        Args:
            distance (float): 正の有限距離(cm)。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: distanceが有限の正数でない場合。
            RuntimeError: カメラが無効、またはMayaが更新を拒否した場合。
        """
        value = _finite(distance, "distance")
        if value <= 0:
            raise ValueError("distanceは正の距離で指定してください")
        self._require_valid("合焦距離の変更")
        cmds.camera(self.getFullName(), edit=True, nearFocusDistance=om2.MDistance(value).asUnits(om2.MDistance.uiUnit()))

    def setFarFocusDistance(self, distance):
        """遠側の合焦距離を指定して、カメラの焦点位置を補正する。

        Maya標準の補正に従い、反対側の合焦距離も変わる。クリップ面の設定ではない。
        fast引数は持たない(1回のcmdsで更新するため)。

        Args:
            distance (float): 正の有限距離(cm)。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: distanceが有限の正数でない場合。
            RuntimeError: カメラが無効、またはMayaが更新を拒否した場合。
        """
        value = _finite(distance, "distance")
        if value <= 0:
            raise ValueError("distanceは正の距離で指定してください")
        self._require_valid("合焦距離の変更")
        cmds.camera(self.getFullName(), edit=True, farFocusDistance=om2.MDistance(value).asUnits(om2.MDistance.uiUnit()))

    def getCenterOfInterestPoint(self, worldSpace=_UNSET, *, ws=_UNSET):
        """カメラの注視点を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定True。
            ws (bool): worldSpaceの短縮名。長名と同時指定できない。

        Returns:
            Vector: 注視点の位置(cm)。

        Raises:
            TypeError: 空間指定がbool以外、または長短名を同時指定した場合。
            RuntimeError: カメラが無効な場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=True)
        return _vectors_of_points([self.mfn().centerOfInterestPoint(self._space(worldSpace))])[0]

    def setCenterOfInterestPoint(self, point, worldSpace=_UNSET, *, ws=_UNSET, fast=False):
        """視点を保ちながらカメラの注視点を変更する。

        カメラの向きとcenterOfInterestをMFnCameraで更新する。
        fast=True専用でUndoには記録しない。Undo設定は変更しない。

        Args:
            point (Iterable[float]): 注視点のXYZ座標(cm)。視点と異なる位置。
            worldSpace (bool): Trueはワールド空間、Falseはカメラ空間。既定True。
            ws (bool): worldSpaceの短縮名。同時指定はできない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 型または長短名の指定が不正な場合。
            ValueError: 非有限値、または視点と注視点が一致する場合。
            RuntimeError: ロック・入力接続・参照がある場合、またはMayaが更新を拒否した場合。
            NotImplementedError: fast=False、または親が通常Transformでないかインスタンスの場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=True)
        space = self._space(worldSpace)
        point = om2.MPoint(_finite_vector(point, 3, "point"))
        if (point - self.mfn().eyePoint(space)).length() < 1e-12:
            raise ValueError("注視点は視点と異なる位置で指定してください")
        self._require_view_edit(fast)
        self.mfn().setCenterOfInterestPoint(point, space)

    def getAspectRatio(self):
        """カメラのフィルム開口のアスペクト比を取得する。

        Returns:
            float: MFnCamera.aspectRatioの値。レンダー解像度の比ではない。
        """
        return self.mfn().aspectRatio()

    def setAspectRatio(self, value):
        """カメラのフィルム開口の縦横比を変更する。

        レンダー解像度の縦横比は変更しない。MayaのverticalLock設定に従って開口を補正する。
        fast引数は持たない(1回のcmdsで更新するため)。

        Args:
            value (float): 正の縦横比(幅/高さ)。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: valueが有限の正数でない場合。
            RuntimeError: カメラが無効、またはMayaが更新を拒否した場合。
        """
        value = _finite(value, "value")
        if value <= 0:
            raise ValueError("valueは正の縦横比で指定してください")
        self._require_valid("縦横比の変更")
        cmds.camera(self.getFullName(), edit=True, aspectRatio=value)

    def getParameterLimits(self):
        """カメラのアスペクト比・フィルム開口・焦点距離の制限値を取得する。

        現在のアトリビュート値ではなく、Mayaが定める設定範囲を返す。

        Returns:
            dict: aspectRatio、filmAperture(インチ)、focalLength(mm)をキーとし、各値は(最小, 最大)。

        Raises:
            RuntimeError: カメラが無効な場合。
        """
        fn = self.mfn()
        return {
            "aspectRatio": tuple(fn.getAspectRatioLimits()),
            "filmAperture": tuple(fn.getFilmApertureLimits()),
            "focalLength": tuple(fn.getFocalLengthLimits()),
        }

    def hasSamePerspective(self, other):
        """別のカメラがMayaの判定で同じパースペクティブを持つか調べる。

        Args:
            other (Camera): 比較するカメラシェイプ。

        Returns:
            bool: MFnCamera.hasSamePerspectiveの結果。全アトリビュートの一致判定ではない。

        Raises:
            TypeError: otherがCameraでない場合。
            RuntimeError: カメラが無効な場合。
        """
        if not isinstance(other, Camera):
            raise TypeError("otherはCameraで指定してください")
        return self.mfn().hasSamePerspective(other.mpath())

    def getEyePoint(self, worldSpace=_UNSET, *, ws=_UNSET):
        """カメラの位置を取得する。

        ``MFnCamera.eyePoint`` の値を返す。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル(オブジェクト)空間で取得する。既定はTrue。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 位置(cm)。

        Raises:
            TypeError: worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: ノードが削除済みの場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=True)
        return _vectors_of_points([self.mfn().eyePoint(self._space(worldSpace))])[0]

    def getViewDirection(self, worldSpace=_UNSET, *, ws=_UNSET):
        """カメラの視線の向きを取得する。

        ``MFnCamera.viewDirection`` の値を返す。ローカル空間では -Z の向きになる。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル(オブジェクト)空間で取得する。既定はTrue。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 長さ1の向き。

        Raises:
            TypeError: worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: ノードが削除済みの場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=True)
        return Vector(self.mfn().viewDirection(self._space(worldSpace))).normal()

    def getUpDirection(self, worldSpace=_UNSET, *, ws=_UNSET):
        """カメラの上の向きを取得する。

        ``MFnCamera.upDirection`` の値を返す。ローカル空間では +Y の向きになる。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル(オブジェクト)空間で取得する。既定はTrue。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 長さ1の向き。

        Raises:
            TypeError: worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: ノードが削除済みの場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=True)
        return Vector(self.mfn().upDirection(self._space(worldSpace))).normal()

    def setUpDirection(self, direction):
        """ワールド空間の上方向を基準にカメラのロールを変更する。

        視線に直交する成分をMayaが上方向として使う。視線と平行な指定は拒否する。
        fast引数は持たない(1回のcmdsで更新するため)。

        Args:
            direction (Iterable[float]): ワールド空間の方向ベクトル。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: directionが3つの数値でない場合。
            ValueError: 非有限値、ゼロベクトル、または視線と平行な場合。
            RuntimeError: カメラが無効、またはMayaが更新を拒否した場合。
        """
        direction = Vector(_finite_vector(direction, 3, "direction"))
        if (direction ^ self.getViewDirection()).length() < 1e-12:
            raise ValueError("directionは視線と平行でない方向で指定してください")
        cmds.camera(self.getFullName(), edit=True, worldUp=list(direction))

    def getProjectionMatrix(self):
        """投影マトリクスを取得する。

        カメラ空間からクリップ空間へ写すマトリクスで、``MFnCamera.projectionMatrix`` の値を返す。
        焦点距離・フィルムバック・クリップ面から決まる。

        ワールドの点を画面へ写すには、次の順に計算する(行ベクトルの規約)。

        1. カメラのTransformの逆マトリクス(``worldInverseMatrix``)を掛ける。
        2. このマトリクスを掛ける。
        3. w で割る。

        Returns:
            Matrix: 投影マトリクス(``om2.MFloatMatrix`` の値を倍精度にしたもの)。

        Raises:
            RuntimeError: ノードが削除済みの場合。
        """
        matrix = self.mfn().projectionMatrix()
        return Matrix([matrix.getElement(row, column) for row in range(4) for column in range(4)])

    def getFilmFrustum(self, distance, *, applyPanZoom=False):
        """指定距離でのフィルムゲートの寸法とフィルム面のオフセットを取得する。

        MFnCamera.getFilmFrustumの4値を返す。透視投影の幅・高さはdistanceに比例し、
        正投影ではdistanceによらない。オフセットは距離面への投影値ではなく、
        Mayaが返すフィルム面の値。UIの距離単位を変更しても戻り値は変わらない。

        Args:
            distance (float): カメラからの距離(cm)。正の有限値。
            applyPanZoom (bool): Trueなら有効な2D pan/zoomを反映する。既定False。

        Returns:
            tuple[float, float, float, float]: (幅cm, 高さcm, 横オフセットinch, 縦オフセットinch)。
                正投影ではフィルムオフセットを含まず、指定時のpanのみをオフセットに反映する。

        Raises:
            TypeError: distanceが数値以外、またはapplyPanZoomがbool以外の場合。
            ValueError: distanceが正の有限値でない場合。
            RuntimeError: カメラが無効な場合。
        """
        distance = _finite(distance, "distance")
        if distance <= 0:
            raise ValueError("distanceは正の数値で指定してください")
        _require_bool(applyPanZoom, "applyPanZoom")
        return tuple(self.mfn().getFilmFrustum(distance, applyPanZoom))

    def getRenderingFrustum(self, aspectRatio):
        """レンダーに使うニアクリップ面の撮影範囲を取得する。

        MFnCamera.getRenderingFrustumへ指定縦横比を渡す。表示用のoverscan等の選択はgetViewingFrustumで行う。

        Args:
            aspectRatio (float): 横幅/高さ。正の有限値。

        Returns:
            tuple[float, float, float, float]: (左, 右, 下, 上)。カメラ空間の距離(cm)。

        Raises:
            TypeError: aspectRatioが数値以外の場合。
            ValueError: aspectRatioが正の有限値でない場合。
            RuntimeError: カメラが無効な場合。
        """
        aspect = _finite(aspectRatio, "aspectRatio")
        if aspect <= 0:
            raise ValueError("aspectRatioは正の数値で指定してください")
        return tuple(self.mfn().getRenderingFrustum(aspect))

    def getViewingFrustum(self, aspectRatio, *, applyOverscan=False, applySqueeze=False, applyPanZoom=False):
        """表示条件に対応するニアクリップ面の撮影範囲を取得する。

        Args:
            aspectRatio (float): 表示の横幅/高さ。正の有限値。
            applyOverscan (bool): overscanを反映する。既定False。
            applySqueeze (bool): lensSqueezeRatioを反映する。既定False。
            applyPanZoom (bool): 2D pan/zoomを反映する。既定False。

        Returns:
            tuple[float, float, float, float]: (左, 右, 下, 上)。カメラ空間の距離(cm)。

        Raises:
            TypeError: 数値・boolの引数の型が不正な場合。
            ValueError: aspectRatioが正の有限値でない場合。
            RuntimeError: カメラが無効な場合。
        """
        aspect = _finite(aspectRatio, "aspectRatio")
        if aspect <= 0:
            raise ValueError("aspectRatioは正の数値で指定してください")
        _require_bool(applyOverscan, "applyOverscan")
        _require_bool(applySqueeze, "applySqueeze")
        _require_bool(applyPanZoom, "applyPanZoom")
        return tuple(self.mfn().getViewingFrustum(aspect, applyOverscan, applySqueeze, applyPanZoom))

    def getViewParameters(self, aspectRatio, *, applyOverscan=False, applySqueeze=False, applyPanZoom=False):
        """表示条件を反映したフィルム開口とオフセットを取得する。

        撮影範囲の計算に使う中間値で、ニアクリップ面の寸法ではない。

        Args:
            aspectRatio (float): 表示の横幅/高さ。正の有限値。
            applyOverscan (bool): overscanを反映する。既定False。
            applySqueeze (bool): lensSqueezeRatioを反映する。既定False。
            applyPanZoom (bool): 2D pan/zoomを反映する。既定False。

        Returns:
            tuple[float, float, float, float]: (水平開口, 垂直開口, 水平オフセット, 垂直オフセット)。
                透視カメラはインチ、平行投影ではオブジェクト空間の距離(cm)。

        Raises:
            TypeError: 数値・boolの引数の型が不正な場合。
            ValueError: aspectRatioが正の有限値でない場合。
            RuntimeError: カメラが無効な場合。
        """
        aspect = _finite(aspectRatio, "aspectRatio")
        if aspect <= 0:
            raise ValueError("aspectRatioは正の数値で指定してください")
        _require_bool(applyOverscan, "applyOverscan")
        _require_bool(applySqueeze, "applySqueeze")
        _require_bool(applyPanZoom, "applyPanZoom")
        return tuple(self.mfn().getViewParameters(aspect, applyOverscan, applySqueeze, applyPanZoom))

    def getPortFieldOfView(self, width, height, *, unit="deg"):
        """表示の幅と高さに対応する水平・垂直画角を取得する。

        Args:
            width (int): 表示の幅。正の整数。
            height (int): 表示の高さ。正の整数。
            unit (str): 角度の単位。deg(既定)またはrad。

        Returns:
            tuple[float, float]: (水平画角, 垂直画角)。MFnCamera.getPortFieldOfViewの結果。

        Raises:
            TypeError: width・heightが整数以外の場合。
            ValueError: width・heightが正でないか、unitが未対応の場合。
            RuntimeError: カメラが無効な場合。
        """
        for value, name in ((width, "width"), (height, "height")):
            if type(value) is not int:
                raise TypeError(f"{name}は整数で指定してください")
            if value <= 0:
                raise ValueError(f"{name}は正の整数で指定してください")
        angle_unit = _angle_unit(unit)
        return tuple(_from_radians(value, angle_unit) for value in self.mfn().getPortFieldOfView(width, height))

    def getPostProjectionMatrix(self):
        """フィルム面のロール等に使う後段の投影マトリクスを取得する。

        Returns:
            Matrix: MFnCamera.postProjectionMatrixの独立した値。通常の投影マトリクスは含めない。

        Raises:
            RuntimeError: カメラが無効な場合。
        """
        matrix = self.mfn().postProjectionMatrix()
        return Matrix([matrix.getElement(row, column) for row in range(4) for column in range(4)])

    def isOrtho(self):
        """正投影のカメラか調べる。

        ``orthographic`` アトリビュートの値を返す。

        Returns:
            bool: 正投影ならTrue、透視投影ならFalse。

        Raises:
            RuntimeError: ノードが削除済みの場合。
        """
        return bool(self.mfn().isOrtho())

    def _require_view_edit(self, fast):
        """カメラと親Transformの直接編集条件を確認する。

        Args:
            fast (bool): Undoなしの更新を明示したか。
        """
        _require_bool(fast, "fast")
        if not fast:
            raise NotImplementedError("カメラ視点の直接更新はfast=True専用です")
        parent = self.getParent()
        if parent.getType() != "transform" or self.isInstanced() or parent.isInstanced():
            raise NotImplementedError("非インスタンスの通常Transform下のカメラだけに対応しています")
        for node in (self, parent):
            dependency = node._dependency_fn()
            if dependency.isLocked or dependency.isFromReferencedFile:
                raise RuntimeError("ロック・参照カメラの視点は直接編集できません")
        for name in ("translate", "rotate", "rotateAxis", "rotateOrder", "rotatePivot", "rotatePivotTranslate", "scale", "shear", "offsetParentMatrix"):
            plug = parent.getPlug(name)
            require_writable(plug.mplug())
            for child in plug.getChildren() if plug.mplug().isCompound else ():
                require_writable(child.mplug())
        for plug in self.getPlugs():
            if plug.mplug().attribute().hasFn(om2.MFn.kMessageAttribute) or not om2.MFnAttribute(plug.mplug().attribute()).writable:
                continue
            require_writable(plug.mplug())

    @staticmethod
    def _space(worldSpace):
        """worldSpaceを検証し、om2の空間を返す。

        Args:
            worldSpace (bool): Trueはワールド空間。

        Returns:
            int: ``om2.MSpace.kWorld`` または ``om2.MSpace.kObject``。

        Raises:
            TypeError: worldSpaceがbool以外の場合。
        """
        return om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
