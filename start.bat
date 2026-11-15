@echo off
setlocal

if not "%~2"=="" goto usage_error
if "%~1"=="--help" goto help
if "%~1"=="-h" goto help
if not "%~1"=="" if not "%~1"=="--rebuild" goto usage_error

where docker >nul 2>&1
if errorlevel 1 (
    echo Docker is not installed or is not available in PATH.
    goto failure
)

docker info >nul 2>&1
if errorlevel 1 (
    echo Start Docker and try again.
    goto failure
)

if "%~1"=="--rebuild" goto rebuild
docker container inspect avs-lab3 >nul 2>&1
if not errorlevel 1 goto existing

:rebuild
docker build -t avs-lab3-printer "%~dp0."
if errorlevel 1 goto failure

docker container inspect avs-lab3 >nul 2>&1
if errorlevel 1 goto create
docker stop --time 8 avs-lab3 >nul
if errorlevel 1 goto failure
docker rm avs-lab3 >nul
if errorlevel 1 goto failure

:create
docker run -dit --name avs-lab3 --mount type=volume,source=avs-lab3-work,target=/work avs-lab3-printer >nul
if errorlevel 1 goto failure
goto connect

:existing
docker start avs-lab3 >nul
if errorlevel 1 goto failure

:connect
docker exec -it avs-lab3 bash
if errorlevel 1 goto failure
exit /b 0

:failure
pause
exit /b 1

:help
echo Usage: start.bat [--rebuild]
echo Starts the lab with two printers and opens Bash.
echo --rebuild rebuilds the image and replaces the container, ending all sessions.
echo Files in /work are preserved in the avs-lab3-work volume.
exit /b 0

:usage_error
echo Unknown arguments. Use start.bat --help.
exit /b 2
