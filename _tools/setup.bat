@echo off
setlocal

::----------------------------------------------------------------
:: Put the tools used while writing mlib (ruff) into this folder, so that
:: everyone formats the code with the same version. mlib itself does not need
:: them, and nothing is installed into Maya or changed on the system.
::
::   setup.bat              create the environment and install the tools
::   setup.bat --no-pause   do not wait for a key at the end
::
:: It creates ".venv" in this folder with the Python of the Windows Python
:: launcher (py), newest version first, and installs requirements-dev.txt in
:: it. When no Python is installed, it uses mayapy of Maya 2027-2023 and
:: installs into ".mayapy-site" instead (mayapy cannot create a venv).
:: An existing .venv or .mayapy-site is reused and a broken one is left alone.
::
:: format_mlib.bat and check_mlib_layout.bat use what this batch installed.
:: The same layout as _docs\setup.bat, which does this for the documentation.
::----------------------------------------------------------------
SET "MLIB_TOOLS_ENV=%~dp0.venv"
SET "MLIB_TOOLS_PYTHON=%~dp0.venv\Scripts\python.exe"
SET "MLIB_TOOLS_RUFF=%~dp0.venv\Scripts\ruff.exe"
SET "MLIB_TOOLS_SITE=%~dp0.mayapy-site"
SET "MLIB_TOOLS_MAYAPY_FILE=%~dp0.mayapy-site\mayapy-path.txt"
SET "MLIB_TOOLS_RESULT=1"

rem Reuse an existing environment. Do not replace a broken one automatically.
IF EXIST "%MLIB_TOOLS_ENV%" GOTO :existing_environment
IF EXIST "%MLIB_TOOLS_SITE%" GOTO :existing_mayapy

rem Ask the Windows Python launcher for each version, newest first.
rem "python" is not used: it can be the Microsoft Store placeholder, which
rem opens the Store instead of running Python. "py -3" is not used either:
rem it picks the newest installed Python, and 3.15 or later is not accepted
rem (the same range as generate_mlib_stubs.bat).
rem Only look for an installed Python: never let the launcher install one.
SET "PYLAUNCHER_ALLOW_INSTALL="
SET "MLIB_TOOLS_PY="
FOR %%V IN (3.14 3.13 3.12 3.11 3.10 3.9) DO (
    IF NOT DEFINED MLIB_TOOLS_PY (
        py -%%V -c "import sys" >NUL 2>&1
        IF NOT ERRORLEVEL 1 SET "MLIB_TOOLS_PY=%%V"
    )
)
IF NOT DEFINED MLIB_TOOLS_PY GOTO :find_mayapy
ECHO Using Python %MLIB_TOOLS_PY% of the Python launcher.
py -%MLIB_TOOLS_PY% -m venv "%MLIB_TOOLS_ENV%"
IF ERRORLEVEL 1 GOTO :create_failed
GOTO :install

:find_mayapy
rem Fall back to mayapy of Maya 2027-2023 (Python 3.9 or newer).
rem mayapy cannot create a venv (the venv looks for python.exe next to
rem mayapy.exe), so the tools go into .mayapy-site with pip install --target.
SET "MLIB_TOOLS_MAYAPY="
FOR %%V IN (2027 2026 2025 2024 2023) DO (
    IF NOT DEFINED MLIB_TOOLS_MAYAPY IF EXIST "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" SET "MLIB_TOOLS_MAYAPY=C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe"
)
IF DEFINED MLIB_TOOLS_MAYAPY GOTO :install_mayapy
ECHO Python 3.9 to 3.14 was not found with the Python launcher (py),
ECHO and neither was mayapy of Maya 2027-2023.
ECHO Install Python for Windows, then run this batch again.
GOTO :finish

:existing_environment
IF EXIST "%MLIB_TOOLS_PYTHON%" GOTO :install
ECHO The existing .venv does not contain Scripts\python.exe.
ECHO It was left unchanged. Rename it to .venv-backup and run this batch again.
GOTO :finish

:existing_mayapy
IF NOT EXIST "%MLIB_TOOLS_MAYAPY_FILE%" GOTO :broken_mayapy
SET /p MLIB_TOOLS_MAYAPY=<"%MLIB_TOOLS_MAYAPY_FILE%"
IF NOT EXIST "%MLIB_TOOLS_MAYAPY%" GOTO :broken_mayapy
GOTO :install_mayapy

:broken_mayapy
ECHO The existing .mayapy-site does not name an installed mayapy.
ECHO It was left unchanged. Remove it and run this batch again.
GOTO :finish

:install
"%MLIB_TOOLS_PYTHON%" -m pip install --disable-pip-version-check -r "%~dp0requirements-dev.txt"
IF ERRORLEVEL 1 GOTO :install_failed
GOTO :verify

:install_mayapy
ECHO Using "%MLIB_TOOLS_MAYAPY%".
rem Keep packages in the user site of mayapy out of this environment.
SET "PYTHONNOUSERSITE=1"
"%MLIB_TOOLS_MAYAPY%" -m pip install --disable-pip-version-check --upgrade --target "%MLIB_TOOLS_SITE%" -r "%~dp0requirements-dev.txt"
IF ERRORLEVEL 1 GOTO :install_failed
rem format_mlib.bat reads this file to run the checks with the same mayapy.
>"%MLIB_TOOLS_MAYAPY_FILE%" ECHO %MLIB_TOOLS_MAYAPY%
SET "MLIB_TOOLS_RUFF=%MLIB_TOOLS_SITE%\bin\ruff.exe"
SET "MLIB_TOOLS_PYTHON=%MLIB_TOOLS_MAYAPY%"

:verify
IF NOT EXIST "%MLIB_TOOLS_RUFF%" (
    ECHO ruff was installed but "%MLIB_TOOLS_RUFF%" is missing.
    GOTO :finish
)
"%MLIB_TOOLS_RUFF%" --version
IF ERRORLEVEL 1 GOTO :finish
"%MLIB_TOOLS_PYTHON%" -c "import sys; print(sys.version)"
IF ERRORLEVEL 1 GOTO :finish

SET "MLIB_TOOLS_RESULT=0"
ECHO.
ECHO Tool setup succeeded.
ECHO Next, run "%~dp0format_mlib.bat" to format the code and check it.
GOTO :finish

:create_failed
ECHO Could not create the Python environment for the tools.
ECHO Check the messages above.
GOTO :finish

:install_failed
ECHO Installing the tools failed. Check the messages and network connection.

:finish
ECHO.
IF /I NOT "%~1"=="--no-pause" PAUSE
EXIT /b %MLIB_TOOLS_RESULT%
