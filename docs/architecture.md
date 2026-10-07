# RTTune Architecture

```text
+---------------------------+
| React + TypeScript UI     |
| Dashboard / Charts / CSV  |
+-------------+-------------+
              |
              | HTTP/JSON
              v
+---------------------------+
| FastAPI REST API          |
| Validation / CRUD / Sim   |
+-------------+-------------+
              |
       +------+------+
       |             |
       v             v
+-------------+  +----------------+
| RTO Engine  |  | SQLite DB      |
| SRTT        |  | Experiments    |
| RTTVAR      |  | Measurements   |
| RTO         |  | History        |
+-------------+  +----------------+
```

The browser is responsible for presentation and user interaction. FastAPI handles
validation, simulation, persistence and orchestration. The RTO engine contains the
network-timing calculation logic. SQLite provides persistent experiment history.
