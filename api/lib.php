<?php
// Mjenzi Cloud form backend for shared hosting (PHP 7.4+, PDO SQLite, mail()).
// Shared helpers for submit.php and leads.php.

declare(strict_types=1);

function mj_config(): array {
    $defaults = [
        'mail_to'      => 'cloudmjenzi@gmail.com',
        'mail_from'    => 'website@mjenzi.cloud',
        // Keep the database OUTSIDE public_html. Default: ~/mjenzi-data/leads.sqlite3
        'db_path'      => dirname(__DIR__, 2) . '/mjenzi-data/leads.sqlite3',
        'admin_token'  => '',
        'allowed_origins' => [],
        'rate_limit'   => 8,      // submissions ...
        'rate_window'  => 900,    // ... per 15 minutes per IP
    ];
    $file = __DIR__ . '/config.php';
    $cfg = is_file($file) ? (array) require $file : [];
    return array_merge($defaults, $cfg);
}

function mj_db(array $cfg): PDO {
    $dir = dirname($cfg['db_path']);
    if (!is_dir($dir)) {
        mkdir($dir, 0750, true);
    }
    $pdo = new PDO('sqlite:' . $cfg['db_path'], null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $pdo->exec('PRAGMA busy_timeout = 5000');
    $pdo->exec('CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        received TEXT NOT NULL, type TEXT NOT NULL, reference TEXT,
        name TEXT, email TEXT, phone TEXT, company TEXT, topic TEXT,
        message TEXT, summary TEXT, data TEXT, ip TEXT, emailed INTEGER DEFAULT 0)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS hits (ip TEXT NOT NULL, t INTEGER NOT NULL)');
    return $pdo;
}

function mj_json(int $status, array $body): void {
    http_response_code($status);
    header('Content-Type: application/json');
    header('Cache-Control: no-store');
    echo json_encode($body);
    exit;
}

function mj_cors(array $cfg): void {
    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    if ($origin !== '' && in_array($origin, $cfg['allowed_origins'], true)) {
        header('Access-Control-Allow-Origin: ' . $origin);
        header('Vary: Origin');
        header('Access-Control-Allow-Methods: POST, OPTIONS');
        header('Access-Control-Allow-Headers: Content-Type');
    }
}

function mj_clean($v, int $max): string {
    if (is_array($v) || is_object($v)) {
        return '';
    }
    $s = preg_replace('/[\x00-\x08\x0b\x0c\x0e-\x1f]/u', '', (string) ($v ?? '')) ?? '';
    return mb_substr(trim($s), 0, $max);
}

function mj_header_safe(string $s): string {
    return trim(str_replace(["\r", "\n"], ' ', $s));
}
