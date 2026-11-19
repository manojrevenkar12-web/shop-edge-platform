# 0001. Tag bans and long TTLs, not short TTLs or flushes

## Status

Accepted.

## Context

A catalogue page has to show the current price and stock. Shops usually get there in one of three ways:

- **A short TTL.** Pages expire every few minutes.
- **A flush on every release.**
- **Broad bans.** A price change bans its whole category.

A short TTL still shows stale prices between expiries, and it renders the shop far more often. Flushes and broad bans
throw away most of the cache in one go, and the origin then takes the full traffic.

## Decision

- **Tags.** Pages carry `X-Cache-Tags`: `p-<id>` for each product shown, and `l-<id>` for listing pages that show
  the product.
- **Bans.** A price or stock change bans exactly the pages that show that product, in every country shop.
- **Batching.** Changes are batched into one regex ban each flush interval.
- **TTL.** Tagged pages live 24 hours, because the bans keep them right.
- **Releases** do not touch the cache.

## Consequences

- **Correct tags are required.** A template that forgets a tag shows stale prices until the TTL ends. The integration
  test renders tags through the real VCL.
- **Bans accumulate.** The ban list grows during a mass reprice. Batching keeps it to one ban per interval, and the
  ban lurker cleans up behind.
- **The ablations measure each choice:** `short_ttl`, `platform_broad_bans` and `platform_flush_on_deploy`.
