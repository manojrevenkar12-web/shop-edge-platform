# 0004. Scale on renders per pod, raise the floor before campaigns

## Status

Accepted.

## Context

- **CPU is a slow signal.** CPU utilisation lags load by minutes on PHP-FPM, because the pool queues before the CPU
  saturates.
- **Floors get padded.** Teams that scale on CPU keep a high floor so a spike does not land on too few pods, and that
  floor is paid for all night.
- **A purge raises origin load.** After a purge the cache-miss rate jumps, and so does origin load, even when visitor
  traffic does not.

## Decision

- **Scale on uncached renders.** KEDA scales on uncached renders per second per pod, from Prometheus, against a
  target below a pod's capacity (5.5 of about 7.5).
- **Raise the floor ahead of campaigns.** Known campaigns (the Black Friday launch, evening peaks) are cron triggers
  that lift the floor ahead of time, from `config/platform.yaml`.
- **Scale down slowly.** Scale-down has a 10-minute stabilisation window.

## Consequences

- **The calendar has to be kept current.** A campaign nobody added to the calendar gets only reactive scaling.
- **Measured trade-offs.** The ablations `platform_cpu_scaling` and `platform_no_prescale` show the cost and the
  errors of each choice.
