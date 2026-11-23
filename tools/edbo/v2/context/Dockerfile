FROM ghcr.io/jinselw/chem-tools@sha256:e939ef5c984c02876db5a779ef1a66d77329a71e7471c484c11e63419e272a04
USER root
RUN apt-mark hold libxrender1 libxext6 && apt-get update && apt-get install -y --no-install-recommends graphviz=2.42.4-3 && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /opt/retrostar/requirements.lock
RUN python -m pip install --no-cache-dir --no-deps --require-hashes -r /opt/retrostar/requirements.lock && python -m pip check
COPY fetch_source.py /opt/retrostar/fetch_source.py
RUN python /opt/retrostar/fetch_source.py && python -m pip install --no-deps --no-build-isolation -e /opt/retrostar/src/retro_star/packages/mlp_retrosyn -e /opt/retrostar/src/retro_star/packages/rdchiral -e /opt/retrostar/src && python -m pip check
COPY probe.py /opt/retrostar/probe.py
WORKDIR /work
ENTRYPOINT []
CMD ["python"]
ENTRYPOINT []
