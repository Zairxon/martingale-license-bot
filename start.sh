#!/bin/bash
python create_db.py
gunicorn api:app --host 0.0.0.0 --port $PORT
