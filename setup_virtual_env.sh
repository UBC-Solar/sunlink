#!/bin/bash 

# Creating a python virtual environment
echo -e "\nCreating Python Virtual Environment"
python3 -m venv environment
source environment/bin/activate
echo -e "Created Virtual Environment, Installing Requirements.txt\n"
python -m pip install -r requirements.txt
