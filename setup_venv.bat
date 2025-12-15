@echo off
echo Creating virtual environment...
py -3.13 -m venv venv

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Setup complete! The virtual environment is ready.
echo To activate it in the future, run: venv\Scripts\activate.bat
pause
