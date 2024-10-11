FROM python:3.9

WORKDIR /app

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PIP_NO_CACHE_DIR false

RUN pip install --upgrade pip && pip install pipenv
RUN apt-get -y update && apt-get -y install ffmpeg imagemagick

# Install some special fonts we use in testing, etc..
RUN apt-get -y install fonts-liberation

RUN apt-get install -y locales && \
    locale-gen C.UTF-8 && \
    /usr/sbin/update-locale LANG=C.UTF-8

ENV LC_ALL C.UTF-8

COPY requirements.txt .
RUN pip install -r requirements.txt

# modify ImageMagick policy file so that Textclips work correctly.
RUN sed -i 's/none/read,write/g' /etc/ImageMagick-6/policy.xml

# Copy the application code into the container
COPY app.py .

# Set the command to run the application
CMD ["python", "app.py"]
