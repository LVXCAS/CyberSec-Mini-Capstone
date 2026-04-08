#!/bin/bash
set -e

# Create users with weak but non-trivial passwords
id admin &>/dev/null || useradd -m -s /bin/bash admin
id webdev &>/dev/null || useradd -m -s /bin/bash webdev
id dbadmin &>/dev/null || useradd -m -s /bin/bash dbadmin
id backup &>/dev/null || useradd -m -s /bin/bash backup

chpasswd <<'PASSWORDS'
admin:Pr0jectAdmin1
webdev:WebDev2024
dbadmin:DbPass99
backup:B4ckup_usr
PASSWORDS

usermod -aG sudo admin

# Create database and seed data (MySQL already started by Dockerfile RUN)
mysql -u root <<'SQL'
CREATE DATABASE IF NOT EXISTS webapp;
USE webapp;
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    password VARCHAR(128) NOT NULL,
    email VARCHAR(128),
    role VARCHAR(32) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO users (username, password, email, role) VALUES
    ('admin', 'admin123', 'admin@corp.local', 'admin'),
    ('jsmith', 'password1', 'jsmith@corp.local', 'user'),
    ('mjones', 'Welcome1!', 'mjones@corp.local', 'user'),
    ('dba_service', 'r00tdb!!', 'dba@corp.local', 'admin');

CREATE USER IF NOT EXISTS 'webapp_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'webapppass';
GRANT SELECT, INSERT, UPDATE ON webapp.* TO 'webapp_user'@'localhost';
FLUSH PRIVILEGES;
SQL

# Deploy vulnerable PHP web app
cat > /var/www/html/index.php <<'PHP'
<?php
$conn = new mysqli("localhost", "webapp_user", "webapppass", "webapp");
if ($conn->connect_error) die("Connection failed");

$message = "";
if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $user = $_POST["username"];
    $pass = $_POST["password"];
    // Intentionally vulnerable to SQL injection for training purposes
    $sql = "SELECT * FROM users WHERE username='$user' AND password='$pass'";
    $result = $conn->query($sql);
    if ($result && $result->num_rows > 0) {
        $message = "Login successful. Welcome, " . htmlspecialchars($user) . "!";
    } else {
        $message = "Invalid credentials.";
    }
}
?>
<!DOCTYPE html>
<html>
<head><title>Corp Portal</title></head>
<body>
<h1>Corporate Portal Login</h1>
<?php if ($message) echo "<p>$message</p>"; ?>
<form method="POST">
    <label>Username: <input name="username" type="text"></label><br>
    <label>Password: <input name="password" type="password"></label><br>
    <button type="submit">Login</button>
</form>
</body>
</html>
PHP

rm -f /var/www/html/index.html

# Cron jobs
echo "0 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1" | crontab -u backup -
cat > /usr/local/bin/backup.sh <<'SCRIPT'
#!/bin/bash
echo "[$(date)] Starting backup..."
mysqldump -u root webapp > /tmp/webapp_backup.sql
echo "[$(date)] Backup complete."
SCRIPT
chmod +x /usr/local/bin/backup.sh

(crontab -u root -l 2>/dev/null; echo "0 */6 * * * /usr/sbin/logrotate /etc/logrotate.conf") | crontab -u root -

# Seed log files
mkdir -p /var/log
cat > /var/log/auth.log <<'LOG'
Apr  7 03:14:22 battleground sshd[1001]: Failed password for admin from 192.168.1.50 port 44122 ssh2
Apr  7 03:14:25 battleground sshd[1001]: Accepted password for admin from 192.168.1.50 port 44122 ssh2
Apr  7 08:30:01 battleground sshd[1045]: Accepted password for webdev from 192.168.1.51 port 55201 ssh2
Apr  7 12:00:15 battleground sshd[1102]: Failed password for invalid user test from 10.0.0.5 port 33210 ssh2
Apr  7 12:00:18 battleground sshd[1102]: Failed password for invalid user root from 10.0.0.5 port 33212 ssh2
LOG

cat > /var/log/webapp.log <<'LOG'
[2026-04-07 09:15:00] INFO: User jsmith logged in from 192.168.1.51
[2026-04-07 09:20:33] WARNING: Failed login attempt for user admin from 10.0.0.5
[2026-04-07 09:20:35] WARNING: Failed login attempt for user admin from 10.0.0.5
[2026-04-07 10:00:00] INFO: User mjones logged in from 192.168.1.52
[2026-04-07 14:30:12] ERROR: Database query timeout on /api/reports
LOG

echo "Battleground setup complete."
