# Use a lightweight Python image as the base
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /chef

# Copy the requirements file and install dependencies
COPY requirements.txt /chef
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . /chef

# Expose a port (optional, if you're running a web server like Flask)
EXPOSE 8080

# Specify the command to run your app
CMD ["python", "main.py"]
