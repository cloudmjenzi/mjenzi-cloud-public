<?php
// GET /api/leads.csv  with header  Authorization: Bearer <admin_token>
// Downloads every lead as a spreadsheet.

declare(strict_types=1);
require __DIR__ . '/lib.php';

$cfg = mj_config();
$auth = $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '';
if ($cfg['admin_token'] === '' || !hash_equals('Bearer ' . $cfg['admin_token'], $auth)) {
    mj_json(401, ['error' => 'Unauthorised']);
}

$rows = mj_db($cfg)->query('SELECT id,received,type,reference,name,email,phone,company,topic,message,summary,emailed
                            FROM leads ORDER BY id DESC')->fetchAll(PDO::FETCH_NUM);
header('Content-Type: text/csv; charset=utf-8');
header('Content-Disposition: attachment; filename="mjenzi-leads.csv"');
header('Cache-Control: no-store');
$out = fopen('php://output', 'w');
fputcsv($out, ['id', 'received', 'type', 'reference', 'name', 'email', 'phone', 'company', 'topic', 'message', 'summary', 'emailed']);
foreach ($rows as $r) {
    // neutralise spreadsheet formulas in visitor-supplied text
    fputcsv($out, array_map(fn($c) => (is_string($c) && $c !== '' && strpbrk($c[0], '=+-@') !== false) ? "'" . $c : $c, $r));
}
