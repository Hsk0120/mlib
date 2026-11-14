@echo off
setlocal

::----------------------------------------------------------------
:: mlibのSphinx文書(_docs\source)を、空にした _docs\_build\html へ作る。
:: 任意の工程。文書が要るときに、format_mlib.bat と test_mlib.bat の後で
:: 実行する(流れは CONTRIBUTING.md)。
::
::   build_mlib_docs.bat              ビルドして、最後にキー入力を待つ
::   build_mlib_docs.bat --no-pause   待たない(ターミナル・スクリプトから呼ぶとき)
::
:: 終了コード: ビルドに成功すれば 0。それ以外は 1、またはSphinxの終了コード。
::
:: 表示する文は messages.txt にあり、_message.bat が表示する。最後の文は [OK] か [NG] で始まる。
::
:: このファイルは Shift-JIS(CP932)・CRLF で保存する(.gitattributes を参照)。
::----------------------------------------------------------------
rem Sphinxは、setup.bat が作る1つの環境にruffと一緒に入っている。
set "MLIB_TOOLS_DIR=%~dp0"
set "SAY=call "%~dp0_message.bat""
set "MLIB_DOCS_PYTHON=%~dp0.venv\Scripts\python.exe"
set "MLIB_DOCS_SOURCE=%~dp0..\_docs\source"
set "MLIB_DOCS_MAYAPY_FILE=%~dp0.mayapy-site\mayapy-path.txt"
set "MLIB_DOCS_RESULT=1"
set "MLIB_DOCS_MESSAGE=docs.noEnvironment"
rem 最後に表示するパスを読みやすく・コピーしやすくするため、".." を解決しておく。
for %%P in ("%~dp0..\_docs\_build\html") do set "MLIB_DOCS_OUTPUT=%%~fP"

if exist "%MLIB_DOCS_PYTHON%" goto clean
rem Pythonが無くて setup.bat がmayapyを使った場合は、同じmayapyと、
rem .mayapy-site へ入れたパッケージでSphinxを動かす。
if exist "%MLIB_DOCS_MAYAPY_FILE%" set /p MLIB_DOCS_PYTHON=<"%MLIB_DOCS_MAYAPY_FILE%"
if not exist "%MLIB_DOCS_PYTHON%" goto finish
set "PYTHONNOUSERSITE=1"
set "PYTHONPATH=%~dp0.mayapy-site"

:clean
rem Sphinxは出力先にある古いファイルを消さない。元から消したファイル
rem (古い _static の素材など)が残らないよう、毎回、出力先を空にしてから作る。
set "MLIB_DOCS_MESSAGE=docs.cannotClean"
if exist "%MLIB_DOCS_OUTPUT%" rmdir /s /q "%MLIB_DOCS_OUTPUT%"
if exist "%MLIB_DOCS_OUTPUT%" goto finish

rem -P は、今いるフォルダーを sys.path へ入れない指定。mlibのフォルダーで実行すると、
rem mlibの json パッケージが、Sphinxの使う標準の json を隠してしまうため。
rem -n は、解決できない参照も報告する指定(許すものは conf.py の nitpick_ignore_regex)。
%SAY% docs.building
"%MLIB_DOCS_PYTHON%" -P -m sphinx -E -a -b html -n -W --keep-going "%MLIB_DOCS_SOURCE%" "%MLIB_DOCS_OUTPUT%"
set "MLIB_DOCS_RESULT=%ERRORLEVEL%"
set "MLIB_DOCS_MESSAGE=docs.ng"
if "%MLIB_DOCS_RESULT%"=="0" set "MLIB_DOCS_MESSAGE=docs.ok"

:finish
%SAY% blank line %MLIB_DOCS_MESSAGE% line
echo.
if /I not "%~1"=="--no-pause" pause
exit /b %MLIB_DOCS_RESULT%
