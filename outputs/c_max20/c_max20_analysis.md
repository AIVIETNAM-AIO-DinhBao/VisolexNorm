# C-max20 exploratory analysis

**Artifact ID:** OPT-CMAX20. This is an exploratory optimization result, not an application
promotion candidate and not a revision of the frozen factorial conclusion.

The expanded-pool run used seed 2026, a maximum budget of 20 epochs, a minimum of 8 epochs,
Dev-loss patience 4, and minimum improvement 0.0001. It stopped at epoch 13 and selected epoch 9
by Dev loss.

| Checkpoint | ERR | F1 | Exact match |
|---|---:|---:|---:|
| Selected by Dev loss, epoch 9 | 0.668729 | 0.759552 | 0.560952 |
| Terminal at stop, epoch 13 | 0.669554 | 0.765908 | 0.567619 |

The selected checkpoint did not improve the frozen L8 selected-checkpoint reference. The terminal
checkpoint is retained only as sensitivity evidence because its selection criterion differs from
the frozen Dev-loss rule.