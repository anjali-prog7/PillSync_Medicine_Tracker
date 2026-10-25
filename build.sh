#!/usr/bin/env bash
set -o errexit

cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
