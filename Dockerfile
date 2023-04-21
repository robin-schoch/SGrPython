FROM python:3.7-slim-buster

WORKDIR /app

COPY . .

RUN pip3 install -e .

# CMD ["python3", "SGr_test_lehmann.py"]