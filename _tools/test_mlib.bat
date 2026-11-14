@echo off
setlocal

::----------------------------------------------------------------
:: mlibのテストを全部実行する。先にMayaが要らないテスト(noMaya/)、
:: 通ったらmayapyで動くテスト(inMaya/)を実行する。
::
::   test_mlib.bat                          noMaya/ → Maya 2025 の inMaya/
::                                          (1回が重くならないよう既定は1版だけ)
::   test_mlib.bat --versions 2027          noMaya/ → Maya 2027 の inMaya/
::   test_mlib.bat --versions 2022 2027     同じテストを複数の版で実行する
::   test_mlib.bat --suite unit             inMaya/unit/ だけ(integration・all も可)
::   test_mlib.bat --tests test_joint.py    指定したファイルだけ
::   test_mlib.bat --no-maya                noMaya/ だけ
::   test_mlib.bat --no-pause               最後にキー入力を待たない
::                                          (ターミナル・スクリプトから呼ぶとき)
::
:: --no-maya と --no-pause 以外の引数は、そのまま __tests__\runMaya.py へ渡す。
:: コードの整形と検査は format_mlib.bat が受け持つ(流れは CONTRIBUTING.md)。
::
:: 終了コード: 全部成功で 0。失敗したときは最初に失敗した手順の終了コード。
:: Python か mayapy が見つからないときは 2。
::
:: 表示する文は messages.txt にあり、_message.bat が表示する。最後のまとめは
:: 手順ごとに [OK]・[NG]・[--](実行していない)を並べ、最後の行が [OK] か [NG] になる。
::
:: このファイルは Shift-JIS(CP932)・CRLF で保存する(.gitattributes を参照)。
::----------------------------------------------------------------
rem 引数を読む前にパスを控える(SHIFT すると %0 も変わるため)。
SET "TOOLS=%~dp0"
SET "TESTS=%~dp0..\__tests__\"
SET "SAY=CALL "%~dp0_message.bat""
SET "MLIB_TEST_ARGS="
SET "MLIB_TEST_MAYA=1"
SET "MLIB_TEST_PAUSE=1"
SET "MLIB_TEST_RESULT=0"
SET "MLIB_TEST_MESSAGE=test.ok"
rem まとめに出す各手順の結果。OK・NG・--(実行していない)のどれか。
SET "MLIB_TEST_STEP_NOMAYA=--"
SET "MLIB_TEST_STEP_MAYA=--"

:parse_args
IF "%~1"=="" GOTO :args_done
IF /I "%~1"=="--no-maya" SET "MLIB_TEST_MAYA=" & SHIFT & GOTO :parse_args
IF /I "%~1"=="--no-pause" SET "MLIB_TEST_PAUSE=" & SHIFT & GOTO :parse_args
SET "MLIB_TEST_ARGS=%MLIB_TEST_ARGS% %1"
SHIFT
GOTO :parse_args
:args_done
rem 入っているPythonだけを探す(ランチャーに新しいPythonを入れさせない)。
SET "PYLAUNCHER_ALLOW_INSTALL="

rem noMaya/ のテストは通常のPython 3.8以上で動く。setup.bat が作った環境を
rem 優先し、1回のセットアップで全部がそろうようにする。
SET "MLIB_TEST_NOMAYA_PYTHON=%TOOLS%.venv\Scripts\python.exe"
IF NOT EXIST "%MLIB_TEST_NOMAYA_PYTHON%" SET "MLIB_TEST_NOMAYA_PYTHON=py -3"

%SAY% test.step1
%MLIB_TEST_NOMAYA_PYTHON% "%TESTS%runNoMaya.py"
IF NOT ERRORLEVEL 1 GOTO :maya
SET "MLIB_TEST_STEP_NOMAYA=NG"
SET "MLIB_TEST_RESULT=1"
SET "MLIB_TEST_MESSAGE=test.ng.noMaya"
GOTO :summary

:maya
SET "MLIB_TEST_STEP_NOMAYA=OK"
IF DEFINED MLIB_TEST_MAYA GOTO :find_mayapy
%SAY% test.skipMaya
GOTO :summary

:find_mayapy
rem runMaya.py を動かす制御用のPythonとして、入っている中で一番新しいmayapyを使う
rem (テスト自体は、runMaya.py が --versions の各版のmayapyを起動して実行する)。
IF DEFINED MLIB_TEST_PYTHON GOTO :run
FOR %%V IN (2022 2023 2024 2025 2026 2027) DO (
    IF EXIST "%ProgramFiles%\Autodesk\Maya%%V\bin\mayapy.exe" SET "MLIB_TEST_PYTHON=%ProgramFiles%\Autodesk\Maya%%V\bin\mayapy.exe"
)
IF DEFINED MLIB_TEST_PYTHON GOTO :run
%SAY% blank test.noMayapy
SET "MLIB_TEST_RESULT=2"
SET "MLIB_TEST_MESSAGE=test.notRun"
GOTO :summary

:run
%SAY% test.step2
"%MLIB_TEST_PYTHON%" "%TESTS%runMaya.py"%MLIB_TEST_ARGS%
SET "MLIB_TEST_RESULT=%ERRORLEVEL%"
SET "MLIB_TEST_STEP_MAYA=OK"
IF "%MLIB_TEST_RESULT%"=="0" GOTO :summary
SET "MLIB_TEST_STEP_MAYA=NG"
SET "MLIB_TEST_MESSAGE=test.ng.maya"

:summary
%SAY% blank line test.steps rule %MLIB_TEST_MESSAGE% legend line

rem ダブルクリックで実行したときも結果を読めるよう、キー入力を待つ。
IF DEFINED MLIB_TEST_PAUSE (
    ECHO.
    PAUSE
)
EXIT /b %MLIB_TEST_RESULT%
