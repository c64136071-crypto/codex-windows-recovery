@echo off
if "%~2"=="-c" exit /b 0
echo healthy
if defined RECOVERY_TEST_EXIT exit /b %RECOVERY_TEST_EXIT%
exit /b 0
