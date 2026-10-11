FROM sha256:6172ec0c0a63075d9a7481c9c934657f698a6f3d8764e063cdbccdf9a21daa63
USER root
COPY sidecar/icarus_memory/memory_categories.py /usr/local/lib/python3.12/site-packages/icarus_memory/memory_categories.py
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.45cb1c8
LABEL org.opencontainers.image.revision=45cb1c8272a1335a49b7a3adc1d59fa3c542e9c5
USER kingfisher
