@echo off
setlocal

::----------------------------------------------------------------
:: Format the mlib sources with ruff and check what ruff cannot fix.
:: The settings are in mlib\ruff.toml, so every run gives the same result.
:: Maya is not needed.
::
::   format_mlib.bat             format the files, fix what can be fixed,
::                               then list what is left
::   format_mlib.bat --check     change nothing; only report what is not
::                               formatted or still wrong (for a check before
::                               a commit, and for the workflow)
::   --no-pause                  do not wait for a key at the end
::                               (for terminals and other scripts)
::
:: It runs, in this order:
::   ruff format                 the layout of the code (spaces, blank lines,
::                               line breaks, quotes)
::   ruff check --fix            import order and grouping, unused names,
::                               pathlib, encodings, and the other rules of
::                               ruff.toml
::   check_mlib_layout.py        what ruff does not cover: the position of the
::                               constants, __all__ and TYPE_CHECKING, the order
::                               of the members of a class, and the input
::                               assertions of the public entries
::
:: Needs ruff. Run "%~dp0setup.bat" once to put the pinned version into
:: _tools\.venv (or into _tools\.mayapy-site when no Python is installed).
:: A ruff on the PATH or in a Python of the launcher (py) is used as well.
::
:: Exit code: 0 when everything passed, 1 when something is reported,
:: 2 when ruff or Python was not found.
::----------------------------------------------------------------
SET "PACKAGE=%~dp0.."
SET "LAYOUT=%~dp0check_mlib_layout.py"
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

rem Take --no-pause and --check out of the arguments.
:parse_args
IF "%~1"=="" GOTO :args_done
IF /I "%~1"=="--no-pause" SET "MLIB_FORMAT_PAUSE=" & GOTO :next_arg
IF /I "%~1"=="--check" SET "MLIB_FORMAT_CHECK=1" & GOTO :next_arg
ECHO [ERROR] Unknown argument "%~1". Use --check and --no-pause only.
GOTO :finish
:next_arg
SHIFT
GOTO :parse_args
:args_done
rem Only look for an installed Python: never let the launcher install one.
SET "PYLAUNCHER_ALLOW_INSTALL="

rem Prefer what setup.bat installed, so that everyone uses the same version:
rem .venv, then .mayapy-site, then a ruff on the PATH, then a Python of the
rem launcher. The checks that need Python use the same environment.
rem The version is put together outside the brackets: inside them the value of
rem a variable set in the same block is not yet available.
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
IF NOT DEFINED MLIB_FORMAT_RUFF (
    ECHO [ERROR] ruff was not found. Run this once to install it:
    ECHO     "%~dp0setup.bat"
    GOTO :finish
)
%MLIB_FORMAT_RUFF% --version

IF DEFINED MLIB_FORMAT_CHECK (
    %MLIB_FORMAT_RUFF% format --check "%PACKAGE%"
    SET "MLIB_FORMAT_RESULT=%ERRORLEVEL%"
    %MLIB_FORMAT_RUFF% check "%PACKAGE%"
    IF ERRORLEVEL 1 SET "MLIB_FORMAT_RESULT=1"
) ELSE (
    %MLIB_FORMAT_RUFF% format "%PACKAGE%"
    SET "MLIB_FORMAT_RESULT=%ERRORLEVEL%"
    %MLIB_FORMAT_RUFF% check --fix "%PACKAGE%"
    IF ERRORLEVEL 1 SET "MLIB_FORMAT_RESULT=1"
)

rem The checks that ruff does not cover. Python is needed only for these.
IF NOT DEFINED MLIB_FORMAT_PYTHON IF DEFINED MLIB_FORMAT_PY SET "MLIB_FORMAT_PYTHON=py -%MLIB_FORMAT_PY%"
IF NOT DEFINED MLIB_FORMAT_PYTHON SET "MLIB_FORMAT_PYTHON=py -3"
ECHO.
%MLIB_FORMAT_PYTHON% "%LAYOUT%" --check
IF ERRORLEVEL 1 SET "MLIB_FORMAT_RESULT=1"

:finish
rem Wait for a key so that the result stays readable when the batch was
rem started by a double click (the same as generate_mlib_stubs.bat).
IF DEFINED MLIB_FORMAT_PAUSE (
    ECHO.
    PAUSE
)
EXIT /b %MLIB_FORMAT_RESULT%
