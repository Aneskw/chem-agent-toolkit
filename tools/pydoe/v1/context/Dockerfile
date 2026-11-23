FROM python@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /opt/pydoe
COPY requirements.txt probe.py /opt/pydoe/
RUN python -m pip install --only-binary=:all: pip==26.3 setuptools==84.2.1 wheel==0.48.0 && python -m pip install --only-binary=:all: numpy==2.4.6 scipy==1.17.1 && python -m pip install --no-deps --no-build-isolation -r requirements.txt && python -m pip check
RUN python /opt/pydoe/probe.py pyDOE2 1.3.0
ENTRYPOINT []
