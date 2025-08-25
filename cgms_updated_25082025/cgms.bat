@echo off
ECHO Starting the Court Case Information System...

:: Activate the virtual environment
ECHO Activating virtual environment...
CALL "C:\Users\admin\Desktop\Sangrur Court\src_02\venv\Scripts\activate.bat"
IF ERRORLEVEL 1 (
    ECHO Failed to activate virtual environment.
    PAUSE
    EXIT /B 1
)

:: Run the Python script
ECHO Running sangrur_main.py...
python "C:\Users\admin\Desktop\Sangrur Court\src_02\sangrur_main.py"
IF ERRORLEVEL 1 (
    ECHO Failed to run sangrur_main.py.
    PAUSE
    EXIT /B 1
)

:: Deactivate the virtual environment
ECHO Deactivating virtual environment...
CALL deactivate

ECHO Script execution completed.
PAUSE


