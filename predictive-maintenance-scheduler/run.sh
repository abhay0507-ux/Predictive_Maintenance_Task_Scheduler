#!/usr/bin/env bash
# ./run.sh setup   (first time)      ./run.sh   (start)
if [ "$1" = "setup" ]; then
  pip install -r requirements.txt && python -m backend.init_db && python -m ml.train_model
  (cd cpp_engine && g++ -O2 -std=c++17 -o scheduler_engine scheduler_engine.cpp && echo "C++ engine built")
else
  python -m uvicorn backend.main:app --reload
fi
