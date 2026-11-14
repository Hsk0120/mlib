@echo off
setlocal

::----------------------------------------------------------------
:: mlibの型スタブ(各 .py の隣の .pyi)を、docstringの型から作る。
:: VS Code(Pylance)の補完と引数の表示に使われる。.py は書き換えない。
:: 作り直した .pyi は、元の .py と一緒にコミットする。
::
::   generate_mlib_stubs.bat            スタブを作り直す
::   generate_mlib_stubs.bat --report   注釈にできなかった型も一覧表示する
::   generate_mlib_stubs.bat --check    スタブが最新かどうかだけを調べる
::   --no-pause                         最後にキー入力を待たない
::                                      (ターミナル・スクリプトから呼ぶとき)
::
:: Pythonランチャー(py)の Python 3.9〜3.14、または Maya 2027〜2023 のmayapyが必要。
:: どれで実行しても同じスタブができる。
::
:: 終了コード: generate_mlib_stubs.py の終了コード(成功、または --check で
:: 最新のとき 0)。Pythonが見つからなければ 2。
::
:: 表示する文は messages.txt にあり、_message.bat が表示する。最後の文は [OK] か [NG] で始まる。
::
:: このファイルは Shift-JIS(CP932)・CRLF で保存する(.gitattributes を参照)。
::----------------------------------------------------------------
rem 引数を読む前にパスを控える(SHIFT すると %0 も変わるため)。
SET "SCRIPT=%~dp0generate_mlib_stubs.py"
SET "SAY=CALL "%~dp0_message.bat""
SET "MLIB_STUBS_PY="
SET "MLIB_STUBS_MAYAPY="
SET "MLIB_STUBS_RESULT=2"
SET "MLIB_STUBS_PAUSE=1"
SET "MLIB_STUBS_ARGS="
rem 結果の文のキー。stubs か stubs.check に、.ok か .ng を付ける。
SET "MLIB_STUBS_KIND=stubs"
SET "MLIB_STUBS_MESSAGE=stubs.noPython"

rem 引数から --no-pause を取り出し、残りはスクリプトへ渡す。
:parse_args
IF "%~1"=="" GOTO :args_done
IF /I "%~1"=="--check" SET "MLIB_STUBS_KIND=stubs.check"
IF /I "%~1"=="--no-pause" (
    SET "MLIB_STUBS_PAUSE="
) ELSE (
    SET "MLIB_STUBS_ARGS=%MLIB_STUBS_ARGS% %1"
)
SHIFT
GOTO :parse_args
:args_done
rem 入っているPythonだけを探す(ランチャーに新しいPythonを入れさせない)。
SET "PYLAUNCHER_ALLOW_INSTALL="

rem Pythonランチャーへ、新しい版から順に問い合わせる。
rem "python" は使わない(Microsoft Storeを開くだけの代役が先に見つかることがある)。
rem "py -3" も使わない(入っている中で最新を選ぶため、対応していない 3.15 以降に
rem なることがある)。setup.bat はSphinxの都合で 3.11 からだが、スタブは 3.9 から作れる。
FOR %%V IN (3.14 3.13 3.12 3.11 3.10 3.9) DO (
    IF NOT DEFINED MLIB_STUBS_PY (
        py -%%V -c "import sys" >NUL 2>&1
        IF NOT ERRORLEVEL 1 SET "MLIB_STUBS_PY=%%V"
    )
)
IF NOT DEFINED MLIB_STUBS_PY GOTO :find_mayapy
py -%MLIB_STUBS_PY% "%SCRIPT%"%MLIB_STUBS_ARGS%
GOTO :done

:find_mayapy
rem 代わりに Maya 2027〜2023 のmayapy(Python 3.9 以上)を使う。
FOR %%V IN (2027 2026 2025 2024 2023) DO (
    IF NOT DEFINED MLIB_STUBS_MAYAPY IF EXIST "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" SET "MLIB_STUBS_MAYAPY=C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe"
)
IF NOT DEFINED MLIB_STUBS_MAYAPY GOTO :finish
%SAY% stubs.usingMayapy
"%MLIB_STUBS_MAYAPY%" "%SCRIPT%"%MLIB_STUBS_ARGS%

:done
SET "MLIB_STUBS_RESULT=%ERRORLEVEL%"
SET "MLIB_STUBS_MESSAGE=%MLIB_STUBS_KIND%.ng"
IF "%MLIB_STUBS_RESULT%"=="0" SET "MLIB_STUBS_MESSAGE=%MLIB_STUBS_KIND%.ok"

:finish
%SAY% blank line %MLIB_STUBS_MESSAGE% line

rem ダブルクリックで実行したときも結果を読めるよう、キー入力を待つ。
IF DEFINED MLIB_STUBS_PAUSE (
    ECHO.
    PAUSE
)
EXIT /b %MLIB_STUBS_RESULT%
