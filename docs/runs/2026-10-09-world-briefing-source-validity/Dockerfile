FROM sha256:552a7d2f6ccc6433357000c2385dfe0b034f597a8c7126ea87fca3009580937a
USER root
RUN rm -rf /usr/local/lib/python3.12/site-packages/icarus_memory
COPY sidecar/icarus_memory /usr/local/lib/python3.12/site-packages/icarus_memory
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.e2bd4c1
LABEL org.opencontainers.image.revision=e2bd4c14e98a0aed7ca8a873286dbf46e53c52ad
USER kingfisher
