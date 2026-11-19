# Runbook: latency budget burning

The alert pages when more than 1% of page views take over 1.5 s, burning the budget 14.4 times too fast over an
hour, or 6 times too fast over 6 hours.

1. **A release.** A slow query from a release shows up as a higher mean render time on the new pods only. Compare
   `shop_render_seconds` by `rollouts_pod_template_hash`, and roll back if the new hash is slower.
2. **Saturation.** If the pods are above 90% busy, scale up and check why the hit ratio fell.
3. **Search.** If Elasticsearch latency is up, category pages degrade first. Grace serves them stale while search
   recovers.
