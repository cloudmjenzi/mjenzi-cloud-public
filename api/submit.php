<?php
// POST /api/submit  (rewritten here by the site's .htaccess)
// Same JSON contract as api/form_server.py - see api/README.md.

declare(strict_types=1);
require __DIR__ . '/lib.php';

const TYPES = [
    'contact'    => 'Website enquiry',
    'assessment' => 'Cloud & AI assessment',
    'sizing'     => 'Server sizing quote request',
    'cloud'      => 'Cloud configuration pricing request',
    'partner'    => 'Partner program enquiry',
];

$cfg = mj_config();
mj_cors($cfg);
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($method === 'OPTIONS') {
    http_response_code(204);
    exit;
}
if ($method === 'GET' && isset($_GET['health'])) {
    try {
        mj_db($cfg);
        mj_json(200, ['ok' => true]);
    } catch (Throwable $e) {
        error_log('mjenzi health: ' . $e->getMessage());
        mj_json(500, ['ok' => false]);
    }
}
if ($method !== 'POST') {
    mj_json(405, ['error' => 'Method not allowed']);
}

$raw = file_get_contents('php://input', false, null, 0, 200001);
if ($raw === false || $raw === '' || strlen($raw) > 200000) {
    mj_json(400, ['error' => 'Invalid request']);
}
$d = json_decode($raw, true);
if (!is_array($d) || array_is_list_compat($d)) {
    mj_json(400, ['error' => 'Invalid request']);
}

// Honeypot: bots fill the hidden "website" field. Pretend success, keep nothing.
if (mj_clean($d['website'] ?? '', 200) !== '') {
    mj_json(200, ['ok' => true]);
}

$type = mj_clean($d['type'] ?? '', 20);
if (!isset(TYPES[$type])) {
    mj_json(400, ['error' => 'Unknown form type']);
}
$ip = $_SERVER['REMOTE_ADDR'] ?? '';
$data = (isset($d['data']) && is_array($d['data'])) ? $d['data'] : null;
$e = [
    'received'  => gmdate('Y-m-d\TH:i:s+00:00'),
    'type'      => $type,
    'reference' => mj_clean($d['reference'] ?? '', 40),
    'name'      => mj_clean($d['name'] ?? '', 200),
    'email'     => mj_clean($d['email'] ?? '', 200),
    'phone'     => mj_clean($d['phone'] ?? '', 50),
    'company'   => mj_clean($d['company'] ?? '', 200),
    'topic'     => mj_clean($d['topic'] ?? '', 120),
    'message'   => mj_clean($d['message'] ?? '', 5000),
    'summary'   => mj_clean($d['summary'] ?? '', 20000),
    'ip'        => $ip,
];
if ($e['name'] === '' || !preg_match('/^[^@\s]+@[^@\s]+\.[^@\s]+$/', $e['email'])) {
    mj_json(400, ['error' => 'Please give your name and a valid email address.']);
}
if ($type === 'contact' && $e['message'] === '') {
    mj_json(400, ['error' => 'Please write a message.']);
}

try {
    $db = mj_db($cfg);

    // Rate limit per IP
    $now = time();
    $db->prepare('DELETE FROM hits WHERE t < ?')->execute([$now - $cfg['rate_window']]);
    $q = $db->prepare('SELECT COUNT(*) FROM hits WHERE ip = ?');
    $q->execute([$ip]);
    if ((int) $q->fetchColumn() >= $cfg['rate_limit']) {
        mj_json(429, ['error' => 'Too many submissions. Please try again in a few minutes.']);
    }
    $db->prepare('INSERT INTO hits (ip, t) VALUES (?, ?)')->execute([$ip, $now]);

    $db->prepare('INSERT INTO leads (received,type,reference,name,email,phone,company,topic,message,summary,data,ip)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?)')
       ->execute([$e['received'], $type, $e['reference'], $e['name'], $e['email'], $e['phone'], $e['company'],
                  $e['topic'], $e['message'], $e['summary'],
                  $data === null ? null : json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), $ip]);
    $id = (int) $db->lastInsertId();
} catch (Throwable $ex) {
    error_log('mjenzi save failed: ' . $ex->getMessage());
    mj_json(500, ['error' => "Sorry, we couldn't save that. Please email kinyua@mjenzi.cloud."]);
}

// Email (lead is already saved, so a mail failure is only logged)
try {
    if (mj_send_mail($cfg, $id, $e, $data)) {
        $db->prepare('UPDATE leads SET emailed = 1 WHERE id = ?')->execute([$id]);
    } else {
        error_log("mjenzi lead #$id saved but mail() failed");
    }
} catch (Throwable $ex) {
    error_log("mjenzi lead #$id mail error: " . $ex->getMessage());
}

mj_json(200, ['ok' => true, 'id' => $id]);


function mj_send_mail(array $cfg, int $id, array $e, ?array $data): bool {
    $label = TYPES[$e['type']];
    $subject = $label . ($e['reference'] ? ' ' . $e['reference'] : '') . ': ' . $e['name']
             . ($e['company'] ? ' (' . $e['company'] . ')' : '');
    $lines = [
        "New " . strtolower($label) . " from mjenzi.cloud (lead #$id)", '',
        'Name:     ' . $e['name'],
        'Email:    ' . $e['email'],
        'Phone:    ' . ($e['phone'] ?: '-'),
        'Company:  ' . ($e['company'] ?: '-'),
    ];
    if ($e['topic'])     { $lines[] = 'Topic:    ' . $e['topic']; }
    if ($e['reference']) { $lines[] = 'Ref:      ' . $e['reference']; }
    $lines[] = 'Received: ' . $e['received'];
    if ($e['message'])   { array_push($lines, '', 'Message:', $e['message']); }
    if ($e['summary'])   { array_push($lines, '', str_repeat('-', 60), $e['summary']); }
    $text = implode("\r\n", $lines) . "\r\n";

    $from = mj_header_safe($cfg['mail_from']);
    $replyName = mj_header_safe($e['name']);
    $headers = [
        'From: =?UTF-8?B?' . base64_encode('Mjenzi Cloud website') . "?= <$from>",
        'Reply-To: =?UTF-8?B?' . base64_encode($replyName) . '?= <' . mj_header_safe($e['email']) . '>',
        'MIME-Version: 1.0',
    ];

    if ($data !== null) {
        $boundary = 'mj_' . bin2hex(random_bytes(12));
        $headers[] = "Content-Type: multipart/mixed; boundary=\"$boundary\"";
        $fname = preg_replace('/[^A-Za-z0-9_.-]/', '', $e['reference'] ?: "lead-$id") . '.json';
        $body = "--$boundary\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n"
              . chunk_split(base64_encode($text))
              . "--$boundary\r\nContent-Type: application/json; name=\"$fname\"\r\nContent-Transfer-Encoding: base64\r\n"
              . "Content-Disposition: attachment; filename=\"$fname\"\r\n\r\n"
              . chunk_split(base64_encode(json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)))
              . "--$boundary--\r\n";
    } else {
        $headers[] = 'Content-Type: text/plain; charset=UTF-8';
        $headers[] = 'Content-Transfer-Encoding: base64';
        $body = chunk_split(base64_encode($text));
    }

    $to = implode(', ', array_map('mj_header_safe', (array) $cfg['mail_to']));
    $encSubject = '=?UTF-8?B?' . base64_encode($subject) . '?=';
    return mail($to, $encSubject, $body, implode("\r\n", $headers), '-f' . $from);
}

function array_is_list_compat(array $a): bool {
    return $a === [] || array_keys($a) === range(0, count($a) - 1);
}
