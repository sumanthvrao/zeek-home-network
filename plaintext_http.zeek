module PlaintextHTTP;

event http_request(c: connection, method: string, original_URI: string) {
    if ( c$id$resp_p == 80/tcp ) {
        NOTICE([$note=Notice::Info,
                $msg=fmt("Plaintext HTTP request: %s %s", method, original_URI),
                $conn=c]);
    }
}
