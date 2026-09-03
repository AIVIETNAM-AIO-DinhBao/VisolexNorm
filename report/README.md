# Report artifacts

- `main.tex` is the current report source, including the controlled factorial and C-max20 closure.
- `main.pdf` is retained as the historical `v1.0.0` release PDF referenced by the immutable
  release manifest.
- `training-closure.pdf` is the rebuilt closure PDF produced from the current `main.tex`.

The current report source is verified and built separately so that updating research discussion
does not mutate the historical `v1.0.0` release manifest. See `release/TRAINING_CLOSURE.md` for
the app and research artifact boundary.