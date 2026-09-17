# Run Order

1. R0 Inventory + Ownership Manifest
2. R1 Backend Print Ownership
3. R2 Backend Learn Ownership
4. R3 Curriculum + Platform Extraction
5. R4 Prompts/Writers/Validators/Resources
6. R5 Frontend Feature Ownership
7. R6 Physical Package Alignment
8. R7 Architecture Guards + Compatibility Cleanup
9. R8 Full Verification

Use one Cursor run per phase.

At the start of every phase, Cursor must reread the permanent contracts and the current phase prompt rather than relying on chat memory.
