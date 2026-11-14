"""Maya のカメラシェイプを扱う。"""

import maya.api.OpenMaya as om2

from ..decorator import _pick_alias
from ..maths.matrix import Matrix
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _angle_unit, _from_radians, _world_space
from .shape import Shape


class Camera(Shape):
    """Mayaのcameraシェイプノードを扱うクラス。"""

    def mfn(self):
        """このカメラのfunction set(``om2.MFnCamera``)を取得する。

        呼び出すたびに、このオブジェクトが持つDAGパスから新しく作る。

        Returns:
            om2.MFnCamera: このカメラのfunction set。
        """
        return om2.MFnCamera(self.mpath())

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

    def isOrtho(self):
        """正投影のカメラか調べる。

        ``orthographic`` アトリビュートの値を返す。

        Returns:
            bool: 正投影ならTrue、透視投影ならFalse。

        Raises:
            RuntimeError: ノードが削除済みの場合。
        """
        return bool(self.mfn().isOrtho())

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
