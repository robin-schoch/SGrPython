FROM python:3.8-slim-buster

WORKDIR /app

COPY . .

# RUN pip3 install -e .
RUN pip install -r requirements.txt
RUN pip install xsdata[cli]

# generate data classes
RUN xsdata --package data_classes xsd_files/SGrIncluder.xsd

# CMD ["python3", "SGr_test_lehmann.py"]