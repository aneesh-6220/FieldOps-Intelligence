# Analytics definitions

Phase 1 analytics use persisted lead and job facts only. Unknown actual values are excluded rather than treated as zero. A rate with no denominator is unavailable (`None`) in calculation code and displayed as an empty-state value in the UI. Segment rows below the configurable sample threshold are labelled low sample.

| Metric | Definition | Important edge case |
|---|---|---|
| Active leads | Leads not converted or lost | Includes new through follow-up states |
| Qualified leads | Current status is qualified | Not a historical stage count |
| Lead conversion | Converted leads ÷ all leads | No leads means unavailable |
| Average lead age | Calendar days since creation for open leads | Future timestamps clamp to zero |
| Overdue follow-ups | Open leads with follow-up before today | Terminal leads excluded |
| Average conversion time | Converted timestamp minus lead creation | Missing timestamps excluded |
| Completion rate | Completed jobs ÷ all jobs | Cancelled jobs remain in denominator |
| Cancellation rate | Cancelled jobs ÷ all jobs | No jobs means unavailable |
| Average/median job value | Mean/median known final revenue | Missing final revenue excluded |
| Quoted revenue | Sum quoted revenue for non-cancelled jobs | A quote is not realized revenue |
| Realized revenue | Completed-job final revenue where known | Missing final revenue is also flagged |
| Outstanding quoted revenue | Quotes for non-terminal jobs | Operational pipeline value only |
| Average duration | Mean actual end minus actual start | Missing/invalid intervals excluded |
| Duration variance | Actual duration ÷ scheduled duration − 1 | Nonpositive scheduled duration excluded |
| Cost variance | Actual cost ÷ estimated cost − 1 | Missing or nonpositive estimate excluded |
| Repeat-customer revenue | Realized revenue from customers with 2+ revenue-bearing jobs | Historical, not predicted lifetime value |
| Customer concentration | Largest customer's realized revenue ÷ total realized revenue | Requires positive realized revenue |
| Jobs per worker | Assignment count | Team jobs count for every assigned worker |
| Worker hours | Actual hours, falling back to expected hours | A utilization proxy, not payroll time |

Revenue charts group completed final revenue by completion month, service, or customer. Lead conversion tables group current status by source or service and show the low-sample marker where appropriate.

## Deterministic insight rules

| Rule | Trigger |
|---|---|
| Overdue follow-up | Open lead follow-up is before today |
| Qualified not converted | Lead remains qualified |
| Staffing gap | Upcoming scheduled/confirmed work has no worker |
| Schedule conflict | One worker has overlapping job intervals |
| Past incomplete | Scheduled end is past and job is not terminal |
| Missing final revenue | Completed job has no final revenue |
| Cost overrun | Known actual cost exceeds estimate by the configured ratio |
| Duration overrun | Known actual duration exceeds schedule by the configured ratio |
| Customer concentration | Largest customer exceeds configured realized-revenue share |

Each finding includes severity, the measured evidence, and a concrete next action. These are reproducible operating rules, not forecasts, anomaly models, or artificial intelligence claims.

## Known analytical limits

Current-state lead statuses do not reconstruct every stage ever reached. Assignment hours do not represent total worker capacity. Revenue is recognized operationally at job completion, not according to accounting standards. Weather, travel, quality, customer satisfaction, cash collection, and external demand are outside Phase 1.
