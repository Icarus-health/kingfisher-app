FROM sha256:a8d2d89e6c47c5050b779dbc0e595cb187efd9650142416cdb557dfdf8b6cfe9
USER root
RUN rm -rf /usr/local/lib/python3.12/site-packages/icarus_memory /opt/kingfisher/ui
COPY sidecar/icarus_memory /usr/local/lib/python3.12/site-packages/icarus_memory
COPY ui /opt/kingfisher/ui
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.83cfaa0
LABEL org.opencontainers.image.revision=83cfaa0664f73b0d95d2535c582427814f2d24ba
USER kingfisher
