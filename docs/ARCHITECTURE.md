# Architecture

`retirement` coordinates input validation, a single working-tree inventory and a private report pair. `git_state` snapshots the selected index and HEAD tree, builds a sorted tracked-prefix index, and checks administrative boundaries. The inventory folds the logical sizes of safe entries bottom-up, stops project discovery at artifact boundaries and continues their protection checks. Project and dependency metadata is scoped to one invocation. Fast fingerprints encode relative path and metadata in deterministic traversal order. Explicit deep mode hashes observed, eligible files without another tree walk.

`retire_rules` applies scoped Node, Python and cache rules, and shares recovery terminology and package-manager guidance with `restore`. `retirement_reports` validates schema and totals, renders inert paths and commits per-file outputs with a completion record. `verify` binds the pair back to the selected root and observes listed directory entries without a full scan.

Legacy discovery reuses the no-follow metadata enumerator for sizing and topology. It retains its classifications and candidate content hash format. `plans` can consume a prior compatible scan and retains schema-2 validation. The standalone restoration command retains monorepo guidance. Legacy report types stay distinct from retirement.

The Agent Skill delegates to one local `retire` call and stops. The installed package has a plain compatibility refusal for legacy apply. Historical deletion and approval prototypes live in the disposable test harness.
