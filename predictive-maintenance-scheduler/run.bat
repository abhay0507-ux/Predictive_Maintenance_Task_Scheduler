@echo off
REM One-click start for Windows. Run SETUP once (first time), then START.
if "%1"=="setup" goto setup
echo Starting server on http://127.0.0.1:8000 ...
start http://127.0.0.1:8000
python -m uvicorn backend.main:app --reload
goto end
:setup
pip install -r requirements.txt
python -m backend.init_db
python -m ml.train_model
echo Optional: cd cpp_engine ^&^& g++ -O2 -std=c++17 -o scheduler_engine scheduler_engine.cpp
:end
