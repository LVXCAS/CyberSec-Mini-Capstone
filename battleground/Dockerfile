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
    ufw \
    hydra \
    nmap \
    php-cli \
    && rm -rf /var/lib/apt/lists/*

# Weak users for red team brute-force targets
RUN useradd -m -s /bin/bash testuser && echo 'testuser:password123' | chpasswd
RUN useradd -m -s /bin/bash sysop && echo 'sysop:admin123' | chpasswd

# SUID binary for privilege escalation
RUN cp /usr/bin/find /usr/local/bin/find-vuln && chmod u+s /usr/local/bin/find-vuln

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
