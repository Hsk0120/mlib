@echo off
setlocal

::----------------------------------------------------------------
:: Put the tools used while writing mlib into one environment, so that everyone
:: formats the code and builds the documentation with the same versions. mlib
:: itself does not need them, and nothing is installed into Maya or changed on
:: the system.
::
::   setup.bat              create the environment and install the tools
::   setup.bat --no-pause   do not wait for a key at the end
::
:: It creates ".venv" in this folder with the Python of the Windows Python
:: launcher (py), newest version first, and installs both requirement files
:: in it:
::   _tools\requirements-dev.txt   ruff (the formatter and the linter)
::   _docs\requirements.txt        Sphinx (the documentation)
:: When no Python is installed, it uses mayapy of Maya 2027-2025 and installs
:: into ".mayapy-site" instead (mayapy cannot create a venv).
:: An existing .venv or .mayapy-site is reused and a broken one is left alone.
::
:: Python 3.11 or newer is required, because Sphinx 8.2 needs it. ruff alone
:: would run on 3.9, but one environment keeps the setup to a single batch.
::
:: This is the only setup batch. format_mlib.bat, test_mlib.bat and
:: build_mlib_docs.bat all use what it installed.
:: The browser checks of the documentation need _docs\browser-requirements.txt
:: as well; install it only when you run them (see _docs\README.md).
::
:: Exit code: 0 when the tools are ready, otherwise 1.
::
:: The Japanese messages are in messages.txt and shown by _message.bat (this
:: file stays ASCII). The last message starts with [OK] or [NG].
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

rem Reuse an existing environment. Do not replace a broken one automatically.
IF EXIST "%MLIB_TOOLS_ENV%" GOTO :existing_environment
IF EXIST "%MLIB_TOOLS_SITE%" GOTO :existing_mayapy

rem Ask the Windows Python launcher for each version, newest first.
rem "python" is not used: it can be the Microsoft Store placeholder, which
rem opens the Store instead of running Python. "py -3" is not used either:
rem it picks the newest installed Python, and 3.15 or later is not accepted
rem (the same range as generate_mlib_stubs.bat, without the versions that
rem Sphinx 8.2 does not support).
rem Only look for an installed Python: never let the launcher install one.
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
rem Fall back to mayapy of Maya 2027-2025 (Python 3.11 or newer).
rem mayapy cannot create a venv (the venv looks for python.exe next to
rem mayapy.exe), so the tools go into .mayapy-site with pip install --target.
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
rem Keep packages in the user site of mayapy out of this environment.
SET "PYTHONNOUSERSITE=1"
"%MLIB_TOOLS_MAYAPY%" -m pip install --disable-pip-version-check --upgrade --target "%MLIB_TOOLS_SITE%" -r "%MLIB_TOOLS_DEV%" -r "%MLIB_TOOLS_DOCS%"
IF NOT ERRORLEVEL 1 GOTO :installed_mayapy
SET "MLIB_TOOLS_MESSAGE=setup.installFailed"
GOTO :finish

:installed_mayapy
rem format_mlib.bat and build_mlib_docs.bat read this file to use the same mayapy.
>"%MLIB_TOOLS_MAYAPY_FILE%" ECHO %MLIB_TOOLS_MAYAPY%
SET "MLIB_TOOLS_RUFF=%MLIB_TOOLS_SITE%\bin\ruff.exe"
SET "MLIB_TOOLS_PYTHON=%MLIB_TOOLS_MAYAPY%"

:verify
rem MLIB_TOOLS_MESSAGE is still setup.verifyFailed: it is shown when one of
rem these does not run.
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
