# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if any are needed (e.g., for Pillow)
# Pillow on slim images might need some libs, but often the wheels are fine.
# If you run into issues, uncomment the next line:
# RUN apt-get update && apt-get install -y libopenjp2-7 libtiff6 && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Make port 2021 available to the world outside this container
EXPOSE 2021

# Define environment variable for Flask
ENV FLASK_APP=app.py
ENV PORT=2021

# Run app.py when the container launches
CMD ["python", "app.py"]
