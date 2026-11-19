# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya のカメラシェイプを扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import _pick_alias, _require_bool
from ..maths.matrix import Matrix
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _angle_unit, _finite, _finite_vector, _from_radians, _world_space
from .shape import Shape
from typing import Iterable



class Camera(Shape):
    """Mayaのcameraシェイプノードを扱うクラス。"""
    def mfn(self) -> om2.MFnCamera:
        """このカメラのfunction set(``om2.MFnCamera``)を取得する。

        呼び出すたびに、このオブジェクトが持つDAGパスから新しく作る。

        Returns:
            om2.MFnCamera: このカメラのfunction set。
        """
        ...
    def getDepthOfFieldRange(self) -> tuple[float, float]:
        """被写界深度を再計算し、近側と遠側の合焦距離を取得する。

        MFnCamera.computeDepthOfFieldでMaya内部の計算結果を更新する。
        カメラのアトリビュートやUndo設定は変更しない。レンダラー独自の被写界深度は扱わない。

        Returns:
            tuple[float, float]: (近側, 遠側)の距離(cm)。Mayaの計算結果をそのまま返す。

        Raises:
            RuntimeError: カメラが無効、またはMayaが計算を拒否した場合。
        """
        ...
    def isVerticalLocked(self) -> bool:
        """縦横比変更時に垂直フィルム開口を維持する設定か調べる。

        アトリビュートの編集ロックとは異なるMayaのカメラ設定。

        Returns:
            bool: 垂直フィルム開口を維持する場合はTrue。
        """
        ...
    def setVerticalLocked(self, state: bool = ...) -> None:
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
        ...
    def getFocalLength(self) -> float:
        """焦点距離を取得する。

        Returns:
            float: Mayaの焦点距離。
        """
        ...
    def getFieldOfView(self, *, unit: str = ...) -> tuple[float, float]:
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
        ...
    def setFieldOfView(self, angle: float, *, vertical: bool = ..., unit: str = ...) -> None:
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
        ...
    def setNearFocusDistance(self, distance: float) -> None:
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
        ...
    def setFarFocusDistance(self, distance: float) -> None:
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
        ...
    def getCenterOfInterestPoint(self, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
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
        ...
    def getAspectRatio(self) -> float:
        """カメラのフィルム開口のアスペクト比を取得する。

        Returns:
            float: MFnCamera.aspectRatioの値。レンダー解像度の比ではない。
        """
        ...
    def setAspectRatio(self, value: float) -> None:
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
        ...
    def getParameterLimits(self) -> dict:
        """カメラのアスペクト比・フィルム開口・焦点距離の制限値を取得する。

        現在のアトリビュート値ではなく、Mayaが定める設定範囲を返す。

        Returns:
            dict: aspectRatio、filmAperture(インチ)、focalLength(mm)をキーとし、各値は(最小, 最大)。

        Raises:
            RuntimeError: カメラが無効な場合。
        """
        ...
    def hasSamePerspective(self, other: Camera) -> bool:
        """別のカメラがMayaの判定で同じパースペクティブを持つか調べる。

        Args:
            other (Camera): 比較するカメラシェイプ。

        Returns:
            bool: MFnCamera.hasSamePerspectiveの結果。全アトリビュートの一致判定ではない。

        Raises:
            TypeError: otherがCameraでない場合。
            RuntimeError: カメラが無効な場合。
        """
        ...
    def getEyePoint(self, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
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
        ...
    def getViewDirection(self, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
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
        ...
    def getUpDirection(self, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
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
        ...
    def setUpDirection(self, direction: Iterable[float]) -> None:
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
        ...
    def getProjectionMatrix(self) -> Matrix:
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
        ...
    def getFilmFrustum(self, distance: float, *, applyPanZoom: bool = ...) -> tuple[float, float, float, float]:
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
        ...
    def getRenderingFrustum(self, aspectRatio: float) -> tuple[float, float, float, float]:
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
        ...
    def getViewingFrustum(self, aspectRatio: float, *, applyOverscan: bool = ..., applySqueeze: bool = ..., applyPanZoom: bool = ...) -> tuple[float, float, float, float]:
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
        ...
    def getViewParameters(self, aspectRatio: float, *, applyOverscan: bool = ..., applySqueeze: bool = ..., applyPanZoom: bool = ...) -> tuple[float, float, float, float]:
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
        ...
    def getPortFieldOfView(self, width: int, height: int, *, unit: str = ...) -> tuple[float, float]:
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
        ...
    def getPostProjectionMatrix(self) -> Matrix:
        """フィルム面のロール等に使う後段の投影マトリクスを取得する。

        Returns:
            Matrix: MFnCamera.postProjectionMatrixの独立した値。通常の投影マトリクスは含めない。

        Raises:
            RuntimeError: カメラが無効な場合。
        """
        ...
    def isOrtho(self) -> bool:
        """正投影のカメラか調べる。

        ``orthographic`` アトリビュートの値を返す。

        Returns:
            bool: 正投影ならTrue、透視投影ならFalse。

        Raises:
            RuntimeError: ノードが削除済みの場合。
        """
        ...
    @staticmethod
    def _space(worldSpace: bool) -> int:
        """worldSpaceを検証し、om2の空間を返す。

        Args:
            worldSpace (bool): Trueはワールド空間。

        Returns:
            int: ``om2.MSpace.kWorld`` または ``om2.MSpace.kObject``。

        Raises:
            TypeError: worldSpaceがbool以外の場合。
        """
        ...
