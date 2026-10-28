FROM python:3.11-slim
WORKDIR /opt/skill
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
ENV PYTHONDONTWRITEBYTECODE="1"
ENV PYTHONUNBUFFERED="1"
COPY ["sources/rdkit/requirements.txt", "./sources/rdkit/requirements.txt"]
RUN python -m pip install --no-cache-dir -r /opt/skill/sources/rdkit/requirements.txt
COPY . ./
USER 10001:10001
ENTRYPOINT ["python", "/opt/skill/package/scripts/calc_descriptors.py"]
