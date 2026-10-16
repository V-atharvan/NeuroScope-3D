@echo off
REM NeuroScope 3D - Windows Platform Startup Script
echo ======================================================================
echo NeuroScope 3D - Starting Platform (Backend + Frontend)
echo Research and teaching prototype only. Not for clinical diagnosis.
echo ======================================================================

set PYTHON_CMD=.venv\Scripts\python.exe
if not exist %PYTHON_CMD% set PYTHON_CMD=python

%PYTHON_CMD% run_platform.py
