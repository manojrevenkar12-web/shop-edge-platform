# Runbook: availability budget burning

The alert pages when 5xx page views burn the 99.9% budget 14.4 times too fast over an hour (and still over the
last 5 minutes), or 6 times too fast over 6 hours (and the last 30 minutes).

1. **Look at what changed.** Was there a release in the last hour (Jenkins, `kubectl argo rollouts history shop-php
   -n shop`)? If one is live and the 5xx started with it, abort it: `kubectl argo rollouts undo shop-php -n shop`.
2. **Check the origin.**
   - `sum(rate(shop_renders_total[1m]))` against `kube_deployment_status_replicas_available`: are renders above
     what the pods can take?
   - Are pods starting? Raise the floor through the ScaledObject's `minReplicaCount` if a known peak is under way.
3. **Check the cache.**
   - Varnish hit ratio: `varnish_main_cache_hit / (varnish_main_cache_hit + varnish_main_cache_miss)`.
   - A sudden drop means a mass ban or a flush. `varnishadm ban.list` shows recent bans.
4. **Dependencies.** Database failover and slow search show up as rising render time with flat traffic. Grace keeps
   serving cached pages for 6 hours; pages that were never cached will fail until the dependency recovers.
