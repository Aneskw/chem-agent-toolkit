FROM mambaorg/micromamba@sha256:ce2026639d612fbe837a35ca9d513292a8d776a24a5e6c82cccf9dddf45ad3d2
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libxrender1=1:0.9.12-1 libxext6=2:1.3.4-1+b3 && rm -rf /var/lib/apt/lists/*
RUN micromamba create -y -n edbo --override-channels -c rdkit -c https://repo.anaconda.com/pkgs/main -c https://repo.anaconda.com/pkgs/r python=3.7.5 rdkit=2019.09.3.0 numpy=1.18.1 pandas=1.0.1 pillow=7.0.0 pip=20.0.2 setuptools=45.2.0 wheel=0.34.2 && micromamba clean --all --yes
ENV PATH=/opt/conda/envs/edbo/bin:$PATH MPLBACKEND=Agg PYTHONUNBUFFERED=1
COPY requirements.lock /opt/edbo/requirements.lock
RUN python -m pip install --no-cache-dir --no-deps 'https://download.pytorch.org/whl/cpu/torch-1.3.1%2Bcpu-cp37-cp37m-linux_x86_64.whl' && python -m pip install --no-cache-dir --no-deps --no-build-isolation -r /opt/edbo/requirements.lock && python -m pip check
COPY probe.py /opt/edbo/probe.py
COPY check_native.py /opt/edbo/check_native.py
RUN python /opt/edbo/check_native.py
WORKDIR /work
ENTRYPOINT []
CMD ["python"]
ENTRYPOINT []
