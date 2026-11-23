FROM python@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
RUN apt-get update && apt-get install -y --no-install-recommends --allow-downgrades gcc-14-base=14.2.0-19 libquadmath0=14.2.0-19 libgcc-s1=14.2.0-19 libstdc++6=14.2.0-19 zlib1g=1:1.3.dfsg+really1.3.1-1+b1 libexpat1=2.8.3-1~deb13u1 libx11-6=2:1.8.12-1 libxext6=2:1.3.4-1+b3 libxrender1=1:0.9.12-1 && rm -rf /var/lib/apt/lists/*
COPY requirements.lock probe.py check_native.py /opt/rxnmapper/
RUN python -m pip install --no-cache-dir --only-binary=:all: --no-deps --require-hashes -r /opt/rxnmapper/requirements.lock && python -m pip check && python /opt/rxnmapper/check_native.py && python /opt/rxnmapper/probe.py rxnmapper 0.4.3
WORKDIR /work
ENTRYPOINT []
