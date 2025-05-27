FROM ubuntu:22.04
ENV DEBIAN_FRONTEND noninteractive

# Build dependencies
RUN \
    apt-get update && \
    apt-get install -y wget git build-essential zlib1g-dev libnuma-dev libaio-dev

# Clone fio
WORKDIR /home
RUN git clone --branch master https://github.com/axboe/fio.git fio && \
    cd fio && \
    git checkout bcd46be2adaa4afc32b836ad6137798544a3d80

# Build fio
WORKDIR /home/fio
RUN \
    ./configure && \
   make -j

# Expose fio
VOLUME /var/lib/fio
ENTRYPOINT ["/home/fio/fio"]
