# 0002. No quotes in the ban header

## Status

Accepted.

## Context

The first version of `Ban.header` wrapped the regex in quotes, as a ban typed in `varnishadm` would. In VCL,
`ban("obj.http.X-Cache-Tags ~ " + req.http.X-Ban-Tags)` builds the ban expression from the header's raw text. The
quotes therefore became part of the regex, and no page ever matched. Every unit test passed. Only the test against a
real `varnishd` showed that a purged page was still served.

## Decision

- **No quotes.** The header carries the bare regex `(^|,)(p-1|p-2)(,|$)`.
- **A real-Varnish test.** `tests/test_vcl.py` runs the real VCL in `varnishd` in CI and checks three things:
  - a purged page is fetched again;
  - an unrelated page is not;
  - a `BAN` without the `X-Ban-Tags` or `X-Ban-All` header is refused.

## Consequences

- **The tag alphabet is restricted.** Tags must not contain regex metacharacters. They are `[a-z]-[0-9]+` by
  construction, and the planner rejects anything else.
- **VCL changes need the live test.** A unit test can't catch this kind of mistake.
