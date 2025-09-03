# Use a lightweight Python image as the base
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /chef

# Copy the requirements file and install dependencies
COPY requirements.txt /chef
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . /chef

# Set the environment variable for Cloud Run
ENV PORT 8080

# Expose the port expected by Cloud Run
EXPOSE 8080

# Ensure logs are flushed immediately
ENV PYTHONUNBUFFERED=1

# Specify the command to run your app
CMD ["python", "main.py"]
