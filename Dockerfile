FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash procps util-linux coreutils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash lab \
    && mkdir /work \
    && chown lab:lab /work

COPY printer.py /opt/printer.py
COPY lab.py /opt/lab.py
COPY shell.bashrc /home/lab/.bashrc
RUN chmod 755 /opt/printer.py \
    && ln -s /opt/printer.py /usr/local/bin/printer
USER lab
WORKDIR /work
CMD ["python", "/opt/lab.py"]
