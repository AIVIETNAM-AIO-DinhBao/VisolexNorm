# Training closure

`training-closed-v2` closes the research-training phase without changing the historical
`v1.0.0` application release.

| Artifact ID | Role |
|---|---|
| APP-DEFAULT | Model C application checkpoint |
| APP-FALLBACK | Model B verified rollback checkpoint |
| APP-SELECTION | Existing Dev-only application selection |
| FCT-PROTOCOL | Three-seed controlled factorial protocol |
| FCT-SUMMARY | Factorial result summary |
| FCT-CONCLUSION | Frozen factorial conclusion |
| FCT-ARCHIVE | Local/external factorial handoff archive |
| OPT-CMAX20 | Local/external exploratory C-max20 archive |

The application remains Model C with Model B as fallback. FCT-CONCLUSION establishes L8 as the
strongest factorial configuration under the frozen Dev-loss checkpoint-selection protocol.
OPT-CMAX20 is exploratory, is not promotion eligible, and cannot revise FCT-CONCLUSION.

Run `python -m scripts.verify_training_closure` after restoring APP-DEFAULT, APP-FALLBACK, and
the local handoff archives. The closure manifest stores SHA-256 values as four segments; the
verifier joins and checks them without rendering raw full digests in this document.