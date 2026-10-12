FROM sha256:f9caa5537b33403f0d7beff828a20fecd4ee3458d9ac41068e40d1cf1b436a6e
USER root
RUN rm -rf /usr/local/lib/python3.12/site-packages/icarus_memory /opt/kingfisher/ui
COPY sidecar/icarus_memory /usr/local/lib/python3.12/site-packages/icarus_memory
COPY app/dist /opt/kingfisher/ui
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.6979131
LABEL org.opencontainers.image.revision=69791314c69c0092cd81e69952c2d0a1fdb21985
USER kingfisher
