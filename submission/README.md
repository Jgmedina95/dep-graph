# Submission Artifacts

This folder contains the cleaner final graph outputs for the take-home.

Files:

- `graphs/googlesuper_relationship_graph_clean.html`: cleaner Google Super dependency graph
- `graphs/github_relationship_graph_clean.html`: cleaner GitHub dependency graph

Notes:

- These are filtered versions of the larger exploratory graphs.
- I used a higher confidence threshold, capped the rendered edge count, and removed user-seed nodes to reduce clutter for review.
- The raw and intermediate outputs used to generate these graphs were moved into `artifacts/` to keep the project root cleaner.