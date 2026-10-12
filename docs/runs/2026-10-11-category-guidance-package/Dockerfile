FROM sha256:066cf82ddc4a8217b9d8c4f660f84cdacf0ca9315da287cb9384710bfaccd458
USER root
COPY sidecar/icarus_memory/memory_categories.py /usr/local/lib/python3.12/site-packages/icarus_memory/memory_categories.py
COPY VERSION /opt/kingfisher/VERSION
ENV KINGFISHER_FASSUNG=1.0.6-preview.2d6467b
LABEL org.opencontainers.image.revision=2d6467b888fc150eb2f118e272ba8ac2f2bfbeda
USER kingfisher
