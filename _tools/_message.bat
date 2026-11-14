@echo off

::----------------------------------------------------------------
:: Show the Japanese messages of the batch files in this folder.
:: Not an entry of its own: the other batch files CALL it.
::
::   CALL "%~dp0_message.bat" <key> [<key> ...]
::
:: Every line of messages.txt (UTF-8) that starts with "<key>=" is shown, in
:: the order of the keys, and %NAME% in it is replaced by the value of that
:: environment variable. The text is not written in the batch files
:: themselves, because cmd can misread a UTF-8 batch file after a GOTO.
:: PowerShell writes it, so the code page of the console is not changed.
:: When a key cannot be shown, the key itself is printed instead, so that the
:: result ([OK] or [NG] is part of the text) is never lost silently.
::----------------------------------------------------------------
SET "MLIB_MESSAGE_KEYS=%*"
SET "MLIB_MESSAGE_FILE=%~dp0messages.txt"
powershell -NoProfile -Command "$lines = [IO.File]::ReadAllLines($env:MLIB_MESSAGE_FILE, [Text.Encoding]::UTF8); foreach ($key in $env:MLIB_MESSAGE_KEYS.Split(' ', [StringSplitOptions]::RemoveEmptyEntries)) { $prefix = $key + '='; $shown = $false; foreach ($line in $lines) { if ($line.StartsWith($prefix)) { $shown = $true; Write-Host ([Environment]::ExpandEnvironmentVariables($line.Substring($prefix.Length))) } }; if (-not $shown) { Write-Host ('[message: ' + $key + ']') } }"
IF ERRORLEVEL 1 ECHO [messages: %*]
EXIT /b 0
