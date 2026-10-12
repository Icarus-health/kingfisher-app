FROM sha256:a8d2d89e6c47c5050b779dbc0e595cb187efd9650142416cdb557dfdf8b6cfe9
USER root
RUN rm -rf /usr/local/lib/python3.12/site-packages/icarus_memory /opt/kingfisher/ui
COPY sidecar/icarus_memory /usr/local/lib/python3.12/site-packages/icarus_memory
COPY ui /opt/kingfisher/ui
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.9544bc4
LABEL org.opencontainers.image.revision=9544bc491c42ef2417870df362c738204166310a
USER kingfisher
