FROM python:3.9-slim

COPY ./app /app
COPY ./requirements/base.txt /app

WORKDIR /app

RUN python3 -m pip install -r base.txt

CMD ["uvicorn", "main:app", "--reload", "--port", "8000"]
