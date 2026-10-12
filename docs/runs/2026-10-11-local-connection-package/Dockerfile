FROM sha256:a3f6dc20a9b9115c0479b11fc174d4eb19ff80ab79320237efc8c99c7761d812
USER root
RUN rm -rf /opt/kingfisher/ui
COPY sidecar/icarus_memory/model_roles_routes.py /usr/local/lib/python3.12/site-packages/icarus_memory/model_roles_routes.py
COPY sidecar/icarus_memory/server.py /usr/local/lib/python3.12/site-packages/icarus_memory/server.py
COPY app/dist /opt/kingfisher/ui
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.bc21155
LABEL org.opencontainers.image.revision=bc211551dc46a8a9b55efb0e120d08779ec4c20f
USER kingfisher
