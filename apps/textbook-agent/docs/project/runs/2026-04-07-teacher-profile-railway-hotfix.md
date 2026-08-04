# Teacher Profile Railway Hotfix

## Bugfix: new teacher profile inserts fail on Railway

**Classification**: minor  
**Root cause**: the external Railway `student_profiles` table still includes legacy learner columns, and `age`, `education_level`, and `learning_style` were still `NOT NULL` while the app had switched to teacher-only inserts.

### Progress
- [x] Reproduced the failing insert path from production logs
- [x] Identified the hybrid-schema root cause
- [x] Implemented repository compatibility defaults for legacy columns
- [x] Added follow-up migration to relax legacy required constraints
- [ ] Deploy to Railway and verify live

### Validation Evidence
- Pending local validation commands before release

### Railway Schema Check

Run this against the Railway Postgres instance before and after deploy:

```sql
SELECT
  column_name,
  is_nullable,
  data_type
FROM information_schema.columns
WHERE table_name = 'student_profiles'
ORDER BY ordinal_position;
```

Expected after migration `20260407_0009`:
- `age` is nullable
- `education_level` is nullable
- `learning_style` is nullable
- teacher-profile columns from `20260406_0008` are present

### Release Notes
- The API remains teacher-shaped.
- Compatibility defaults live only in backend persistence.
- Renaming `student_profiles` to `teacher_profiles` is intentionally deferred to a later cleanup migration once production writes are stable.
