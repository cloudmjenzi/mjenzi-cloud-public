<?php
// Copy to api/config.php on the server and edit. config.php is never committed.
return [
    'mail_to'     => 'cloudmjenzi@gmail.com',
    // Must be an address on this hosting account's domain so Gmail accepts it
    'mail_from'   => 'website@mjenzi.cloud',
    // Long random string for downloading leads from /api/leads.csv
    'admin_token' => 'CHANGE-ME',
    // Database lives outside public_html by default (~/mjenzi-data/leads.sqlite3)
    // 'db_path'  => '/home/USERNAME/mjenzi-data/leads.sqlite3',
];
