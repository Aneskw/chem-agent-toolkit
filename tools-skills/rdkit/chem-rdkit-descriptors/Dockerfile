# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /opt/skill
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements.txt \
    && python -m pip check
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app
COPY scripts/calc_descriptors.py ./scripts/calc_descriptors.py
COPY execution/fixtures.json ./execution/fixtures.json
USER app
RUN python -c "from rdkit import Chem; assert Chem.MolFromSmiles('CCO') is not None"
ENTRYPOINT ["python", "/opt/skill/scripts/calc_descriptors.py"]
CMD ["--help"]
