# Imagem do back do UniDash (Python 3.14, mesma versão do computador).
# Usada no docker-compose local e, na etapa 8, pelo CapRover.
FROM python:3.14-slim

# Sem arquivos .pyc e com o log aparecendo na hora
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primeiro só as bibliotecas: o Docker reaproveita esta camada enquanto o
# requirements.txt não mudar, e a imagem é montada bem mais rápido.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
