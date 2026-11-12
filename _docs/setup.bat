@echo off
setlocal

set "MLIB_DOCS_ENV=%~dp0.venv"
set "MLIB_DOCS_PYTHON=%~dp0.venv\Scripts\python.exe"
set "MLIB_DOCS_SITE=%~dp0.mayapy-site"
set "MLIB_DOCS_MAYAPY_FILE=%~dp0.mayapy-site\mayapy-path.txt"
set "MLIB_DOCS_RESULT=1"

rem Reuse an existing environment. Do not replace a broken one automatically.
if exist "%MLIB_DOCS_ENV%" goto existing_environment
if exist "%MLIB_DOCS_SITE%" goto existing_mayapy

rem Ask the Windows Python launcher for each version, newest first.
rem "python" is not used: it can be the Microsoft Store placeholder, which
rem opens the Store instead of running Python. "py -3" is not used either:
rem it picks the newest installed Python, and with 3.15 or later pip cannot
rem get a prebuilt PyYAML (needed by sphinx-autoapi) and stops at building it.
rem Only look for an installed Python: never let the launcher install one.
set "PYLAUNCHER_ALLOW_INSTALL="
set "MLIB_DOCS_PY="
for %%V in (3.14 3.13 3.12 3.11) do (
    if not defined MLIB_DOCS_PY (
        py -%%V -c "import sys" >nul 2>&1
        if not errorlevel 1 set "MLIB_DOCS_PY=%%V"
    )
)
if defined MLIB_DOCS_PY (
    echo Using Python %MLIB_DOCS_PY% of the Python launcher.
    py -%MLIB_DOCS_PY% -m venv "%MLIB_DOCS_ENV%"
    if errorlevel 1 goto create_failed
    goto install
)

rem Fall back to mayapy of Maya 2027-2025 (Python 3.11 or newer).
rem mayapy cannot create a venv (the venv looks for python.exe next to mayapy.exe),
rem so the packages go into .mayapy-site with pip install --target instead.
for %%V in (2027 2026 2025) do (
    if exist "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" (
        set "MLIB_DOCS_MAYAPY=C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe"
        goto install_mayapy
    )
)
echo Python 3.11 to 3.14 was not found with the Python launcher (py),
echo and neither was mayapy of Maya 2027-2025.
echo Install Python 3.14 for Windows, then run this batch again.
echo See "%~dp0README.md" for the download link and setup steps.
goto finish

:existing_environment
if exist "%MLIB_DOCS_PYTHON%" goto install
echo The existing .venv does not contain Scripts\python.exe.
echo It was left unchanged. See the troubleshooting section in README.md.
goto finish

:existing_mayapy
if not exist "%MLIB_DOCS_MAYAPY_FILE%" goto broken_mayapy
set /p MLIB_DOCS_MAYAPY=<"%MLIB_DOCS_MAYAPY_FILE%"
if not exist "%MLIB_DOCS_MAYAPY%" goto broken_mayapy
goto install_mayapy

:broken_mayapy
echo The existing .mayapy-site does not name an installed mayapy.
echo It was left unchanged. See the troubleshooting section in README.md.
goto finish

:install
"%MLIB_DOCS_PYTHON%" -c "import sys; print(sys.version); sys.exit(not ((3, 11) <= sys.version_info[:2] <= (3, 14)))"
if errorlevel 1 (
    echo The existing .venv must use Python 3.11 to 3.14.
    echo See the troubleshooting section in README.md.
    goto finish
)

"%MLIB_DOCS_PYTHON%" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo Dependency installation failed. Check the messages and network connection.
    goto finish
)
"%MLIB_DOCS_PYTHON%" -m pip check
if errorlevel 1 goto finish
goto verify

:install_mayapy
echo Using "%MLIB_DOCS_MAYAPY%".
rem Keep packages in the user site of mayapy out of the documentation build.
set "PYTHONNOUSERSITE=1"
"%MLIB_DOCS_MAYAPY%" -c "import sys; print(sys.version); sys.exit(sys.version_info < (3, 11))"
if errorlevel 1 (
    echo mayapy requires Python 3.11 or newer.
    goto finish
)
"%MLIB_DOCS_MAYAPY%" -m pip install --disable-pip-version-check --upgrade --target "%MLIB_DOCS_SITE%" -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo Dependency installation failed. Check the messages and network connection.
    goto finish
)
rem rebuild.bat reads this file to run Sphinx with the same mayapy.
>"%MLIB_DOCS_MAYAPY_FILE%" echo %MLIB_DOCS_MAYAPY%
set "PYTHONPATH=%MLIB_DOCS_SITE%"
set "MLIB_DOCS_PYTHON=%MLIB_DOCS_MAYAPY%"

:verify
"%MLIB_DOCS_PYTHON%" -P -m sphinx --version
if errorlevel 1 goto finish
"%MLIB_DOCS_PYTHON%" -P -c "import autoapi; from importlib.metadata import version; print('sphinx-autoapi: ' + version('sphinx-autoapi'))"
if errorlevel 1 goto finish

set "MLIB_DOCS_RESULT=0"
echo.
echo Documentation setup succeeded.
echo Next, run "%~dp0rebuild.bat" to build the HTML pages.
goto finish

:create_failed
echo Could not create the documentation Python environment.
echo Check the messages above and the troubleshooting section in README.md.

:finish
echo.
if /I not "%~1"=="--no-pause" pause
exit /b %MLIB_DOCS_RESULT%
