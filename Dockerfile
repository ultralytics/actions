# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install git
RUN apt-get update && apt-get install -y git

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the dependencies file to the working directory
COPY requirements.txt ./

# Install any dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your action's code
COPY entrypoint.sh .

# Make the entrypoint script executable
RUN chmod +x entrypoint.sh

# Run entrypoint.sh when the container launches
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
