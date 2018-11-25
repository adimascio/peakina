FROM docker.io/python:3.6

ENV APP /app
RUN mkdir -p $APP
WORKDIR /app

COPY . /app
# ADD requirements.txt $APP/requirements.txt
# ADD tests/requirements.txt $APP/tests/requirements.txt
RUN pip install -r requirements.txt
RUN pip install -e .

CMD ["bash"]
