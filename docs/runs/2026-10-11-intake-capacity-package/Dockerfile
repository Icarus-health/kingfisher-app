FROM sha256:a8c96f76d9c5c67de4aff2ffebcd1590f95d70547cfca5760c142cd42909c45a
USER root
RUN rm -rf /opt/kingfisher/ui
COPY sidecar/icarus_memory/hintergrund.py /usr/local/lib/python3.12/site-packages/icarus_memory/hintergrund.py
COPY sidecar/icarus_memory/mail_intake.py /usr/local/lib/python3.12/site-packages/icarus_memory/mail_intake.py
COPY sidecar/icarus_memory/mail_intake_routes.py /usr/local/lib/python3.12/site-packages/icarus_memory/mail_intake_routes.py
COPY sidecar/icarus_memory/mail_stand.py /usr/local/lib/python3.12/site-packages/icarus_memory/mail_stand.py
COPY sidecar/icarus_memory/scheduler.py /usr/local/lib/python3.12/site-packages/icarus_memory/scheduler.py
COPY sidecar/icarus_memory/server.py /usr/local/lib/python3.12/site-packages/icarus_memory/server.py
COPY sidecar/icarus_memory/storage_capacity.py /usr/local/lib/python3.12/site-packages/icarus_memory/storage_capacity.py
COPY app/dist /opt/kingfisher/ui
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.3690733
LABEL org.opencontainers.image.revision=36907338bde9251b4f92081913327ac0d63e463c
USER kingfisher
