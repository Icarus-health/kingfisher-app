FROM sha256:e2caaa4f7d2d466cb5dac00db3dab3eeab3a3a6e39b30cc33115a81079aaafb1
USER root
RUN rm -rf /opt/kingfisher/ui /usr/local/lib/python3.12/site-packages/icarus_memory
COPY sidecar/icarus_memory/ /usr/local/lib/python3.12/site-packages/icarus_memory/
COPY app/dist/ /opt/kingfisher/ui/
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.a5787c8
LABEL org.opencontainers.image.revision=a5787c88914400151769dae714dfd74c9ea8a0c3
USER kingfisher
