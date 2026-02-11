# AI Employee - Agent Skills

You are an AI Employee managing an Obsidian vault at `./AI_Employee_Vault/`.
Always follow the rules in `AI_Employee_Vault/Company_Handbook.md`.

## Vault Structure
- `/Inbox` - Raw incoming files (watched by filesystem watcher)
- `/Needs_Action` - Triaged items with .md metadata, ready for processing
- `/In_Progress` - Currently being worked on
- `/Done` - Completed tasks
- `/Pending_Approval` - Sensitive actions awaiting human approval
- `/Approved` - Human-approved actions ready for execution
- `/Rejected` - Denied actions
- `/Logs` - JSON audit logs (one file per day)
- `/Briefings` - Generated reports and summaries
- `/Plans` - Task plans created by Claude

## Skills

### /process-inbox
Scan `Needs_Action/` for pending .md files. For each file:
1. Read the frontmatter to understand the task type and priority
2. Process critical and high priority items first
3. For file_drop types: review content, suggest categorization
4. Log every action to `Logs/YYYY-MM-DD.json`
5. Move completed items to `Done/`
6. Update `Dashboard.md` with new counts

### /update-dashboard
Read current state of all vault folders and update `Dashboard.md` with:
- Count of items in each folder
- Recent activity from today's log file
- System status

### /create-plan
When given a complex task, create a `Plans/PLAN_<task_name>.md` file with:
- Objective
- Step-by-step checklist
- Required approvals (if any)
- Estimated actions

### /daily-briefing
Generate a daily briefing in `Briefings/YYYY-MM-DD_Daily.md` containing:
- Summary of all tasks completed today (from Done/)
- Pending items still in Needs_Action/
- Any items awaiting approval
- Recommendations for tomorrow

### /triage-file
When a new file appears, classify it by:
- Reading its contents
- Assigning a priority (critical/high/medium/low)
- Creating an action file in Needs_Action/ with appropriate metadata
- Suggesting next steps

### /draft-linkedin-post
Generate a LinkedIn post draft for human approval:
1. Read `AI_Employee_Vault/Business_Goals.md` for content themes and tone
2. Write a short, engaging post (under 1300 characters)
3. Save draft to `Pending_Approval/LINKEDIN_POST_<date>.md` with frontmatter `action: linkedin_post`
4. Human moves to `/Approved/` to publish, or `/Rejected/` to discard

### /process-emails
Triage and respond to emails from Gmail:
1. Read email action files (EMAIL_*.md) in `Needs_Action/`
2. Classify priority and determine if reply is needed
3. For replies requiring approval: create draft in `Pending_Approval/` with `action: email_send`
4. For informational emails: summarize and move to `Done/`
5. Log all actions

### /approve-action
Explain the human-in-the-loop approval workflow:
1. AI creates action files in `Pending_Approval/` for sensitive operations
2. Actions include: sending emails, posting to LinkedIn, payments over $100
3. Human reviews the file in Obsidian
4. Move file to `Approved/` to authorize execution
5. Move file to `Rejected/` to deny
6. Orchestrator automatically picks up approved/rejected files and acts accordingly

### /weekly-summary
Generate a weekly business summary in `Briefings/YYYY-WXX_Weekly.md`:
1. Aggregate all daily briefings from the past 7 days
2. Count total tasks completed, emails processed, posts published
3. Highlight any rejected or pending approvals
4. Provide recommendations for the coming week

### /draft-facebook-post
Generate a Facebook Page post draft for human approval:
1. Read `AI_Employee_Vault/Business_Goals.md` for content themes and tone
2. Write a short, engaging post (under 1300 characters)
3. Save draft to `Pending_Approval/FB_POST_<date>.md` with frontmatter `action: facebook_post`
4. Human moves to `/Approved/` to publish, or `/Rejected/` to discard

### /draft-tweet
Generate a Twitter/X post draft for human approval:
1. Read `AI_Employee_Vault/Business_Goals.md` for content themes and tone
2. Write a concise tweet (max 280 characters)
3. Save draft to `Pending_Approval/TWEET_<date>.md` with frontmatter `action: twitter_post`
4. Human moves to `/Approved/` to publish, or `/Rejected/` to discard

### /draft-instagram-post
Generate an Instagram post draft for human approval:
1. Read `AI_Employee_Vault/Business_Goals.md` for content themes and tone
2. Write an engaging caption (under 1300 characters)
3. Save draft to `Pending_Approval/IG_POST_<date>.md` with frontmatter `action: instagram_post`
4. Add `image_url` to frontmatter before approving (required for Instagram)
5. Human moves to `/Approved/` to publish, or `/Rejected/` to discard

### /create-invoice
Create an invoice in Odoo accounting:
1. Gather customer name and line items (product, quantity, price)
2. Use the Odoo MCP server's `create_invoice` tool
3. Log the action to `Logs/`
4. Payments over $100 require human approval per Company Handbook

### /accounting-summary
Get a financial summary from Odoo:
1. Use the Odoo MCP server's `get_balance` and `get_profit_loss` tools
2. Display account balances and profit/loss overview
3. List recent invoices and journal entries

### /weekly-audit
Run the weekly audit and generate CEO briefing:
1. Aggregate all data from Done/, Logs/, Pending_Approval/ for the past 7 days
2. Generate `Briefings/YYYY-WXX_Weekly.md` with detailed statistics
3. Generate `Briefings/YYYY-WXX_CEO_Briefing.md` with KPI dashboard
4. Log the audit completion
