FROM sha256:d65a5a4b205496e222ffab16b1137b9734718e46837a0b848c12819bc2a4de3f
USER root
RUN rm -rf /opt/kingfisher/ui
COPY app/dist/ /opt/kingfisher/ui/
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.d092006
LABEL org.opencontainers.image.revision=d092006699bdfe89b390916ede8505bc7b3cac9f
USER kingfisher
