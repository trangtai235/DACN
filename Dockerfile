FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
COPY requirements ./requirements
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY dist ./dist
COPY scripts ./scripts
RUN chmod +x /app/scripts/entrypoint.sh && useradd --create-home annotaflow && mkdir -p /app/backend/private_data /app/backend/staticfiles && chown -R annotaflow:annotaflow /app
USER annotaflow
WORKDIR /app/backend
EXPOSE 8000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["web"]
