FROM ghcr.io/jinselw/chem-tools@sha256:e9898a1635c84259ba8d835739a2112214d3c67762ab1e1831f2636971cc24f1
USER root
COPY source-manifest.json fetch_source.py probe.py /opt/localretro/
RUN python /opt/localretro/fetch_source.py
ENTRYPOINT []
