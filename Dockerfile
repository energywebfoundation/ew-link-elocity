FROM python:3.7-slim-stretch

# Set our working directory
WORKDIR /usr/src/app

# Copy requirements.txt first for better cache on later pushes
COPY Pipfile Pipfile.lock ./

# pip install python deps from requirements.txt on the resin.io build server
RUN apt-get update && apt-get install -yq gcc libc-dev apt-utils && apt-get clean && rm -rf /var/lib/apt/lists/*; \
    pip3 install --upgrade pip setuptools pipenv; \
    pipenv install --system --deploy; \
    mkdir -p /opt/elocity

# This will copy all files in our root to the working  directory in the container
COPY . ./

# Remove warnings
ENV PYTHONWARNINGS="ignore"

# bond.py will run when container starts up on the device
CMD ["python", "main.py"]