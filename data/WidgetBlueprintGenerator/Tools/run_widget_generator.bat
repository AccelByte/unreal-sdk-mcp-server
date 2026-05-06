@echo off
setlocal

set "PROJECT=%~dp0..\..\..\AccelByteWars.uproject"
set "SPEC=%~dp0specs\login_widget.json"
set "EDITOR_EXE=E:\EpicGames\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"

if not "%~1"=="" set "SPEC=%~1"
if not "%~2"=="" set "PROJECT=%~2"
if not "%~3"=="" set "EDITOR_EXE=%~3"

python "%~dp0widget_blueprint_generator.py" generate "%SPEC%" --project "%PROJECT%" --editor-exe "%EDITOR_EXE%" --force
