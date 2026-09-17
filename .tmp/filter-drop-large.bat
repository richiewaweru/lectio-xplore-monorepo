@echo off
set FILTER_BRANCH_SQUELCH_WARNING=1
cd /d C:\Projects\lectio
git filter-branch -f --prune-empty --index-filter "git rm --cached --ignore-unmatch docs/lectio-reliability-health/evidence/p06-validate-after-wire.txt" -- main..HEAD
echo FILTER_EXIT=%ERRORLEVEL%
