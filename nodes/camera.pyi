# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya のカメラシェイプを扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.fastWrite import require_writable
from ..decorator import _pick_alias, _require_bool
from ..maths.matrix import Matrix
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _angle_unit, _finite, _finite_vector, _from_radians, _require_choice, _world_space
from .shape import Shape
from typing import Iterable

_POINT_KINDS: tuple
_DIRECTION_KINDS: tuple
_PROJECTION_KINDS: tuple


class Camera(Shape):
    """Mayaのcameraシェイプノードを保持し、撮影条件と投影を扱う。

    手動クリップ設定の照会は ``getPlug("bestFitClippingPlanes").get()`` を使う。
    これはMFnCamera.isClippingPlanesの取得値に対応する。似た名前のclippingPlanesは未使用のアトリビュート。
    """
    def mfn(self) -> om2.MFnCamera:
        """このカメラのfunction set(``om2.MFnCamera``)を取得する。

        呼び出すたびに、このオブジェクトが持つDAGパスから新しく作る。

        Returns:
            om2.MFnCamera: このカメラのfunction set。
        """
        ...
    def setView(self, eye: Iterable[float], direction: Iterable[float], up: Iterable[float], fieldOfView: float, aspectRatio: float, *, unit: str = ..., fast: bool = ..., check: bool = ...) -> None:
        """ワールド空間の視点・視線・上方向と画角をまとめて変更する。

        MFnCamera.setを使い、親Transformとカメラの投影設定を変更する。
        fast=True専用でUndoには記録しない。Undo設定は変更しない。
        途中でMayaエラーが発生した場合、更新前への復元は保証しない。
        カメラ・親Transformのノードのロックとリファレンスは、checkに関係なく確かめる。

        Args:
            eye (Iterable[float]): 視点のワールド座標(cm)。
            direction (Iterable[float]): ゼロでない視線方向。
            up (Iterable[float]): 視線と平行でない上方向。
            fieldOfView (float): 水平画角。0より大きく180度未満。
            aspectRatio (float): 正の横幅/高さ比。
            unit (str): 画角の単位。既定deg。radも指定できる。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、カメラと親Transformのアトリビュートが書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 引数の型が不正な場合(fast・checkがbool以外の場合を含む)。
            ValueError: 座標・方向・画角・比率が不正な場合。
            RuntimeError: ノードがロックされているかリファレンスの場合、check=Trueでアトリビュートがロック・入力の接続で書き込めない場合、
                またはMayaが更新を拒否した場合。
            NotImplementedError: fast=False、または親が通常Transformでないかインスタンスの場合。

        Note:
            広い画角は、Mayaが焦点距離とフィルム開口の範囲で切り詰める(Mayaの制限)。範囲を超える画角
            (既定の開口で縦横比1.5なら約176.8度より広い画角)は、例外にならずに切り詰めた画角になる。
            書いた画角は :meth:`getFieldOfView` で確かめられる。
        """
        ...
    def copyViewFrom(self, camera: str | Camera, *, fast: bool = ..., check: bool = ...) -> None:
        """別のカメラの視点・透視投影に関わる設定をコピーする。

        MFnCamera.copyViewFromの対象設定をコピーする。全アトリビュートの複製ではない。
        コピー先の親Transformも変わる。fast=True専用でUndoには記録しない。
        コピー先のカメラ・親Transformのノードのロックとリファレンスは、checkに関係なく確かめる。

        Args:
            camera (str | Camera): コピー元のカメラShape。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、コピー先のカメラと親Transformのアトリビュートが書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: cameraがカメラShapeでない場合、またはfast・checkがboolでない場合。
            RuntimeError: ノードがロックされているかリファレンスの場合、check=Trueでアトリビュートがロック・入力の接続で書き込めない場合、
                またはカメラが無効な場合。
            NotImplementedError: fast=False、またはコピー先が対応しない階層の場合。
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
    def getFieldOfView(self, *, port: tuple[int, int] | None = ..., unit: str = ...) -> tuple[float, float]:
        """水平と垂直の画角を取得する。``port`` を渡すと、その表示の幅と高さに対応する画角を取得する。

        既定では ``MFnCamera.horizontalFieldOfView``・``verticalFieldOfView`` の値を返す。
        画角は、焦点距離とフィルムバック(``horizontalFilmAperture``・``verticalFilmAperture``)から次の式で求まる。
        Mayaは1mmを0.03937インチとして換算する。

        ``2 * atan(フィルムバック(インチ) / 0.03937 / 2 / 焦点距離(mm))``

        Film Fitや解像度の縦横比で切り取られる分は含まない。
        ``port`` を渡したときは ``MFnCamera.getPortFieldOfView`` の結果を返す。

        Args:
            port (tuple[int, int] | None): 表示の (幅, 高さ)。どちらも正の整数。Noneならカメラ自身の画角。既定はNone。
            unit (str): 戻り値の角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。
                ``"degree"`` などの別名も使える。

        Returns:
            tuple[float, float]: (水平の画角, 垂直の画角)。

        Raises:
            TypeError: unitが文字列・None以外の場合、portが2つの値の並びでない場合、または幅・高さが整数以外の場合。
            ValueError: unitに使えない単位名を指定した場合、または幅・高さが正でない場合。
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
    def setFocusDistance(self, *, near: float | None = ..., far: float | None = ...) -> None:
        """近側か遠側の合焦距離を指定して、カメラの焦点位置を補正する。

        ``near`` と ``far`` のどちらか1つを指定する。Maya標準の補正に従い、反対側の合焦距離も変わる
        (そのため、両方を同時には指定できない)。クリップ面の設定ではない。
        fast引数は持たない(1回のcmdsで更新するため)。

        Args:
            near (float | None): 近側の合焦距離。正の有限距離(cm)。既定はNone。
            far (float | None): 遠側の合焦距離。正の有限距離(cm)。既定はNone。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: nearとfarを両方指定したか、どちらも指定しない場合、または距離が数値でない場合。
            ValueError: 距離が有限の正数でない場合。
            RuntimeError: カメラが無効、またはMayaが更新を拒否した場合。
        """
        ...
    def getPoint(self, worldSpace: bool = ..., *, kind: str = ..., ws: bool = ...) -> Vector:
        """カメラの位置(視点)を取得する。``kind="centerOfInterest"`` なら、注視点を取得する。

        ``MFnCamera.eyePoint``・``centerOfInterestPoint`` の値を返す。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル(オブジェクト)空間で取得する。既定はTrue。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            kind (str): 取得する点。``"eye"`` はカメラの位置、``"centerOfInterest"`` は注視点。既定は ``"eye"``。

        Returns:
            Vector: 位置(cm)。

        Raises:
            TypeError: kindが文字列でない場合、worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: kindが対応していない名前の場合。
            RuntimeError: ノードが削除済みの場合。
        """
        ...
    def setPoint(self, point: Iterable[float], worldSpace: bool = ..., *, kind: str = ..., fast: bool = ..., check: bool = ..., ws: bool = ...) -> None:
        """カメラの位置(視点)を変更する。``kind="centerOfInterest"`` なら、視点を保ちながら注視点を変更する。

        - ``"eye"``: ``MFnCamera.setEyePoint`` で、注視点を保ったままカメラを動かす(カメラは注視点を向き続けるので、向きは変わる)。
        - ``"centerOfInterest"``: ``MFnCamera.setCenterOfInterestPoint`` で、カメラの向きとcenterOfInterestを更新する。

        fast=True専用でUndoには記録しない。Undo設定は変更しない。
        カメラ・親Transformのノードのロックとリファレンスは、checkに関係なく確かめる。

        Args:
            point (Iterable[float]): XYZ座標(cm)。注視点は、視点と異なる位置。
            worldSpace (bool): Trueはワールド空間、Falseはカメラ空間。既定True。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            kind (str): 変更する点。``"eye"`` はカメラの位置、``"centerOfInterest"`` は注視点。既定は ``"eye"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、カメラと親Transformのアトリビュートが書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 型または長短名の指定が不正な場合(fast・checkがbool以外の場合を含む)。
            ValueError: kindが対応していない名前の場合、非有限値、または視点と注視点が一致する場合。
            RuntimeError: ノードがロックされているかリファレンスの場合、check=Trueでアトリビュートがロック・入力の接続で書き込めない場合、
                またはMayaが更新を拒否した場合。
            NotImplementedError: fast=False、または親が通常Transformでないかインスタンスの場合。
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
            TypeError: valueが数値でない場合(boolを含む)。
            ValueError: valueが有限の正数でない場合。
            RuntimeError: カメラが無効、またはMayaが更新を拒否した場合。
        """
        ...
    def getDirection(self, worldSpace: bool = ..., *, kind: str = ..., ws: bool = ...) -> Vector:
        """カメラの視線の向きを取得する。``kind="up"`` なら、カメラの上の向きを取得する。

        ``MFnCamera.viewDirection``・``upDirection`` の値を返す。ローカル空間では、視線は -Z、上は +Y の向きになる。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル(オブジェクト)空間で取得する。既定はTrue。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            kind (str): 取得する向き。``"view"`` は視線、``"up"`` は上。既定は ``"view"``。

        Returns:
            Vector: 長さ1の向き。

        Raises:
            TypeError: kindが文字列でない場合、worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: kindが対応していない名前の場合。
            RuntimeError: ノードが削除済みの場合。
        """
        ...
    def setDirection(self, direction: Iterable[float], *, kind: str) -> None:
        """ワールド空間の上方向を基準に、カメラのロールを変更する(``kind="up"``)。

        視線に直交する成分をMayaが上方向として使う。視線と平行な指定は拒否する。
        fast引数は持たない(1回のcmdsで更新するため)。
        視線の向き(``kind="view"``)だけを変える操作は無い。視点・視線・上方向をまとめて変えるときは :meth:`setView`、
        注視点で向きを変えるときは ``setPoint(point, kind="centerOfInterest", fast=True)`` を使う。

        Args:
            direction (Iterable[float]): ワールド空間の方向ベクトル。
            kind (str): 変更する向き。:meth:`getDirection` と同じ名前で指定する。変更できるのは ``"up"`` だけ。
                取得と既定を取り違えないよう、省略できない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: kindが文字列でない場合、またはdirectionが3つの数値でない場合。
            ValueError: kindが対応していない名前の場合、非有限値、ゼロベクトル、または視線と平行な場合。
            RuntimeError: カメラが無効、またはMayaが更新を拒否した場合。
            NotImplementedError: kind="view"の場合。
        """
        ...
    def getProjectionMatrix(self, *, kind: str = ...) -> Matrix:
        """投影マトリクスを取得する。``kind="post"`` なら、フィルム面のロール等に使う後段の投影マトリクスを取得する。

        カメラ空間からクリップ空間へ写すマトリクスで、``MFnCamera.projectionMatrix`` の値を返す。
        焦点距離・フィルムバック・クリップ面から決まる。

        ワールドの点を画面へ写すには、次の順に計算する(行ベクトルの規約)。

        1. カメラのTransformの逆マトリクス(``worldInverseMatrix``)を掛ける。
        2. このマトリクスを掛ける。
        3. w で割る。

        ``kind="post"`` は ``MFnCamera.postProjectionMatrix`` の値で、通常の投影マトリクスは含めない。

        Args:
            kind (str): 取得するマトリクスの種類。``"projection"`` は投影マトリクス、``"post"`` は後段の投影マトリクス。
                既定は ``"projection"``。

        Returns:
            Matrix: 投影マトリクス(``om2.MFloatMatrix`` の値を倍精度にした、独立した値)。

        Raises:
            TypeError: kindが文字列でない場合。
            ValueError: kindが対応していない名前の場合。
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
    def getFrustum(self, aspectRatio: float, *, kind: str = ..., applyOverscan: bool = ..., applySqueeze: bool = ..., applyPanZoom: bool = ...) -> tuple[float, float, float, float]:
        """ニアクリップ面の撮影範囲を取得する。

        - ``"viewing"`` (既定): 表示条件に対応する範囲(``MFnCamera.getViewingFrustum``)。overscan等を反映するかを選べる。
        - ``"rendering"``: レンダーに使う範囲(``MFnCamera.getRenderingFrustum``)。``apply…`` の引数は指定できない。

        指定した距離でのフィルムゲートの寸法(戻り値の意味が違う)は :meth:`getFilmFrustum` で取得する。

        Args:
            aspectRatio (float): 横幅/高さ。正の有限値。
            kind (str): 範囲の種類。``"viewing"``・``"rendering"``。既定は ``"viewing"``。
            applyOverscan (bool): overscanを反映する。既定False。
            applySqueeze (bool): lensSqueezeRatioを反映する。既定False。
            applyPanZoom (bool): 2D pan/zoomを反映する。既定False。

        Returns:
            tuple[float, float, float, float]: (左, 右, 下, 上)。カメラ空間の距離(cm)。

        Raises:
            TypeError: kindが文字列でない場合、数値・boolの引数の型が不正な場合、
                またはkind="rendering"でapplyOverscan・applySqueeze・applyPanZoomを指定した場合。
            ValueError: kindが対応していない名前の場合、またはaspectRatioが正の有限値でない場合。
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
    def isOrtho(self) -> bool:
        """正投影のカメラか調べる。

        ``orthographic`` アトリビュートの値を返す。

        Returns:
            bool: 正投影ならTrue、透視投影ならFalse。

        Raises:
            RuntimeError: ノードが削除済みの場合。
        """
        ...
    def _require_view_edit(self, fast: bool, check: bool):
        """カメラと親Transformの直接編集条件を確認する。

        fast・階層・ノードのロック・リファレンスは常に、アトリビュートのロック・入力の接続はcheck=Trueのときだけ確かめる。

        Args:
            fast (bool): Undoなしの更新を明示したか。
            check (bool): アトリビュートが書き込めるかも確かめるか。

        Raises:
            TypeError: fast・checkがbool以外の場合。
            NotImplementedError: fast=False、または親が通常Transformでないかインスタンスの場合。
            RuntimeError: ノードがロックされているかリファレンスの場合、またはcheck=Trueでアトリビュートが書き込めない場合。
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
