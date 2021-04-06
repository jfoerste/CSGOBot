FROM python:latest

MAINTAINER jfoerste "github@jfoe.de"

COPY ./requirements.txt /requirements.txt

WORKDIR /

RUN python -m pip install -r requirements.txt

ENV FLASK_APP=app/app.py
ENV FLASK_RUN_HOST=0.0.0.0
EXPOSE 5000

COPY . /

CMD ["flask",  "run" ]