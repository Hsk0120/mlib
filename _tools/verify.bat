@echo off
setlocal

::----------------------------------------------------------------
:: Run every gate for mlib in one go, in the order of CONTRIBUTING.md.
::
::   verify.bat                  format the sources, then run every check
::   verify.bat --check          change nothing; only report (before a commit)
::   verify.bat --no-maya        skip the Maya tests (the first three steps only)
::   --no-pause                  do not wait for a key at the end
::
:: It runs, in this order, and stops at the first failing step:
::   1. format_mlib.bat          ruff format, ruff check, check_mlib_layout.py
::   2. check_mlib_exports.py    the public names match the explicit exports
::   3. __tests__\runNoMaya.py   the tests that do not need Maya
::   4. __tests__\run.bat        the Maya 2027 tests (unit and integration)
::
:: The type stubs (_tools\generate_mlib_stubs.bat) and the documentation
:: (_docs\rebuild.bat) are NOT part of this batch. They are optional steps that
:: come after it, and they report their own problems (--check and -n -W).
:: For other Maya versions, call __tests__\run.bat --versions 2022 2027 directly.
::
:: Exit code: 0 when every step passed, otherwise the code of the first failure.
::----------------------------------------------------------------
rem Keep the paths before the argument loop: SHIFT changes %0, so %~dp0 would
rem no longer point at this batch file afterwards.
SET "TOOLS=%~dp0"
SET "TESTS=%~dp0..\__tests__"
SET "MLIB_VERIFY_PAUSE=1"
SET "MLIB_VERIFY_CHECK="
SET "MLIB_VERIFY_MAYA=1"
SET "MLIB_VERIFY_RESULT=0"

:parse_args
IF "%~1"=="" GOTO :args_done
IF /I "%~1"=="--no-pause" SET "MLIB_VERIFY_PAUSE=" & GOTO :next_arg
IF /I "%~1"=="--check" SET "MLIB_VERIFY_CHECK=--check" & GOTO :next_arg
IF /I "%~1"=="--no-maya" SET "MLIB_VERIFY_MAYA=" & GOTO :next_arg
ECHO [ERROR] Unknown argument "%~1". Use --check, --no-maya and --no-pause only.
SET "MLIB_VERIFY_RESULT=2"
GOTO :finish
:next_arg
SHIFT
GOTO :parse_args
:args_done
rem Only look for an installed Python: never let the launcher install one.
SET "PYLAUNCHER_ALLOW_INSTALL="

ECHO === 1/4 format and lint ===
CALL "%TOOLS%format_mlib.bat" --no-pause %MLIB_VERIFY_CHECK%
SET "MLIB_VERIFY_RESULT=%ERRORLEVEL%"
IF NOT "%MLIB_VERIFY_RESULT%"=="0" (
    ECHO [FAILED] format and lint
    GOTO :finish
)

ECHO.
ECHO === 2/4 public names ===
py -3 "%TOOLS%check_mlib_exports.py"
SET "MLIB_VERIFY_RESULT=%ERRORLEVEL%"
IF NOT "%MLIB_VERIFY_RESULT%"=="0" (
    ECHO [FAILED] public names
    GOTO :finish
)

ECHO.
ECHO === 3/4 tests without Maya ===
py -3 "%TESTS%\runNoMaya.py"
SET "MLIB_VERIFY_RESULT=%ERRORLEVEL%"
IF NOT "%MLIB_VERIFY_RESULT%"=="0" (
    ECHO [FAILED] tests without Maya
    GOTO :finish
)

IF NOT DEFINED MLIB_VERIFY_MAYA (
    ECHO.
    ECHO === 4/4 Maya tests: skipped by --no-maya ===
    GOTO :finish
)
ECHO.
ECHO === 4/4 Maya 2027 tests ===
CALL "%TESTS%\run.bat" --versions 2027 --suite all
SET "MLIB_VERIFY_RESULT=%ERRORLEVEL%"
IF NOT "%MLIB_VERIFY_RESULT%"=="0" ECHO [FAILED] Maya tests

:finish
ECHO.
IF "%MLIB_VERIFY_RESULT%"=="0" (
    ECHO All gates passed. The type stubs and the documentation are separate,
    ECHO optional steps: _tools\generate_mlib_stubs.bat and _docs\rebuild.bat.
)
rem Wait for a key so that the result stays readable after a double click.
IF DEFINED MLIB_VERIFY_PAUSE (
    ECHO.
    PAUSE
)
EXIT /b %MLIB_VERIFY_RESULT%
