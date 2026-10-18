You’re absolutely right to think “affiliate” for DocFoundry – this is exactly the kind of product that can spread via automation nerds, devs, and SaaS people recommending it.

Below is a **business requirements pack** for the affiliate feature _plus_ a concrete **action plan + promotion channels** so you can build and launch it, not just think about it.

---

## 1. Product Vision for the Affiliate Program

**Goal:**

Turn DocFoundry into a “money machine” for power users, agencies, and content creators who send you customers. The affiliate program must feel:

- **Developer/automation-first** (API focus, webhooks, clear tracking)
- **Simple, transparent, and recurring** (recurring rev share, clear dashboards)
- **Easy to promote** (nice landing page, copy, premade content)

**Primary KPIs:**

- % of new MRR from affiliate channel
- Number of active affiliates (sent ≥1 customer in last 90 days)
- Time to first conversion per affiliate
- Churn rate of affiliate-referred customers

---

## 2. Actors & User Personas

1. **Affiliate (Partner)**
   - Freelance dev, automation consultant, SaaS founder, agency, YouTuber, blogger, etc.
   - Wants recurring revenue for recommending a tool they already use.
2. **Merchant (You) – DocFoundry Admin**
   - Needs to create offers, manage affiliates, track performance, and handle payouts.
3. **Referred Customer**
   - Signs up via affiliate link or coupon.
   - Uses DocFoundry (trial → paid).

---

## 3. High-Level Flows

1. **Affiliate Onboarding**
   - Visit “/partners” landing page → Apply → Get approved → Access dashboard.
2. **Link & Offer Management**
   - Affiliate grabs unique link (and optionally coupon) for a specific plan.
3. **Attribution**
   - Visitor clicks affiliate link → tracking cookie/session + optional URL params.
   - If they sign up within X days, the affiliate is credited.
4. **Billing & Commissions**
   - Customer pays subscription → commission is calculated → added to affiliate balance.
5. **Payouts**
   - Once threshold is reached & hold period passes → affiliate requests payout → admin approves → paid via PayPal/Wise/etc.
6. **Analytics & Optimization**
   - Affiliates see dashboards.
   - Admin sees top affiliates, ROI per campaign, fraud flags.

---

## 4. Functional Requirements (What to Build)

### 4.1 Affiliate Onboarding & Management

**FR-1: Partner Landing Page**

- Public page `/partners` describing:
  - Who this is for (devs, automators, SaaS builders, agencies).
  - Commission model (e.g. **30% recurring for 12 months** ).
  - Example earnings.
  - Signup CTA.

**FR-2: Affiliate Signup**

- Affiliate signs up with:
  - Name, email, company/brand.
  - Website / social profiles.
  - Intended audience and promotion methods (checkboxes: blog, YouTube, automation setups, client work, etc.).
- Option: allow sign-in via Google/GitHub for dev vibe.

**FR-3: Affiliate Approval Workflow**

- Statuses: `pending`, `approved`, `rejected`, `blocked`.
- Admin can:
  - View applications.
  - Approve/reject manually.
  - Add notes.
- Optional later: auto-approve based on simple rules (e.g. company email or domain).

**FR-4: Affiliate Profile**

- Editable fields:
  - Display name (used in links).
  - Payment details (PayPal email, Wise, bank IBAN).
  - Preferred currency (if you support multi-currency).
  - Tax details (country, VAT ID if relevant).

---

### 4.2 Tracking & Attribution

**FR-5: Unique Affiliate Links**

- Each affiliate gets an ID / slug: e.g. `?aff=alkis42` or `/r/alkis42`.
- Ability to generate **multiple links** per affiliate for different campaigns:
  - `link_id` for A/B tests (e.g. `?aff=alkis42&cid=youtube-review`).

**FR-6: Cookie / Session Attribution**

- When a user clicks a link:
  - Set a cookie with affiliate ID + campaign ID.
  - Attribution window configurable (e.g. 60–90 days).
  - If user later signs up, affiliate is linked.
- If user clears cookies but signs up with **affiliate coupon** , coupon overrides.

**FR-7: Attribution Priority & Rules**

- If multiple links clicked:
  - Rule: **last click wins** (default) or **first click wins** – define explicitly.
- If customer is already referred by another affiliate:
  - Rule: keep original affiliate for lifetime or until manual override.

**FR-8: Coupon-Based Attribution (Optional but Powerful)**

- Admin can create coupons tied to an affiliate.
- Customer enters coupon at checkout:
  - Coupon registers immediate affiliate attribution (even without prior link).
- Good for offline / 1:1 consulting / webinars.

---

### 4.3 Offers, Plans & Commission Logic

**FR-9: Commission Plans**

- Ability to define **commission plans** :
  - e.g. “Standard”: 30% recurring for 12 months.
  - “VIP”: 40% recurring for 24 months (for top affiliates).
- Parameters per plan:
  - % of net revenue.
  - Duration (months) from customer’s first payment.
  - Eligible product plans (Standard, Pro, Enterprise).
  - One-time vs recurring.

**FR-10: Plan Assignment**

- Each affiliate is assigned to a commission plan.
- Admin can override on affiliate level.

**FR-11: Commission Events**

- Commission is created on:
  - New subscription.
  - Renewal.
  - Upgrades.
- Commission is **cancelled or reversed** on:
  - Refunds.
  - Chargebacks.
  - Cancellation before trial end.

**FR-12: Minimum Payout Threshold & Hold Period**

- Settings:
  - Minimum payout amount (e.g. €50).
  - Hold period (e.g. 30 days after charge to cover refunds).
- Only “cleared” commissions count towards payable balance.

---

### 4.4 Affiliate Dashboard (Portal)

**FR-13: Overview Page**

- Lifetime earnings.
- Pending / cleared / paid balance.
- Number of referred leads.
- Number of paying customers.
- MRR/ARR generated.

**FR-14: Links & Assets**

- List of affiliate links with:
  - Destination URL (homepage, pricing, docs, specific feature pages).
  - Clicks, signups, conversions per link.
- Copy-paste blocks:
  - Simple URLs.
  - UTM-tagged URLs for GA.
- Media kit:
  - Logos.
  - Product screenshots.
  - Example text snippets (email, tweets, LinkedIn, etc.).

**FR-15: Detailed Reports**

- Table of **referred customers** (privacy-aware):
  - Obfuscated identifiers (e.g. buyer@\*\*\*\*.com) if needed.
  - Plan, status (trial/paying), signup date.
- Table of **commissions** :
  - Date, customer, event type, amount, currency, status (pending/cleared/paid/reversed).

**FR-16: Payout Requests**

- Affiliates can:
  - See current payable balance.
  - Request payout (if ≥ threshold).
- Admin sees payout requests with:
  - Affiliate details.
  - Amount.
  - Payment method.

---

### 4.5 Admin Backoffice

**FR-17: Affiliate Directory**

- List of all affiliates:
  - Filters by status, country, performance.
  - Sort by MRR generated, total earnings.

**FR-18: Commission & Customer View**

- View commissions by:
  - Date.
  - Affiliate.
  - Customer.
  - Subscription.
- Manual adjustment:
  - Add/remove/modify commissions.
  - Reason log.

**FR-19: Payout Management**

- View payout requests and history.
- Mark payouts as:
  - Approved → Paid.
  - Rejected (with reason).
- Export CSV for accounting.

**FR-20: Fraud & Abuse Controls**

- Alerts when:
  - Same IP creating multiple referred signups.
  - Very high refund rate for an affiliate.
  - Suspicious credit cards across affiliate referrals.
- Ability to:
  - Block affiliate.
  - Freeze unpaid commissions.

---

### 4.6 Non-Functional Requirements

- **Security:**
  - Only affiliate can see their own stats.
  - Admin-only endpoints for commission modifications.
- **Auditability:**
  - Full log of who changed what (admin side).
- **Scalability:**
  - Should handle at least thousands of affiliates and tens of thousands of referred customers without meltdown.
- **APIs/Webhooks (Dev-First):**
  - Webhooks for:
    - New affiliate approved.
    - New referred signup.
    - New commission created.
  - Public API (later):
    - Affiliates can pull their stats into their own dashboards.

---

## 5. Data Model (High-Level)

Just to get you started:

- `affiliates`
  - id
  - user_id (FK to your users table)
  - slug (for link)
  - status
  - commission_plan_id
  - payment_method_type / payment_details (encrypted)
  - country, tax_id
  - created_at, updated_at
- `commission_plans`
  - id
  - name
  - percentage
  - duration_months
  - is_recurring
  - allowed_plans (jsonb)
- `affiliate_links`
  - id
  - affiliate_id
  - slug / code
  - destination_url
  - campaign_id (optional)
  - created_at
- `affiliate_clicks`
  - id
  - affiliate_link_id
  - ip_hash
  - user_agent_hash
  - timestamp
  - referrer
- `affiliate_attributions`
  - id
  - affiliate_id
  - affiliate_link_id (nullable)
  - customer_id
  - attribution_source (link / coupon)
  - first_attributed_at
  - last_attributed_at
- `commissions`
  - id
  - affiliate_id
  - customer_id
  - subscription_id
  - event_type (initial, renewal, upgrade, etc.)
  - amount
  - currency
  - status (pending, cleared, reversed, paid)
  - event_date
  - cleared_at (nullable)
  - payout_id (nullable)
- `payouts`
  - id
  - affiliate_id
  - amount
  - currency
  - status (requested, approved, paid, rejected)
  - requested_at
  - processed_at
  - notes

---

## 6. Phased Implementation (MVP → v2)

### MVP (Ship This First)

- Single commission plan (e.g. 30% recurring for 12 months).
- Manual affiliate approval.
- Simple link-based attribution (cookie 60 days).
- Simple dashboard for affiliates:
  - clicks, signups, paying customers, total earned.
- Manual payout process (you export CSV + pay via Wise/PayPal).
- Basic fraud rules.

### v2 Enhancements

- Coupon-based attribution.
- Multiple commission plans (VIP tiers).
- Multi-link per affiliate with campaign stats.
- Webhooks + public API.
- Deeper fraud detection and automated flags.
- Multi-currency support, if needed.

---

## 7. Actions to Do & Where to Promote

Now the “where the hell do I find affiliates” part.

### 7.1 Positioning for Affiliates

Your message to potential partners:

> “Recommend DocFoundry to your audience/clients and earn recurring revenue every month, for every account you bring in. We handle the OCR + data extraction mess, you look like a hero.”

Make it clear:

- Recurring commission.
- Dev/automation-friendly API.
- Use-cases: invoices → JSON, logistics documents → CSV, KYC docs → structured data, etc.

---

### 7.2 Target Affiliate Types & Channels

**1. Automation & No-Code Creators**

- People creating tutorials on:
  - Make.com
  - n8n
  - Zapier
  - Airtable
  - Notion + automation
- Where:
  - YouTube search “invoice OCR automation”
  - Reddit communities: /r/NoCode, /r/automation
  - Discords for Make/n8n

**2. SaaS & Indie Hacker Crowd**

- Indie SaaS builders that need document ingestion but don’t want to build OCR.
- Where:
  - Indie Hackers.
  - Product Hunt makers’ groups.
  - Twitter/X dev accounts.
  - /r/SaaS, /r/startups.

**3. Accounting / Bookkeeping / ERP Integrators**

- Small firms that do bookkeeping and want to automate invoice entry.
- Where:
  - LinkedIn search: “Xero integrator”, “QuickBooks automation”, “SAP consultant”.
  - Local FB groups for accountants & bookkeepers (global + Greek).

**4. Agencies & Consultants**

- Digital agencies doing:
  - Process automation.
  - Custom internal tools.
- Where:
  - Clutch, Upwork, Fiverr top-rated automation/AI freelancers.
  - LinkedIn search filters: “automation consultant”, “AI consultant”, “workflow automation”.

**5. Content Creators in AI/Dev Tools**

- YouTubers / bloggers who review dev tools, AI APIs, OCR solutions.
- Offer them:
  - Free access to DocFoundry.
  - Affiliate rev share.
  - Co-created tutorial content.

---

### 7.3 Concrete Action Plan

#### Phase 1 – Internal Prep (1–2 weeks)

1. **Implement MVP Affiliate System** (as outlined above).
2. Create:
   - `/partners` landing page.
   - Simple docs page: “How the affiliate program works”.
   - Media kit zip (logo, screenshots, short copy).
3. Decide:
   - Commission % and duration.
   - Payout methods & threshold.

#### Phase 2 – Low-Hanging Fruit

4. **Existing Network**
   - DM people you already know in:
     - Dev / SaaS / automation.
   - Offer:
     - Early affiliate rate (e.g. 40% for first 3 months after launch).
5. **Add to Product UI**
   - In DocFoundry dashboard:
     - Banner: “Earn by recommending DocFoundry – join the partner program”.
   - Email existing users:
     - “Do you want to earn recurring revenue recommending us?”

#### Phase 3 – Outreach & Partnerships

6. **Systematic Outreach**
   - Build a simple Google Sheet:
     - Columns: Name, Platform, URL, Niche, Email/DM, Status.
   - Each day:
     - Contact 5–10 potential affiliates (small but consistent).
7. **Offer Value**
   - For creators:
     - Custom demo environment.
     - Ability to co-brand a “DocFoundry automation pack” that they give to their audience.
   - For agencies:
     - Internal-use license discount + affiliate rev share.

#### Phase 4 – Scale & Optimize

8. **Public Launch**
   - Announce affiliate program on:
     - Product Hunt (if/when you launch DocFoundry there).
     - Indie Hackers.
     - LinkedIn posts.
     - Reddit (where allowed, in value-add form).
9. **Create Playbooks**
   - “How to earn $500/month promoting DocFoundry with Make.com.”
   - “How agencies can charge +€500/month to clients using DocFoundry.”
10. **Bounties and Challenges**
    - Example:
      - “First affiliate to reach 10 paying customers gets +€200 bonus.”
      - Quarterly leaderboard with small prizes.

---

## 8. What You Can Implement Right Now

If you want a super short dev starting point:

- Add:
  - `affiliates`, `commission_plans`, `affiliate_links`, `commissions`, `payouts` tables.
- Expose:
  - `/api/affiliates/me` (dashboard stats).
  - `/api/affiliates/links` (CRUD for links).
  - `/api/affiliates/payout-requests` (create/list).
- Integrate:
  - In your billing webhook (Stripe/whatever), create commissions when invoices are paid and `customer` is linked to `affiliate_attributions`.

If you want, next step I can draft:

- The exact **API design** (routes, request/response JSON).
- Or the **/partners landing page copy** geared to these personas.
