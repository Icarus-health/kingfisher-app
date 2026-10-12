FROM sha256:24a5528456eff9474d1aa7b6f9f7e710491e6a6a0323829c2cd00e177387d3cf
USER root
RUN rm -rf /opt/kingfisher/ui /usr/local/lib/python3.12/site-packages/icarus_memory
COPY sidecar/icarus_memory/ /usr/local/lib/python3.12/site-packages/icarus_memory/
COPY app/dist/ /opt/kingfisher/ui/
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.f858681
LABEL org.opencontainers.image.revision=f858681bb5afa0d7fe0482f87ce208c10793c38f
USER kingfisher
