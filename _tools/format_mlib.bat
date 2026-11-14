@echo off
setlocal

::----------------------------------------------------------------
:: mlibのコードをruffで整形し、ruffでは直せない点を検査する。
:: 設定は mlib\ruff.toml にあるので、誰が実行しても同じ結果になる。Mayaは不要。
::
::   format_mlib.bat             整形して直せるものを直し、残った指摘を表示する
::   format_mlib.bat --check     何も書き換えず、整形されていない所と指摘だけを
::                               表示する(コミット前の確認用)
::   --no-pause                  最後にキー入力を待たない
::                               (ターミナル・スクリプトから呼ぶとき)
::
:: 次の順に実行する。
::   ruff format                 コードの見た目(空白・空行・改行位置・引用符)
::   ruff check --fix            importの並びと分類、使っていない名前、pathlib、
::                               文字コード指定など、ruff.toml で選んだルール
::   check_mlib_layout.py        ruffに無い検査。定数・__all__・TYPE_CHECKING の位置、
::                               クラス内メンバーの順、公開入口の入力assert など
::   check_mlib_exports.py       公開名と、明示した公開(__all__ など)の一致
::
:: これはコードそのもののためのバッチ。テストは test_mlib.bat が受け持ち、
:: 型スタブ(generate_mlib_stubs.bat)と文書(build_mlib_docs.bat)は別の任意の工程。
::
:: ruffが必要。setup.bat を1回実行すると、版を固定したruffが _tools\.venv
:: (Pythonが無いときは _tools\.mayapy-site)に入る。PATH上のruffや、
:: Pythonランチャー(py)のPythonに入っているruffも使える。
::
:: 終了コード: 全部通れば 0、指摘が残れば 1、ruff か Python が見つからなければ 2。
::
:: 表示する文は messages.txt にあり、_message.bat が表示する。最後のまとめは
:: 手順ごとに [OK]・[NG]・[--](実行していない)を並べ、最後の行が [OK] か [NG] になる。
::
:: このファイルは Shift-JIS(CP932)・CRLF で保存する(.gitattributes を参照)。
::----------------------------------------------------------------
rem 引数を読む前にフォルダーを控える(SHIFT すると %0 も変わるため)。
SET "MLIB_TOOLS_DIR=%~dp0"
SET "SAY=CALL "%~dp0_message.bat""
SET "PACKAGE=%~dp0.."
SET "LAYOUT=%~dp0check_mlib_layout.py"
SET "EXPORTS=%~dp0check_mlib_exports.py"
SET "MLIB_FORMAT_ENV_RUFF=%~dp0.venv\Scripts\ruff.exe"
SET "MLIB_FORMAT_ENV_PYTHON=%~dp0.venv\Scripts\python.exe"
SET "MLIB_FORMAT_SITE_RUFF=%~dp0.mayapy-site\bin\ruff.exe"
SET "MLIB_FORMAT_MAYAPY_FILE=%~dp0.mayapy-site\mayapy-path.txt"
SET "MLIB_FORMAT_PY="
SET "MLIB_FORMAT_RUFF="
SET "MLIB_FORMAT_PYTHON="
SET "MLIB_FORMAT_RESULT=2"
SET "MLIB_FORMAT_PAUSE=1"
SET "MLIB_FORMAT_CHECK="
rem まとめに出す各手順の結果。OK・NG・--(実行していない)のどれか。
SET "MLIB_FORMAT_STEP_FORMAT=--"
SET "MLIB_FORMAT_STEP_CHECK=--"
SET "MLIB_FORMAT_STEP_LAYOUT=--"
SET "MLIB_FORMAT_STEP_EXPORTS=--"

rem 引数から --no-pause と --check を取り出す。
:parse_args
IF "%~1"=="" GOTO :args_done
IF /I "%~1"=="--no-pause" SET "MLIB_FORMAT_PAUSE=" & GOTO :next_arg
IF /I "%~1"=="--check" SET "MLIB_FORMAT_CHECK=1" & GOTO :next_arg
SET "MLIB_MESSAGE_VALUE=%~1"
%SAY% format.badArgument
GOTO :summary
:next_arg
SHIFT
GOTO :parse_args
:args_done
rem 入っているPythonだけを探す(ランチャーに新しいPythonを入れさせない)。
SET "PYLAUNCHER_ALLOW_INSTALL="

rem 全員が同じ版を使えるよう、setup.bat が入れたものを優先する。
rem .venv → .mayapy-site → PATH上のruff → ランチャーのPython の順に探す。
rem Pythonが要る検査も同じ環境を使う。
rem 版の文字列は括弧の外で組み立てる(括弧の中では、同じブロックで
rem SET した変数の値がまだ使えないため)。
IF EXIST "%MLIB_FORMAT_ENV_RUFF%" SET "MLIB_FORMAT_RUFF="%MLIB_FORMAT_ENV_RUFF%""
IF EXIST "%MLIB_FORMAT_ENV_PYTHON%" SET "MLIB_FORMAT_PYTHON="%MLIB_FORMAT_ENV_PYTHON%""
IF NOT DEFINED MLIB_FORMAT_RUFF IF EXIST "%MLIB_FORMAT_SITE_RUFF%" SET "MLIB_FORMAT_RUFF="%MLIB_FORMAT_SITE_RUFF%""
IF NOT DEFINED MLIB_FORMAT_PYTHON IF EXIST "%MLIB_FORMAT_MAYAPY_FILE%" SET /p MLIB_FORMAT_PYTHON=<"%MLIB_FORMAT_MAYAPY_FILE%"
IF NOT DEFINED MLIB_FORMAT_RUFF (
    ruff --version >NUL 2>&1
    IF NOT ERRORLEVEL 1 SET "MLIB_FORMAT_RUFF=ruff"
)
IF NOT DEFINED MLIB_FORMAT_RUFF (
    FOR %%V IN (3.14 3.13 3.12 3.11 3.10 3.9) DO (
        IF NOT DEFINED MLIB_FORMAT_PY (
            py -%%V -c "import ruff" >NUL 2>&1
            IF NOT ERRORLEVEL 1 SET "MLIB_FORMAT_PY=%%V"
        )
    )
)
IF NOT DEFINED MLIB_FORMAT_RUFF IF DEFINED MLIB_FORMAT_PY SET "MLIB_FORMAT_RUFF=py -%MLIB_FORMAT_PY% -m ruff"
IF DEFINED MLIB_FORMAT_RUFF GOTO :ruff_found
%SAY% format.noRuff
GOTO :summary

:ruff_found
%MLIB_FORMAT_RUFF% --version

rem ここから先はツールが見つかっているので、0以外の結果は実際の指摘を表す。
rem 各手順の結果は、次の行の "IF ERRORLEVEL 1" で拾う(括弧のブロックの中では
rem %ERRORLEVEL% がコマンドの実行前に展開され、結果を取りこぼすため)。
SET "MLIB_FORMAT_RESULT=0"
IF DEFINED MLIB_FORMAT_CHECK GOTO :check_only

%SAY% format.step1.fix
SET "MLIB_FORMAT_STEP_FORMAT=OK"
%MLIB_FORMAT_RUFF% format "%PACKAGE%"
IF ERRORLEVEL 1 SET "MLIB_FORMAT_STEP_FORMAT=NG"
%SAY% format.step2.fix
SET "MLIB_FORMAT_STEP_CHECK=OK"
%MLIB_FORMAT_RUFF% check --fix "%PACKAGE%"
IF ERRORLEVEL 1 SET "MLIB_FORMAT_STEP_CHECK=NG"
GOTO :layout

:check_only
%SAY% format.step1.check
SET "MLIB_FORMAT_STEP_FORMAT=OK"
%MLIB_FORMAT_RUFF% format --check "%PACKAGE%"
IF ERRORLEVEL 1 SET "MLIB_FORMAT_STEP_FORMAT=NG"
%SAY% format.step2.check
SET "MLIB_FORMAT_STEP_CHECK=OK"
%MLIB_FORMAT_RUFF% check "%PACKAGE%"
IF ERRORLEVEL 1 SET "MLIB_FORMAT_STEP_CHECK=NG"

:layout
rem ruffに無い検査。Pythonが要るのはここだけ。
IF NOT DEFINED MLIB_FORMAT_PYTHON IF DEFINED MLIB_FORMAT_PY SET "MLIB_FORMAT_PYTHON=py -%MLIB_FORMAT_PY%"
IF NOT DEFINED MLIB_FORMAT_PYTHON SET "MLIB_FORMAT_PYTHON=py -3"
%SAY% format.step3
SET "MLIB_FORMAT_STEP_LAYOUT=OK"
%MLIB_FORMAT_PYTHON% "%LAYOUT%" --check
IF ERRORLEVEL 1 SET "MLIB_FORMAT_STEP_LAYOUT=NG"
%SAY% format.step4
SET "MLIB_FORMAT_STEP_EXPORTS=OK"
%MLIB_FORMAT_PYTHON% "%EXPORTS%"
IF ERRORLEVEL 1 SET "MLIB_FORMAT_STEP_EXPORTS=NG"

IF "%MLIB_FORMAT_STEP_FORMAT%"=="NG" SET "MLIB_FORMAT_RESULT=1"
IF "%MLIB_FORMAT_STEP_CHECK%"=="NG" SET "MLIB_FORMAT_RESULT=1"
IF "%MLIB_FORMAT_STEP_LAYOUT%"=="NG" SET "MLIB_FORMAT_RESULT=1"
IF "%MLIB_FORMAT_STEP_EXPORTS%"=="NG" SET "MLIB_FORMAT_RESULT=1"

:summary
SET "MLIB_FORMAT_MESSAGE=format.ng"
IF "%MLIB_FORMAT_RESULT%"=="0" SET "MLIB_FORMAT_MESSAGE=format.ok"
IF "%MLIB_FORMAT_RESULT%"=="2" SET "MLIB_FORMAT_MESSAGE=format.notRun"
%SAY% blank line format.steps rule %MLIB_FORMAT_MESSAGE% legend line

rem ダブルクリックで実行したときも結果を読めるよう、キー入力を待つ。
IF DEFINED MLIB_FORMAT_PAUSE (
    ECHO.
    PAUSE
)
EXIT /b %MLIB_FORMAT_RESULT%
