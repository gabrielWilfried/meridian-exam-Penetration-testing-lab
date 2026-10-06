FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir flask requests pyjwt
COPY app.py /app/app.py
WORKDIR /app
EXPOSE 80
CMD ["python3", "app.py"]
