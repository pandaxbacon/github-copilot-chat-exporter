# Codecov Setup Instructions

## Step 1: Sign Up for Codecov

1. Go to https://codecov.io/
2. Click "Sign up with GitHub"
3. Authorize Codecov to access your repositories

## Step 2: Add Repository

1. In Codecov dashboard, click "Add repository"
2. Find `github-copilot-chat-exporter`
3. Click "Activate"

## Step 3: Get Codecov Token

1. In repository settings on Codecov, find your token
2. Copy the token (format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

## Step 4: Add Token to GitHub Secrets

1. Go to https://github.com/pandaxbacon/github-copilot-chat-exporter/settings/secrets/actions
2. Click "New repository secret"
3. Name: `CODECOV_TOKEN`
4. Value: Paste your Codecov token
5. Click "Add secret"

## Step 5: Trigger CI

Once the token is added, the next push or PR will upload coverage to Codecov.

You can manually trigger by:
```bash
git commit --allow-empty -m "ci: Trigger CI"
git push origin main
```

## Verify Setup

After CI runs:
1. Check GitHub Actions: https://github.com/pandaxbacon/github-copilot-chat-exporter/actions
2. Check Codecov: https://codecov.io/gh/pandaxbacon/github-copilot-chat-exporter

The badges in README should update automatically!

