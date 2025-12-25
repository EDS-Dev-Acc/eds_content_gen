# Observability Dashboards

Grafana dashboard configurations for EMCIP monitoring.

## Dashboards

| Dashboard | File | Description |
|-----------|------|-------------|
| Seeds Probe Health | `seeds_probe_health.json` | Monitor seed validation and test-crawl operations |
| Runs SLO | `runs_slo.json` | Track crawl run performance against SLO targets |
| Export Throughput | `export_throughput.json` | Monitor export job creation and completion rates |
| System Overview | `system_overview.json` | High-level operational metrics |

## Installation

### Grafana Import

1. Open Grafana → Dashboards → Import
2. Upload JSON file or paste contents
3. Select Prometheus data source
4. Save dashboard

### Provisioning (Production)

Add to `/etc/grafana/provisioning/dashboards/emcip.yaml`:

```yaml
apiVersion: 1

providers:
  - name: 'EMCIP Dashboards'
    orgId: 1
    folder: 'EMCIP'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards/emcip
```

Copy JSON files to `/var/lib/grafana/dashboards/emcip/`.

## Prometheus Data Source

These dashboards expect a Prometheus data source named `Prometheus`.

### Required Metrics

The application exposes these metrics at `/metrics`:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | method, endpoint, status_class | HTTP request counts |
| `http_request_duration_seconds` | Histogram | method, endpoint | Request latency |
| `crawl_runs_total` | Counter | status | Completed crawl runs |
| `crawl_run_duration_seconds` | Histogram | - | Crawl run duration |
| `articles_collected_total` | Counter | source | Articles collected |
| `export_jobs_total` | Counter | status, format | Export job counts |
| `seeds_validated_total` | Counter | result | Seed validation results |
| `celery_tasks_total` | Counter | task, status | Celery task counts |

## Alerting

See [runbooks](../runbooks/) for alert handling procedures.

### Recommended Alerts

1. **High Error Rate**: `rate(http_requests_total{status_class="5xx"}[5m]) > 0.1`
2. **Slow API Responses**: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2`
3. **Stuck Runs**: `increase(crawl_runs_total{status="completed"}[1h]) == 0`
4. **Export Failures**: `rate(export_jobs_total{status="failed"}[1h]) > 0`
