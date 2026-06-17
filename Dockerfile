# 1) Base Image : Use official, lightweight python linux computer
FROM python:3.12-slim

# 2) Set the working directory
WORKDIR /app

# 3) Copy only the requirment file first 
# dot at the end tells it to copy it to the current directory
COPY requirements.txt .

# 4) Install the dependecies
RUN pip install --no-cache-dir -r requirements.txt

# 5) Copy everything else
# again dot at the end tells it to copy it to the current directory
COPY . .

# 6) Open port 8000 on the container
EXPOSE 8000

# 7) The command to start the server (NOTE the 0.0.0.0 host, This is required for DOCKER!!) 
# 0000 means accept connection from outside world (like windows computer) because the default is 127.0.0.1 which is local host and doenst allow taht
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]