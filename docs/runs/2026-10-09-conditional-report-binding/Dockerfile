FROM sha256:fc2b486e0644fe17ad2dc4baf9d3098051ff8a6a5ded9e5db90b5d56b78ecf5f
USER root
RUN rm -rf /usr/local/lib/python3.12/site-packages/icarus_memory
COPY sidecar/icarus_memory /usr/local/lib/python3.12/site-packages/icarus_memory
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.e326f81
LABEL org.opencontainers.image.revision=e326f8113eae2e6e8123c7a39417fddf1e9fbebc
USER kingfisher
