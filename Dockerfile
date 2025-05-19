FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

ENV MPLCONFIGDIR=/app/.config/matplotlib

RUN apt-get update && apt-get install -y \
    python3 python3-pip curl unzip git \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/.config/matplotlib

WORKDIR /app
COPY app/ /app/

RUN pip install -r requirements.txt

EXPOSE 7860

CMD python3 app.py

