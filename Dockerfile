FROM python:3.6-slim-stretch

ENV APP /app
RUN mkdir -p $APP
WORKDIR /app

ADD requirements.txt $APP/requirements.txt
ADD tests/requirements.txt $APP/tests/requirements.txt
RUN pip install -r requirements.txt

CMD ["bash"]