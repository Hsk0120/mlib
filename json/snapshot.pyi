# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""JSONへ保存・復元するデータに共通する流れ(取得・保存・読み込み・検査・適用)。

``ValidationReport`` は、:class:`Snapshot` の検査と適用だけが返す小さな結果のクラスなので、同じファイルに置く。
"""

import maya.api.OpenMaya as om2
from .. import logger
from ..decorator import _edit_context
from . import file
from .nameMapping import NameMapping
from typing import Any, Iterable
import os
import pathlib



class ValidationReport:
    """適用する前の検査の結果と、適用した結果を持つ。

    - ``missing``: 対応するノードが見つからなかったもの。
    - ``skipped``: ロックや接続などで書けず、飛ばしたもの。
    - ``errors``: 適用できない問題(頂点数の違いなど)。

    ``errors`` があると、それぞれの種類の ``apply``
    (:meth:`PoseSnapshot.apply <mlib.json.poseSnapshot.PoseSnapshot.apply>` など)は何も変えずに例外にする。
    """
    def __init__(self) -> None:
        """空の報告を作る。"""
        ...
    def __repr__(self) -> str:
        """それぞれの項目の件数を含む表記を返す。

        Returns:
            str: ``ValidationReport(missing=1, skipped=0, errors=0)`` の形式。
        """
        ...
    @property
    def missing(self) -> list[str]:
        """見つからなかったノードなどの名前を返す。

        Returns:
            list[str]: 名前の対応づけを当てた後の名前。新しいlist。
        """
        ...
    @property
    def skipped(self) -> list[str]:
        """書けずに飛ばしたものの説明を返す。

        Returns:
            list[str]: ``"<名前>: <理由>"`` の形の説明。新しいlist。
        """
        ...
    @property
    def errors(self) -> list[str]:
        """適用できない問題の説明を返す。

        Returns:
            list[str]: 説明。新しいlist。
        """
        ...
    @property
    def valid(self) -> bool:
        """適用できるか(``errors`` が無いか)を返す。

        Returns:
            bool: errorsが空ならTrue。missing・skippedがあってもTrue。
        """
        ...
    def addMissing(self, name: str):
        """見つからなかったものを記録する。同じ名前は1回だけ記録する。

        Args:
            name (str): 名前の対応づけを当てた後の名前。
        """
        ...
    def addSkipped(self, name: str, reason: str):
        """書けずに飛ばしたものを記録する。

        Args:
            name (str): 飛ばしたものの名前。
            reason (str): 理由(``"locked"`` など)。
        """
        ...
    def addError(self, message: str):
        """適用できない問題を記録する。

        Args:
            message (str): 問題の説明。
        """
        ...
    def warn(self, label: str):
        """missing・skippedがあれば、まとめて警告を1回出す。

        Args:
            label (str): 警告の先頭に付ける名前(``"PoseSnapshot"`` など)。
        """
        ...


class Snapshot:
    """シーンのデータを取得し、JSONへ保存・復元するクラスに共通する基底クラス。

    それぞれの種類は、:attr:`FORMAT`・:attr:`VERSION` と、``capture`` (取得)・``_validate`` (検査)・
    ``_apply`` (適用)を書く。持っているデータは数学型を含む辞書で、:meth:`toData` で取得できる。
    名前の対応づけ(``nameMap``・``replace``・``namespaceMap``)は :class:`NameMapping` の規則に従う。
    """
    FORMAT: None
    VERSION: None
    def __init__(self, data: dict, header: file.Header | None = ...) -> None:
        """データを持たせる。ふつうは ``capture`` か :meth:`load` で作る。

        Args:
            data (dict): それぞれの種類の形式のデータ。コピーして持つ。
            header (file.Header | None): 読み込んだファイルのヘッダー。取得したばかりならNone。

        Raises:
            TypeError: dataが辞書でない場合。
            ValueError: データの形が種類と合わない場合。
        """
        ...
    def __repr__(self) -> str:
        """クラス名と形式を含む表記を返す。

        Returns:
            str: ``PoseSnapshot('mlib.pose', 1)`` の形式。
        """
        ...
    @classmethod
    def capture(cls, *args: object, **kwargs: object):
        """シーンからデータを取得する。それぞれの種類が書く。

        Args:
            *args (object): それぞれの種類の ``capture`` の位置引数。
            **kwargs (object): それぞれの種類の ``capture`` のキーワード引数。

        Raises:
            NotImplementedError: 基底クラスで呼んだ場合。
        """
        ...
    @classmethod
    def fromData(cls, data: dict) -> Snapshot:
        """:meth:`toData` の辞書から作る。

        Args:
            data (dict): 種類の形式のデータ。

        Returns:
            Snapshot: 呼び出したクラスの新しいインスタンス。

        Raises:
            TypeError: dataが辞書でない場合。
            ValueError: データの形が種類と合わない場合。
        """
        ...
    @classmethod
    def load(cls, path: str | os.PathLike) -> Snapshot:
        """JSONファイルを読み込んで作る。

        Args:
            path (str | os.PathLike): :meth:`save` で書き出したファイル。

        Returns:
            Snapshot: 呼び出したクラスの新しいインスタンス。:attr:`header` を持つ。

        Raises:
            ValueError: 形式名・版が違う場合、またはデータの形が種類と合わない場合。
            OSError: 読み込みに失敗した場合。
        """
        ...
    @property
    def header(self) -> file.Header | None:
        """読み込んだファイルのヘッダーを返す。

        Returns:
            file.Header | None: :meth:`load` で作った場合のヘッダー。取得したばかりならNone。
        """
        ...
    def toData(self) -> dict:
        """持っているデータのコピーを返す。

        Returns:
            dict: 数学型を含む辞書。変えても、このオブジェクトには影響しない。
        """
        ...
    def save(self, path: str | os.PathLike) -> pathlib.Path:
        """データをJSONファイルへ書き出す。

        Args:
            path (str | os.PathLike): 書き出し先。

        Returns:
            pathlib.Path: 書き出したファイルの絶対パス。

        Raises:
            OSError: 書き出しに失敗した場合。
        """
        ...
    def validate(self, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ...) -> ValidationReport:
        """適用する前に、シーンとの対応を確かめる。シーンは変えない。

        Args:
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。
            replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え。
            namespaceMap (dict[str, str] | None): 名前空間の対応。

        Returns:
            ValidationReport: 見つからないもの・書けないもの・適用できない問題。
        """
        ...
    def _run_apply(self, mapping_args: dict, options: dict, fast: bool = ...) -> ValidationReport:
        """検査してから、1回のUndoで適用する(それぞれの種類の ``apply`` の中身)。

        errorsがあれば、何も変えずにValueErrorにする。通常の経路では、適用の途中で失敗したら元に戻す。
        最後に、missing・skippedをまとめて警告する。

        Args:
            mapping_args (dict): ``nameMap``・``replace``・``namespaceMap``。
            options (dict): 種類ごとに追加する指定。``_validate``・``_apply`` へ渡す。
            fast (bool): TrueはUndoなしのOpenMaya更新(対応する種類だけが渡す)。

        Returns:
            ValidationReport: 適用の結果。

        Raises:
            ValueError: 適用できない問題がある場合。
        """
        ...
    def _convert_time(self, frame: float, timing: str) -> float:
        """保存したときのフレームを、今のシーンのフレームへ換算する。

        Args:
            frame (float): 保存したときのフレーム。
            timing (str): ``"frame"`` か ``"second"``。

        Returns:
            float: 今のシーンのフレーム。取得したばかり(ヘッダーが無い)ならそのまま。
        """
        ...
    def _require_data(self, data: dict):
        """データの形を確かめる。それぞれの種類が上書きする。

        Args:
            data (dict): 持たせる前のデータ。

        Raises:
            ValueError: データの形が種類と合わない場合。
        """
        ...
    def _validate(self, mapping: NameMapping, report: ValidationReport, options: dict):
        """シーンとの対応を確かめ、reportへ記録する。それぞれの種類が書く。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 種類ごとに追加する指定。

        Raises:
            NotImplementedError: 基底クラスで呼んだ場合。
        """
        ...
    def _apply(self, mapping: NameMapping, report: ValidationReport, options: dict, fast: bool):
        """シーンへ書き戻し、書けなかったものをreportへ記録する。それぞれの種類が書く。

        Args:
            mapping (NameMapping): 名前の対応づけ。
            report (ValidationReport): 記録先。
            options (dict): 種類ごとに追加する指定。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Raises:
            NotImplementedError: 基底クラスで呼んだ場合。
        """
        ...

def _copy_data(value: object) -> Any:
    """辞書・listをたどってコピーする。数学型は、同じ型の新しい値にする。

    om2の値は ``copy.deepcopy`` でコピーできないので、自分でたどる。

    Args:
        value (object): コピーする値。

    Returns:
        object: コピー。文字列・数値・Noneはそのまま返す。
    """
    ...

def _summary(items: list[str], limit: int = ...) -> str:
    """長い一覧を先頭だけの文字列にする。

    Args:
        items (list[str]): 一覧。
        limit (int): 表示する件数。

    Returns:
        str: カンマで区切った文字列。表示する件数を超えた分は ``"..."`` にする。
    """
    ...
