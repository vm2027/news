# GitHub Actions Workflow Troubleshooting Guide

**Use this guide to efficiently report workflow issues and get faster solutions.**

---

## Quick Checklist - Always Provide These First

When reporting a workflow issue, include ALL of the following:

- [ ] **Repository name** (owner/repo format, e.g., vm2027/news)
- [ ] **Workflow file name** (.github/workflows/filename.yml)
- [ ] **When it was supposed to run** (specific time, date, or cron schedule)
- [ ] **Current status** (hasn't run yet, failed, running slow, succeeded)
- [ ] **Any error messages** from the Actions tab
- [ ] **Actions policy status** (enabled or disabled in repo settings)

---

## Common Issues & Solutions

### 1. **Workflow Won't Run - Actions Policy Not Enabled**
**Problem:** Scheduled workflow never triggers even though it's configured correctly.

**Root Cause:** Actions policy is disabled at repository or organization level.

**How to Fix:**
- Go to **Settings → Actions → General**
- Under "Actions permissions," select **"Allow all actions and reusable workflows"** (or your org's preferred policy)
- Verify write permissions are allowed for workflows
- Check organization-level policies if it's an org repo

**Prevention:** Always verify Actions policy is enabled BEFORE investigating workflow configuration.

---

### 2. **Scheduled Workflow Not Triggering**
**Problem:** Cron schedule is correct, but workflow doesn't run at scheduled time.

**Possible Causes:**
- Actions policy disabled (see above)
- Workflow file is not on the default branch (usually `main` or `master`)
- Cron schedule is in UTC - verify timezone expectations
- GitHub Actions might be under maintenance

**How to Check:**
1. Verify workflow file is on your default branch
2. Go to Actions tab → select the workflow → check "Runs" history
3. If no runs exist, it hasn't executed yet
4. Manual trigger: Click **"Run workflow"** button to test immediately

---

### 3. **Workflow Fails After Triggering**
**Problem:** Workflow runs but shows as "failed" in Actions tab.

**How to Debug:**
1. Click on the failed run in the Actions tab
2. Check job logs for error messages
3. Common causes:
   - Missing secrets (e.g., API keys not configured)
   - Missing dependencies or incorrect Python version
   - Write permissions denied (for git push)
   - Third-party actions blocked by policy

---

### 4. **Third-Party Actions Blocked**
**Problem:** Workflow fails with "action not allowed" error.

**How to Fix:**
- Go to **Settings → Actions → General**
- Under "Actions permissions," ensure third-party actions are allowed
- Or add specific actions to allowlist based on your org policy

---

## Workflow Information Template

Use this template when asking for help:

Repository: [owner/repo]Workflow File: .github/workflows/[filename].ymlScheduled For: [time/date or cron expression]Current Status: [running/failed/hasn’t run yet]Actions Policy: [enabled/disabled/need to check]Error Message (if any): [paste error here]

---

## Useful Links

## Here is where I can directly find this Gist: https://gist.github.com/vm2027
## An alternate way is: Profile >> Gist

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Cron Schedule Helper](https://crontab.guru/) - Test cron expressions
- [GitHub Actions Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)

---

## Quick Reference: UTC Times

Your workflow runs at: `0 14 * * *` (2:00 PM UTC)

Common timezone conversions:
- **UTC**: 2:00 PM (14:00)
- **Pacific (PDT)**: 7:00 AM
- **Eastern (EDT)**: 10:00 AM
- **UK (BST)**: 3:00 PM
- **Central Europe (CEST)**: 4:00 PM

---

**Last Updated:** 2026-08-21  
**Relevant Repo:** vm2027/news