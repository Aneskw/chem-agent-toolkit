FROM python@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535
ENV DGLBACKEND=pytorch PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /opt/retroknn
COPY requirements.lock probe.py check_native.py /opt/retroknn/
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake git ca-certificates libgomp1 libx11-6 libxext6 libxrender1 libexpat1 zlib1g && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir --no-deps --require-hashes --only-binary=:all: -r requirements.lock
COPY limit_build_jobs.py /opt/retroknn/
RUN git clone --branch v2.4.0 --depth 1 --recurse-submodules --shallow-submodules https://github.com/dmlc/dgl.git /tmp/dgl && test "$(git -C /tmp/dgl rev-parse HEAD)" = c6c874bf7ea085beb04ea1487cfd216a0bacd6c1 && python /opt/retroknn/limit_build_jobs.py /tmp/dgl 2 && cd /tmp/dgl && cmake -S . -B build -DBUILD_TYPE=release -DUSE_CUDA=OFF -DTORCH_PYTHON_INTERPS=/usr/local/bin/python && cmake --build build --parallel 2 && cd python && python setup.py bdist_wheel && python -m pip install --no-cache-dir --no-deps dist/dgl-2.4.0-*.whl && rm -rf /tmp/dgl
RUN apt-get purge -y build-essential cmake git make gcc g++ && python -m pip check && python /opt/retroknn/check_native.py
WORKDIR /work
CMD ["python"]
ENTRYPOINT []
