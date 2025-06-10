FROM python:3.9
WORKDIR /app
ENV HOST=""
ENV PUSHGW=""
ENV INTERVAL=30
COPY push_node.py .
COPY requirements.txt .
RUN pip install -r requirements.txt
CMD ["python", "-u", "push_node.py"]

