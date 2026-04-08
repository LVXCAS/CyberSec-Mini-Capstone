FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    apache2 \
    libapache2-mod-php \
    php-mysql \
    mysql-server \
    cron \
    sudo \
    net-tools \
    curl \
    vim \
    python3 \
    logrotate \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /run/sshd /run/mysqld && \
    chown mysql:mysql /run/mysqld

COPY sshd_config /etc/ssh/sshd_config
COPY setup.sh /usr/local/bin/setup.sh
RUN chmod +x /usr/local/bin/setup.sh

# Run setup (starts mysql temporarily for seeding)
RUN service mysql start && /usr/local/bin/setup.sh && service mysql stop

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 22 80

CMD ["/usr/local/bin/entrypoint.sh"]
