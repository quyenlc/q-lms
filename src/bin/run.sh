#!/bin/bash

python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py collectstatic --noinput

if [ -n "$DEBUG" ]
then
    python3 manage.py runserver 0.0.0.0:8000
else
    gunicorn --bind :8000 -w 2 wsgi:application
fi
