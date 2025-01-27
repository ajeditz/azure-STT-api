# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install the GStreamer to convert from webm to PCM (important to install, otherwise won't work)
RUN apt-get update && apt-get install -y \
    libgstreamer1.0-0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly


# Copy the rest of the application code into the container
COPY . .

# Expose the port that the FastAPI app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main2:app", "--host", "0.0.0.0", "--port", "8000"]
