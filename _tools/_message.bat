@echo off

::----------------------------------------------------------------
:: このフォルダーのバッチが出す日本語の文を表示する。
:: 単独で使う入口ではなく、ほかのバッチから CALL する補助。
::
::   CALL "%~dp0_message.bat" <キー> [<キー> ...]
::
:: messages.txt(UTF-8)のうち "<キー>=" で始まる行を、キーの順に全部表示する。
:: 行の中の %名前% は、その環境変数の値に置き換える。
:: 表示する文をバッチへ直接書かないのは、コンソールのコードページが
:: Shift-JISでないとき(chcp 65001 など)に文字化けするため。PowerShellが書き出すので、
:: コードページは変えずに済む。バッチに書く日本語はコメントだけにする。
:: キーが見つからないときはキーそのものを表示し、結果([OK]・[NG] は文の一部)が
:: 黙って消えないようにする。
::
:: このファイルは Shift-JIS(CP932)・CRLF で保存する(.gitattributes を参照)。
::----------------------------------------------------------------
SET "MLIB_MESSAGE_KEYS=%*"
SET "MLIB_MESSAGE_FILE=%~dp0messages.txt"
powershell -NoProfile -Command "$lines = [IO.File]::ReadAllLines($env:MLIB_MESSAGE_FILE, [Text.Encoding]::UTF8); foreach ($key in $env:MLIB_MESSAGE_KEYS.Split(' ', [StringSplitOptions]::RemoveEmptyEntries)) { $prefix = $key + '='; $shown = $false; foreach ($line in $lines) { if ($line.StartsWith($prefix)) { $shown = $true; Write-Host ([Environment]::ExpandEnvironmentVariables($line.Substring($prefix.Length))) } }; if (-not $shown) { Write-Host ('[message: ' + $key + ']') } }"
IF ERRORLEVEL 1 ECHO [messages: %*]
EXIT /b 0
