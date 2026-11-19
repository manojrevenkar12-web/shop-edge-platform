vcl 4.1;
# Full-page cache in front of the shop. Tag bans from the purge planner (sep/edge/purge.py), grace while the origin
# is slow or down, marketing parameters and analytics cookies stripped before the cache key is built.
# The parameter and cookie lists match sep/edge/keys.py; tests/test_vcl.py runs this file in a real varnishd.

import std;

backend shop {
    .host = "${ORIGIN_HOST}";
    .port = "${ORIGIN_PORT}";
    .first_byte_timeout = 30s;
    .probe = {
        .url = "/health";
        .interval = 5s;
        .timeout = 2s;
        .window = 5;
        .threshold = 3;
        .initial = 3;
    }
}

acl purgers {
    "127.0.0.1";
    "10.0.0.0"/8;
}

sub vcl_recv {
    if (req.method == "BAN") {
        if (client.ip !~ purgers) {
            return (synth(405, "Not allowed"));
        }
        if (req.http.X-Ban-Tags) {
            # one regex per batch, e.g. (^|,)(p-12|l-12)(,|$)
            ban("obj.http.X-Cache-Tags ~ " + req.http.X-Ban-Tags);
            return (synth(200, "Banned"));
        }
        if (req.http.X-Ban-All == "yes") {
            ban("obj.status != 0");
            return (synth(200, "Banned all"));
        }
        return (synth(400, "X-Ban-Tags missing"));
    }

    if (req.method != "GET" && req.method != "HEAD") {
        return (pass);
    }

    # marketing parameters: one ad click must not become one cache key
    if (req.url ~ "(\?|&)(utm_[a-z]+|gclid|gbraid|wbraid|fbclid|msclkid|dclid|mc_cid|mc_eid|_ga|_gl|yclid|ttclid)=") {
        set req.url = regsuball(req.url, "(utm_[a-z]+|gclid|gbraid|wbraid|fbclid|msclkid|dclid|mc_cid|mc_eid|_ga|_gl|yclid|ttclid)=[^&]*&?", "");
        set req.url = regsub(req.url, "[?&]+$", "");
    }
    set req.url = std.querysort(req.url);

    # analytics and consent cookies never change the page
    if (req.http.Cookie) {
        set req.http.Cookie = regsuball(req.http.Cookie, "(^|;\s*)(_ga[^=]*|_gid|_gat[^=]*|_fbp|_fbc|_gcl_[^=]*|_uet[^=]*|_clck|_clsk|OptanonConsent|OptanonAlertBoxClosed|_hj[^=]*|cookie_consent)=[^;]*", "");
        set req.http.Cookie = regsub(req.http.Cookie, "^;\s*", "");
        if (req.http.Cookie ~ "^\s*$") {
            unset req.http.Cookie;
        }
    }
    if (req.http.Cookie ~ "(PHPSESSID|frontend|private_content_version|cart_id|customer_token)=") {
        return (pass);
    }
    unset req.http.Cookie;
    return (hash);
}

sub vcl_backend_response {
    # keep pages long and serve them stale while the shop is slow or down; purges keep prices right
    set beresp.grace = 6h;
    if (beresp.status >= 500) {
        set beresp.ttl = 0s;
        set beresp.uncacheable = true;
        return (deliver);
    }
    if (beresp.http.Cache-Control ~ "private|no-store") {
        set beresp.uncacheable = true;
        set beresp.ttl = 120s;
        return (deliver);
    }
    if (!beresp.http.X-Cache-Tags) {
        set beresp.ttl = 300s;
    } else {
        set beresp.ttl = 24h;
    }
    unset beresp.http.Set-Cookie;
    return (deliver);
}

sub vcl_backend_error {
    # the origin failed and no stale copy was usable: say so plainly
    set beresp.http.Retry-After = "5";
}

sub vcl_deliver {
    if (obj.hits > 0) {
        set resp.http.X-Cache = "HIT";
    } else {
        set resp.http.X-Cache = "MISS";
    }
    unset resp.http.X-Cache-Tags;
}
