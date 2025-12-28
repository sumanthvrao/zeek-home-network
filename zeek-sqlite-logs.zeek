# save as zeek-sqlite-logs.zeek or add to local.zeek

event zeek_init()
    {
    local f_conn: Log::Filter = [
        $name="sqlite_conn",
        $writer=Log::WRITER_SQLITE,
        $path="/opt/zeek/logs/zeek-logs.sqlite",
        $config=table(["tablename"] = "conn"])
    ];
    Log::add_filter(Conn::LOG, f_conn);
    }
