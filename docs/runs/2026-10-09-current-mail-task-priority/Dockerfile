FROM sha256:4b50fb4a18b36f86c2d60de5d7eb9952a580f02baf9c67cc67791e7d935f4f62
USER root
RUN rm -rf /usr/local/lib/python3.12/site-packages/icarus_memory
COPY sidecar/icarus_memory /usr/local/lib/python3.12/site-packages/icarus_memory
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.1913e26
LABEL org.opencontainers.image.revision=1913e265744344de91b123ab1dc6e58dbd4b9ca3
USER kingfisher
