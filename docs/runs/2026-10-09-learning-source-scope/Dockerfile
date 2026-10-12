FROM sha256:6b03de639866319d310581f003345c458b13e824d53bb4e76a5381c14f5c9430
USER root
RUN rm -rf /usr/local/lib/python3.12/site-packages/icarus_memory
COPY sidecar/icarus_memory /usr/local/lib/python3.12/site-packages/icarus_memory
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.9f18408
LABEL org.opencontainers.image.revision=9f18408c8d6c8b0fd55c334cfc3ab184d933bb42
USER kingfisher
