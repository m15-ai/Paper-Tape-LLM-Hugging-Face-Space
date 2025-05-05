FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip curl unzip git \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

ENV PATH="/root/.ollama/bin:${PATH}"

ENV OLLAMA_DIR=/app/.ollama

RUN ollama run qwen:0.5b || true

WORKDIR /app
COPY app/ /app/

RUN pip install -r requirements.txt

EXPOSE 7860

CMD ollama serve & sleep 5 && python3 app.py
