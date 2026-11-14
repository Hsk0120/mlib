@echo off
setlocal

::----------------------------------------------------------------
:: mlibを書くときに使うツールを1つの環境へ入れる。全員が同じ版で整形し、
:: 同じ版で文書を作れるようにするため。mlib本体はこれらを必要としない。
:: Mayaへは何も入れず、PCの設定も変えない。
::
::   setup.bat              環境を作ってツールを入れる
::   setup.bat --no-pause   最後にキー入力を待たない
::
:: Pythonランチャー(py)のPythonを新しい版から探し、このフォルダーに ".venv" を
:: 作って、次の2つのファイルに書かれたものを入れる。
::   _tools\requirements-dev.txt   ruff(整形と検査)
::   _docs\requirements.txt        Sphinx(文書)
:: Pythonが入っていないときは Maya 2027〜2025 のmayapyを使い、代わりに
:: ".mayapy-site" へ入れる(mayapyではvenvを作れないため)。
:: すでにある .venv・.mayapy-site は再利用し、壊れたものは書き換えずに残す。
::
:: Sphinx 8.2 の都合で Python 3.11 以上が必要。ruffだけなら 3.9 でも動くが、
:: 環境を1つにして、セットアップをこのバッチ1本にしている。
::
:: セットアップのバッチはこれだけ。format_mlib.bat・test_mlib.bat・
:: build_mlib_docs.bat は、どれもここで入れたものを使う。
:: 文書のブラウザ確認には _docs\browser-requirements.txt も要る。
:: 実行するときだけ入れる(_docs\README.md を参照)。
::
:: 終了コード: ツールが使える状態になれば 0、それ以外は 1。
::
:: 表示する文は messages.txt にあり、_message.bat が表示する。最後の文は [OK] か [NG] で始まる。
::
:: このファイルは Shift-JIS(CP932)・CRLF で保存する(.gitattributes を参照)。
::----------------------------------------------------------------
SET "SAY=CALL "%~dp0_message.bat""
SET "MLIB_TOOLS_ENV=%~dp0.venv"
SET "MLIB_TOOLS_PYTHON=%~dp0.venv\Scripts\python.exe"
SET "MLIB_TOOLS_RUFF=%~dp0.venv\Scripts\ruff.exe"
SET "MLIB_TOOLS_SITE=%~dp0.mayapy-site"
SET "MLIB_TOOLS_MAYAPY_FILE=%~dp0.mayapy-site\mayapy-path.txt"
SET "MLIB_TOOLS_DEV=%~dp0requirements-dev.txt"
SET "MLIB_TOOLS_DOCS=%~dp0..\_docs\requirements.txt"
SET "MLIB_TOOLS_RESULT=1"
SET "MLIB_TOOLS_MESSAGE=setup.verifyFailed"

rem すでにある環境は再利用する。壊れていても自動では作り直さない。
IF EXIST "%MLIB_TOOLS_ENV%" GOTO :existing_environment
IF EXIST "%MLIB_TOOLS_SITE%" GOTO :existing_mayapy

rem Pythonランチャーへ、新しい版から順に問い合わせる。
rem "python" は使わない(Microsoft Storeを開くだけの代役が先に見つかることがある)。
rem "py -3" も使わない(入っている中で最新を選ぶため、対応していない 3.15 以降に
rem なることがある)。範囲は generate_mlib_stubs.bat から、Sphinx 8.2 が
rem 対応しない版を除いたもの。
rem 入っているPythonだけを探す(ランチャーに新しいPythonを入れさせない)。
SET "PYLAUNCHER_ALLOW_INSTALL="
SET "MLIB_TOOLS_PY="
FOR %%V IN (3.14 3.13 3.12 3.11) DO (
    IF NOT DEFINED MLIB_TOOLS_PY (
        py -%%V -c "import sys" >NUL 2>&1
        IF NOT ERRORLEVEL 1 SET "MLIB_TOOLS_PY=%%V"
    )
)
IF NOT DEFINED MLIB_TOOLS_PY GOTO :find_mayapy
%SAY% setup.usingPython
py -%MLIB_TOOLS_PY% -m venv "%MLIB_TOOLS_ENV%"
IF NOT ERRORLEVEL 1 GOTO :install
SET "MLIB_TOOLS_MESSAGE=setup.createFailed"
GOTO :finish

:find_mayapy
rem 代わりに Maya 2027〜2025 のmayapy(Python 3.11 以上)を使う。
rem mayapyではvenvを作れない(venvが mayapy.exe の隣の python.exe を探すため)ので、
rem pip install --target で .mayapy-site へ入れる。
SET "MLIB_TOOLS_MAYAPY="
FOR %%V IN (2027 2026 2025) DO (
    IF NOT DEFINED MLIB_TOOLS_MAYAPY IF EXIST "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" SET "MLIB_TOOLS_MAYAPY=C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe"
)
IF DEFINED MLIB_TOOLS_MAYAPY GOTO :install_mayapy
SET "MLIB_TOOLS_MESSAGE=setup.noPython"
GOTO :finish

:existing_environment
IF EXIST "%MLIB_TOOLS_PYTHON%" GOTO :install
SET "MLIB_TOOLS_MESSAGE=setup.brokenVenv"
GOTO :finish

:existing_mayapy
IF NOT EXIST "%MLIB_TOOLS_MAYAPY_FILE%" GOTO :broken_mayapy
SET /p MLIB_TOOLS_MAYAPY=<"%MLIB_TOOLS_MAYAPY_FILE%"
IF NOT EXIST "%MLIB_TOOLS_MAYAPY%" GOTO :broken_mayapy
GOTO :install_mayapy

:broken_mayapy
SET "MLIB_TOOLS_MESSAGE=setup.brokenMayapy"
GOTO :finish

:install
%SAY% setup.installing
"%MLIB_TOOLS_PYTHON%" -m pip install --disable-pip-version-check -r "%MLIB_TOOLS_DEV%" -r "%MLIB_TOOLS_DOCS%"
IF NOT ERRORLEVEL 1 GOTO :verify
SET "MLIB_TOOLS_MESSAGE=setup.installFailed"
GOTO :finish

:install_mayapy
%SAY% setup.usingMayapy setup.installing
rem mayapyのユーザー領域にあるパッケージを、この環境へ混ぜない。
SET "PYTHONNOUSERSITE=1"
"%MLIB_TOOLS_MAYAPY%" -m pip install --disable-pip-version-check --upgrade --target "%MLIB_TOOLS_SITE%" -r "%MLIB_TOOLS_DEV%" -r "%MLIB_TOOLS_DOCS%"
IF NOT ERRORLEVEL 1 GOTO :installed_mayapy
SET "MLIB_TOOLS_MESSAGE=setup.installFailed"
GOTO :finish

:installed_mayapy
rem format_mlib.bat と build_mlib_docs.bat が同じmayapyを使えるよう、場所を書き残す。
>"%MLIB_TOOLS_MAYAPY_FILE%" ECHO %MLIB_TOOLS_MAYAPY%
SET "MLIB_TOOLS_RUFF=%MLIB_TOOLS_SITE%\bin\ruff.exe"
SET "MLIB_TOOLS_PYTHON=%MLIB_TOOLS_MAYAPY%"

:verify
rem MLIB_TOOLS_MESSAGE はここまで setup.verifyFailed のまま。
rem 次のどれかが動かなければ、その文を表示する。
IF NOT EXIST "%MLIB_TOOLS_RUFF%" GOTO :finish
"%MLIB_TOOLS_RUFF%" --version
IF ERRORLEVEL 1 GOTO :finish
"%MLIB_TOOLS_PYTHON%" -c "import sys, sphinx; print(sys.version); print('sphinx', sphinx.__version__)"
IF ERRORLEVEL 1 GOTO :finish

SET "MLIB_TOOLS_RESULT=0"
SET "MLIB_TOOLS_MESSAGE=setup.ok"

:finish
%SAY% blank line %MLIB_TOOLS_MESSAGE% line
ECHO.
IF /I NOT "%~1"=="--no-pause" PAUSE
EXIT /b %MLIB_TOOLS_RESULT%
