FROM mambaorg/micromamba@sha256:ce2026639d612fbe837a35ca9d513292a8d776a24a5e6c82cccf9dddf45ad3d2
USER root
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN micromamba install -y -n base --override-channels -c conda-forge --strict-channel-priority python=3.12.16=h5f976f7_0_cpython openbabel=3.2.1=py312hfeebd6e_1 pip && micromamba clean --all --yes
ENV PATH=/opt/conda/bin:$PATH
ENV LD_LIBRARY_PATH=/opt/conda/lib
ENV MPLBACKEND=Agg
ENV PYTHONUNBUFFERED=1
COPY requirements.txt patch_import.py probe.py /opt/autoqchem/
RUN python -m pip install --no-cache-dir --only-binary=:all: pip==26.3 setuptools==84.2.1 wheel==0.48.0 && python -m pip install --no-cache-dir --only-binary=:all: -r /opt/autoqchem/requirements.txt && python /opt/autoqchem/patch_import.py && python -m pip check && python -m pip freeze > /opt/autoqchem/installed.txt
RUN python /opt/autoqchem/probe.py Python 3.12.16 && python /opt/autoqchem/probe.py openbabel 3.2.1 && python /opt/autoqchem/probe.py auto-qchem 1.3.16 && python /opt/autoqchem/probe.py numpy 2.5.4 && python /opt/autoqchem/probe.py pandas 3.1.1 && python /opt/autoqchem/probe.py scipy 1.18.1 && python /opt/autoqchem/probe.py rdkit 2026.9.1
WORKDIR /work
ENTRYPOINT []
CMD ["python"]
ENTRYPOINT []
