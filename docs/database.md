# Database Design

## experiments

| Field | Purpose |
|---|---|
| id | Primary key |
| name | Experiment name |
| description | Human-readable description |
| mode | adaptive/fixed/comparison |
| packet_count | Number of simulated packets |
| base_delay | Base RTT component |
| jitter | Random RTT variation |
| packet_loss | Loss percentage |
| status | Current experiment state |
| started_at | Start timestamp |
| completed_at | Completion timestamp |

## measurements

| Field | Purpose |
|---|---|
| id | Primary key |
| experiment_id | Parent experiment |
| sequence_number | Measurement sequence |
| rtt | Observed RTT |
| srtt | Smoothed RTT |
| rttvar | RTT variation |
| rto | Current retransmission timeout |
| was_retransmission | Whether event was a retransmission |
| timeout_occurred | Whether event was a timeout |
| timestamp | Measurement timestamp |

The relationship is one Experiment to many Measurements.
