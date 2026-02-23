# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# ---
# Note: No CMD is specified as the default command is unclear.
# You can build the image and then run a specific script like this:
#
# To build the image:
# docker build -t chuncproject .
#
# To run a script (e.g., 01_generate_dataset.py):
# docker run --rm -v ./data:/app/data -v ./models:/app/models chuncproject python scripts/01_generate_dataset.py
#
# To run the other script (e.g., 02_train_model.py):
# docker run --rm -v ./data:/app/data -v ./models:/app/models chuncproject python scripts/02_train_model.py
# ---
