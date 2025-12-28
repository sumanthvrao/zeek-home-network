module NewDevices;

export {
    global known_devices: set[string] = set();
}

event zeek_init() {
    print "NewDevices: initialized";
}

event new_connection(c: connection) {
    local key = fmt("%s-%s", c$id$orig_h, c$id$orig_p);
    if ( ! key in known_devices ) {
        known_devices += key;
        NOTICE([$note=Notice::Info,
                $msg=fmt("New device seen: %s", key),
                $conn=c]);
    }
}
