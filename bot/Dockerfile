FROM python:latest

MAINTAINER jfoerste "github@jfoe.de"

COPY ./requirements.txt /requirements.txt

WORKDIR /

RUN python -m pip install -r requirements.txt

COPY . /

CMD ["python",  "app/app.py" ]