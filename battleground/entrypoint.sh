#!/bin/bash
set -e

# Start MySQL
service mysql start
chmod 755 /run/mysqld

# Re-apply webapp_user password with native auth (survives image layer changes)
mysql -u root -e "ALTER USER 'webapp_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'webapppass'; FLUSH PRIVILEGES;" 2>/dev/null || true

# Start Apache
service apache2 start

# Start cron
service cron start

# Run SSH in foreground
exec /usr/sbin/sshd -D
