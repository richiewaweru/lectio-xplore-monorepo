# C03 Report

## Changes

- Learn `node_id` / interaction id = `learn-node:{block.id}:{kind}:{index}` (same as work_order_id)
- `_assert_unique_node_ids` before assemble
- Print shared writer passes `print-node:{planned.id}:{kind}`

## Tests

- `test_c03_unique_node_ids_reject_collisions`
- `test_c03_indexed_ids_are_unique_for_repeated_kinds`

## Gate

PASS — repeated paragraph kinds no longer collide; uniqueness enforced before publish.
