# Railway Deployment Checklist

## Pre-deployment (Local)
- [ ] All files created and tested
- [ ] .gitignore configured
- [ ] README.md updated
- [ ] Environment variables documented

## GitHub Setup
- [ ] Create new repository: hokkaido-ferry-forecast
- [ ] Push all files to main branch
- [ ] Verify repository is public or accessible to Railway

## Railway Deployment  
- [ ] Log into Railway with GitHub account
- [ ] Click "Deploy from GitHub repo"
- [ ] Select hokkaido-ferry-forecast repository
- [ ] Confirm automatic deployment starts

## Environment Configuration
- [ ] Set FLIGHTAWARE_API_KEY in Railway dashboard
- [ ] Verify DATABASE_URL is auto-configured
- [ ] Check deployment logs for success

## Cron Job Setup
- [ ] Go to Railway project dashboard
- [ ] Navigate to "Cron" or "Deployments" section
- [ ] Add new cron job:
  - Command: `python cloud_ferry_collector.py`
  - Schedule: `0 6 * * *` (daily 6 AM JST)

## Testing & Verification
- [ ] Manual trigger test collection
- [ ] Check database for new records
- [ ] Verify logs show successful execution
- [ ] Confirm next scheduled run is set

## Monitoring Setup
- [ ] Bookmark Railway project dashboard
- [ ] Set up log monitoring
- [ ] Document access for future maintenance

## Completion
- [ ] System collecting data automatically
- [ ] No longer dependent on local PC
- [ ] 24/7 operation confirmed

Estimated completion time: 15-20 minutes
