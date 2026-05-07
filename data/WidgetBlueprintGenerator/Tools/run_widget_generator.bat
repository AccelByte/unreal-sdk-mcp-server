@echo off
setlocal

set "PROJECT=%~dp0..\..\..\AccelByteWars.uproject"
set "SPEC=%~dp0specs\login_widget.json"
set "EDITOR_EXE=%UNREAL_EDITOR_EXE%"

if not "%~1"=="" set "SPEC=%~1"
if not "%~2"=="" set "PROJECT=%~2"
if not "%~3"=="" set "EDITOR_EXE=%~3"

if "%EDITOR_EXE%"=="" (
    echo ERROR: Set UNREAL_EDITOR_EXE to the full path of UnrealEditor-Cmd.exe or pass it as the third argument.
    exit /b 1
)

python "%~dp0widget_blueprint_generator.py" generate "%SPEC%" --project "%PROJECT%" --editor-exe "%EDITOR_EXE%" --force
