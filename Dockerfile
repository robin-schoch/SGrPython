FROM python:3.8-slim-buster

WORKDIR /app

# PROD 
COPY . .

# # DEV
# COPY xsd_files xsd_files
# COPY xml_files xml_files
# COPY requirements.txt requirements.txt

# RUN pip3 install -e .
RUN pip install -r requirements.txt
RUN pip install xsdata[cli]

# generate data classes
RUN xsdata --package data_classes xsd_files/SGrIncluder.xsd

# CMD ["python3", "SGr_test_lehmann.py"]