FROM sha256:ede4448a83055a5a1e65b4000dc39cd91f0f5d9e08bc483f88f4e96a51421187
USER root
RUN rm -rf /usr/local/lib/python3.12/site-packages/icarus_memory
COPY sidecar/icarus_memory /usr/local/lib/python3.12/site-packages/icarus_memory
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.a214f99
LABEL org.opencontainers.image.revision=a214f99cde2c8910d1ba5e762b2e89f485380471
USER kingfisher
