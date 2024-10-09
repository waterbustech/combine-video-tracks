# Use the official Python 3.8 base image
FROM python:3.8

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install system dependencies and Python packages
RUN apt-get update && apt-get install -y \
        ffmpeg libsm6 libxext6 libgl1-mesa-glx && pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY app.py .

# Set the command to run the application
CMD ["python", "app.py"]
