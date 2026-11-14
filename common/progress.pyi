# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ループで処理した件数を表示する。Maya GUIではメインのプログレスバー、それ以外ではテキスト1行に表示する。

- Maya GUIでは、もとからある ``$gMainProgressBar`` (ステータスラインの下のバー)を使い、独自のUIは作らない。
- バッチ・mayapyの場合と、出力先を指定した場合は、その出力先へテキストで表示する。
- どちらの場合も、notifyのコールバックを渡せば、表示した文字列を同じように渡す。

要素の取り出しと表示は、progressBar()が返すイテレーターをループで回したときに行う。
Mayaのモジュールは、表示先を決めるときに読み込む。
"""

import sys
from typing import Any, Callable, Iterable, Iterator, TextIO

_DONE_CELL: str
_TODO_CELL: str
_FRAME: str
_UNKNOWN_TOTAL: str

def _proportion(done: int, total: int, scale: int) -> int:
    """処理済みの件数を、0 から scale までの整数に換算する。

    浮動小数点の丸め誤差で値が1つ小さくなるのを避けるため、整数の計算で切り捨てる。
    全体が0件の場合と、処理済みの件数が全体に達したか超えた場合は、scale にする。

    Args:
        done (int): 処理済みの件数。
        total (int): 全体の件数。
        scale (int): 換算後の最大値。

    Returns:
        int: 0 以上 scale 以下の整数。
    """
    ...


class _ProgressLine:
    """1行の進み具合の表示を受け持つ。件数を持ち、文字列を組み立てて出力する。

    処理済みの件数は ``done`` に持ち、``advance`` のたびに1つ増やす。
    見出しは、作るときに末尾の空白を取り除いて持つ。空なら表示しない。

    Args:
        label (str): 行頭の見出し。
        total (int | None): 全体の件数。不明なら None。
        width (int): バー部分の文字数。
        stream (TextIO): ``write`` を備える出力先。
        notify (Callable[[str], object] | None): 描画した文字列の通知先。
    """
    def __init__(self, label: str, total: int | None, width: int, stream: object, notify: Callable[..., Any] | None) -> None:
        """進み具合の値を初期化する。ここでは出力しない。

        Args:
            label (str): 表示名。末尾の空白を取り除いて持つ。
            total (int | None): 全体の処理数。不明な場合は None。
            width (int): バーの表示幅。
            stream (object): 書き込み先。
            notify (callable | None): 描画した文字列を渡す通知先。
        """
        ...
    def render(self) -> str:
        """今の件数に合った表示の文字列を組み立てる。

        Returns:
            str: 全体の件数が分かっていればバー・百分率・件数、分からなければ件数だけを並べた文字列。
                行頭復帰や改行は含まない。
        """
        ...
    def draw(self) -> str:
        """行の先頭へ戻って今の表示で上書きし、通知先があれば同じ文字列を渡す。

        Returns:
            str: 出力した表示文字列。
        """
        ...
    def advance(self) -> None:
        """処理済みの件数を1つ進めて、表示し直す。

        Returns:
            None: 値を返さない。
        """
        ...
    def finish(self, quiet: bool = ...) -> None:
        """改行を出力して行を閉じる。

        Args:
            quiet (bool): True なら、改行の書き込みや ``flush`` で起きた
                ``Exception`` を送出せずに捨てる。別の例外が伝わっている
                途中で行を閉じるときに使い、元の例外が後から起きた出力先の
                失敗で置き換わらないようにする。

        Returns:
            None: 値を返さない。
        """
        ...
    def _flush(self) -> None:
        """出力先が ``flush`` を持つ場合だけ呼び出す。

        Returns:
            None: 値を返さない。
        """
        ...
    label: Any
    total: Any
    width: Any
    stream: Any
    notify: Any
    done: Any


class ProgressCancelled(KeyboardInterrupt):
    """Maya GUIのプログレスバーで、Escキーでループが中止されたことを表す。

    ``KeyboardInterrupt`` の派生なので、``except Exception`` では捕まらずに処理を止める。
    中止を個別に扱う場合は ``except ProgressCancelled`` で捕まえる。
    """


class _MainProgressBar(_ProgressLine):
    """Maya GUIのメインのプログレスバーに、件数を表示する。

    最初の表示で ``beginProgress`` (Escで中止できる)を行う。処理が1件進むたびに、値とステータスの
    文字列を更新し、終わったら ``endProgress`` で閉じる。テキストは書き込まない。
    notifyには、テキストで表示する場合と同じ文字列を渡す。

    Args:
        label (str): ステータスの見出し。
        total (int | None): 全体の件数。不明なら None。
        width (int): notifyへ渡す文字列のバー部分の文字数。
        bar (str): ``$gMainProgressBar`` のコントロール名。
        notify (Callable[[str], object] | None): 描画した文字列の通知先。
    """
    def __init__(self, label: str, total: int | None, width: int, bar: str, notify: Callable[..., Any] | None) -> None:
        """進み具合の値を初期化する。ここではバーを表示しない。

        Args:
            label (str): 表示名。末尾の空白を取り除いて持つ。
            total (int | None): 全体の処理数。不明な場合は None。
            width (int): notifyへ渡す文字列の、バーの表示幅。
            bar (str): メインのプログレスバーのコントロール名。
            notify (callable | None): 描画した文字列を渡す通知先。
        """
        ...
    def status(self) -> str:
        """プログレスバーのステータス欄に表示する文字列を組み立てる。

        Returns:
            str: ``見出し 処理済み/全体`` (全体が不明なら ``?``)。
        """
        ...
    def draw(self) -> str:
        """バーの値とステータスを更新し、通知先があれば、テキストで表示する場合と同じ文字列を渡す。

        Returns:
            str: notifyへ渡した表示文字列。

        Raises:
            ProgressCancelled: Escキーで中止された場合。
        """
        ...
    def finish(self, quiet: bool = ...) -> None:
        """``endProgress`` でバーを閉じる。

        Args:
            quiet (bool): True なら、閉じる処理で起きた ``Exception`` を送出せずに捨てる。

        Returns:
            None: 値を返さない。
        """
        ...
    bar: Any
    begun: Any
_active_bars: set

def _main_progress_bar() -> str | None:
    """Maya GUIで使える、メインのプログレスバーのコントロール名を返す。

    Returns:
        str | None: ``$gMainProgressBar`` の名前。Mayaの外・バッチ・mayapy・バーが無い場合は None。
    """
    ...

def _track(iterable: Iterable, line: _ProgressLine) -> Iterator[object]:
    """要素を順に返しながら、line の件数を更新して表示するジェネレーター。

    - 最初の要素を取り出せたところで、0件の行を表示する。
    - 使う側が次の要素を求めるたびに(つまり直前の要素の処理が終わるたびに)、1件進める。
    - 途中で ``break`` した場合や、例外でジェネレーターが閉じられた場合も、表示を始めていれば
      改行して行を閉じる。表示そのもの(出力や ``notify``)が例外を出した場合も同じで、
      書きかけの行を改行で閉じてから例外を伝える。
    - 要素が1つも無ければ、何も出力しない。

    例外が伝わっている途中で行を閉じる場合、改行の書き込みに失敗しても、その失敗は捨てて
    先に起きた例外をそのまま伝える(閉じられた出力先へもう一度書こうとして、別の例外に置き換わるのを防ぐ)。
    最後までループできた場合の改行の失敗は、そのまま呼び出す側へ伝える。

    Args:
        iterable (Iterable): ループで回す対象。
        line (_ProgressLine): 表示を受け持つ行。

    Yields:
        object: iterable の要素をそのまま返す。
    """
    ...

def progressBar(iterable: Iterable, *, label: str = ..., total: int | None = ..., width: int = ..., stream: TextIO | None = ..., notify: Callable[[str], object] | None = ..., gui: bool | None = ...) -> Iterator:
    """要素を同じ順に返しながら、処理した件数をMayaのプログレスバーかテキスト1行に表示する。

    Maya GUIで ``stream`` を省略した場合は、メインのプログレスバー(``$gMainProgressBar``)に件数と
    見出しを表示する。Script Editorには書き込まない。

    - Escキーで中止できる。中止すると、次の要素を返す前に :class:`ProgressCancelled`
      (``KeyboardInterrupt`` の派生)を送出し、バーを閉じる。それまでに行った変更は戻さない。
    - 次の場合は、これまでどおりテキスト1行に表示する: バッチ・mayapy・Mayaの外、``stream`` を指定したとき、
      または別の progressBar() がバーを使っている(入れ子のループの)とき。

    引数の確認とlen()は、呼び出したときに行う。要素の取り出しと表示は、ループで回したときに行う。

    - 最初の要素を取り出すと0件を表示し、次の要素を求めるたびに1件進む。
    - 最後まで回ると改行する。途中で終えた場合は、返したジェネレーターがclose()されたとき
      (またはガベージコレクションで回収されたとき)に行を閉じる。
    - 入力が空なら、出力もnotifyも行わない。
    - 入力のループ・出力・通知で起きた例外は、そのまま外へ伝える。例外が伝わっている途中やclose()のときは、
      改行で起きた通常の例外だけを捨てる。正常に終わったときは捨てない。

    Args:
        iterable (Iterable): ループで回す対象。要素はそのまま返す。
        label (str): 行の先頭の見出し。末尾の空白は取り除き、空なら表示しない。
        total (int | None): 全体の件数。0以上。Noneならlen()を試し、TypeErrorなら件数だけを表示する。
            実際の件数がtotalを超えた場合、バーと百分率は満杯のまま、件数だけを増やす。
        width (int): バーの幅。1以上。
        stream (TextIO | None): 出力先。writeを持つもの(flushは任意)。Noneなら、呼び出したときのsys.stdout。
            行頭復帰を解釈しない出力先では、表示が上書きされないことがある。
        notify (Callable[[str], object] | None): 表示するたびに、その文字列をその場で受け取る。
            改行と行頭復帰は含まない。戻り値は使わない。通知を間引くなら、呼び出す側で行う。
            プログレスバーに表示するときも、同じ文字列を渡す。
        gui (bool | None): 表示先。Noneなら自動(Maya GUIで、streamを省略したときはプログレスバー)。
            Trueならプログレスバーを使い、使えなければRuntimeError。Falseなら常にテキスト。
            表示先は呼び出したときに決める。

    Returns:
        Iterator: 元の要素を、元の順に返すジェネレーター。

    Raises:
        TypeError: labelの型が正しくない場合、またはwidth・totalが整数でない場合。boolは整数として受け付けない。
        ValueError: widthが1より小さい場合、またはtotalが負の場合。
        RuntimeError: gui=Trueで、メインのプログレスバーが使えない場合(バッチ・ほかで使用中など)。
        ProgressCancelled: ループの途中で、プログレスバーがEscキーで中止された場合。

    Examples:
        >>> import io
        >>> buffer = io.StringIO()
        >>> list(progressBar("ab", label="demo", width=4, stream=buffer))
        ['a', 'b']
        >>> buffer.getvalue().split("\\r")[-1]
        'demo |====| 100% 2/2\\n'
    """
    ...
