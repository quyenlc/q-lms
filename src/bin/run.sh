#!/bin/bash

python3 manage.py makemigrations
python3 manage.py migrate
gunicorn --bind :8000 -w 2 wsgi:application
