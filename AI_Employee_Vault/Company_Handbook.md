---
last_updated: 2026-02-10
version: 0.1.0
---

# Company Handbook - Rules of Engagement

## General Rules
1. Always log every action taken to `/Logs/`
2. Never delete original files - move them to `/Done/` after processing
3. When in doubt, create an approval request in `/Pending_Approval/`

## Communication Rules
1. Always be polite and professional in all communications
2. Never share confidential information externally
3. Respond to urgent messages within 1 hour during business hours

## Financial Rules
1. Flag any payment over $100 for human approval
2. Never auto-approve payments to new payees
3. Log all financial transactions with full details

## File Processing Rules
1. Files dropped in `/Inbox/` should be triaged to `/Needs_Action/`
2. Each action file must have YAML frontmatter with: type, priority, status, created
3. Completed tasks move to `/Done/` with a completion timestamp

## Priority Levels
- **critical**: Requires immediate attention (financial, security)
- **high**: Should be processed within 1 hour
- **medium**: Process within same business day
- **low**: Process when capacity allows

## Social Media Rules
1. All social media posts must go through the approval workflow (Pending_Approval → Approved)
2. Never post without human approval — even scheduled drafts are drafts
3. Keep posts professional and aligned with Business_Goals.md
4. Platform limits: Twitter/X max 280 characters, others max 1300 characters
5. Max 3 hashtags per post across all platforms
6. Never share confidential business data in social media posts
7. Cross-platform posting schedule: LinkedIn (Monday), Facebook (Tuesday), Twitter (Wednesday), Instagram (Thursday)

## Accounting Rules
1. All invoices and payments are managed through Odoo (cloud-hosted)
2. Flag any payment over $100 for human approval
3. Never auto-approve payments to new payees
4. Log all financial transactions with full details
5. Weekly audit generates KPI dashboard and CEO briefing every Sunday
6. DRY_RUN mode must be respected — no real transactions when DRY_RUN=true

## Approval Workflow
1. Sensitive actions create a file in `/Pending_Approval/`
2. Actions requiring approval: sending emails, social media posts, payments over $100, new vendor payments
3. Human moves file to `/Approved/` to authorize
4. Human moves file to `/Rejected/` to deny
5. Approved actions are executed and logged
6. Orchestrator automatically picks up approved/rejected files
