Below are all three deliverables, clean and ready to use.

---

# ✅ 1. Commission Plan Explanation (for your Pricing Page)

Use this as a small section near the bottom of your pricing page, or as a banner next to the plans.

---

## **Partner Program – Earn Recurring Revenue**

If you help others automate document processing, you can earn money by recommending DocFoundry.app.

**💸 Commission Structure**

- **20% recurring commission** for **12 months** on every customer you refer
- Earn from **initial subscription + renewals + upgrades**
- Bonus: Top-performing partners unlock **30% VIP commissions**

**🎯 Who can join?**

Developers, automation specialists (Make.com, n8n, Zapier), agencies, bookkeepers, SaaS creators, and content creators.

**🌍 Payouts**

Paid via PayPal or Wise once your balance reaches €50.

→ **Learn more & join the Partner Program**

---

# ✅ 2. Affiliate Terms (Legal-Style, ~1 page)

This is formatted as a clean terms-of-service style document.

It’s not legally binding in its current state; you should have a lawyer finalize it — but this is perfect for your SaaS.

---

# **DocFoundry.app Affiliate Program Terms**

**Last updated:** [Insert date]

These Affiliate Program Terms ("Terms") govern your participation in the DocFoundry.app Partner Program ("Program"). By joining the Program, you agree to be bound by these Terms.

---

## 1. Eligibility

To participate, you must:

- Be at least 18 years old
- Provide accurate account and payout information
- Promote DocFoundry in a lawful and ethical manner

DocFoundry.app may approve, reject, or remove any affiliate at its discretion.

---

## 2. Affiliate Account

After approval, you will receive access to the affiliate dashboard, unique tracking links, and promotional materials.

You are responsible for safeguarding your login credentials.

---

## 3. Commissions

### 3.1. Standard Commission

Affiliates earn **20% recurring commission for 12 months** on subscription payments made by referred customers.

### 3.2. VIP / Tiered Commissions

DocFoundry.app may grant enhanced commission rates (such as 30%) to high-performing affiliates.

### 3.3. Commission Qualification

Commissions are earned only when:

- The customer signs up through your tracked link or your associated coupon code
- The customer remains in good standing
- The customer’s payment is successfully processed and not refunded or disputed

### 3.4. Exclusions

Commissions are **not** earned on:

- Internal accounts created by the affiliate
- Fraudulent signups
- Chargebacks, refunds, or cancelled payments
- Self-referrals or signups created through incentives prohibited by these Terms

DocFoundry.app reserves the right to reverse commissions in such cases.

---

## 4. Attribution

A referral is attributed through:

- Your unique tracking link (last-click attribution), or
- An affiliate coupon code entered during checkout

Attribution lasts for the defined cookie window unless otherwise stated.

---

## 5. Payouts

### 5.1. Methods

Payouts are currently available via **PayPal** or **Wise** .

Affiliates must provide valid payout information.

### 5.2. Threshold & Schedule

- Minimum payout: **€50**
- Payouts are processed upon request
- Commissions may be held for a verification period before being released

DocFoundry.app may require additional identity or tax information before payouts.

---

## 6. Promotional Rules

Affiliates may promote DocFoundry through:

- Content, tutorials, videos, blogs, social media
- Email newsletters
- Client recommendations
- Automation / workflow guides

Prohibited promotion methods:

- Spam or unsolicited bulk messaging
- Misleading statements about features, pricing, or results
- Use of paid ads bidding on DocFoundry’s brand name
- Use of cookie stuffing or deceptive redirects
- Any illegal, unethical, or fraudulent behavior

Violation may result in removal from the Program and forfeiture of unpaid commissions.

---

## 7. Use of Branding

Affiliates may use approved DocFoundry.app logos and assets provided in the media kit.

Do not modify the logo or imply official partnership beyond affiliate status.

---

## 8. Termination

DocFoundry.app may terminate or suspend your affiliate account at any time for:

- Violation of these Terms
- Fraudulent or suspicious activity
- Harm to DocFoundry’s reputation

Upon termination, unpaid commissions may be forfeited.

Affiliates may leave the Program at any time by contacting support.

---

## 9. Changes to the Program

DocFoundry.app may modify or discontinue the Program, including commission rates, at any time.

Changes will not retroactively affect commissions already earned.

---

## 10. Limitation of Liability

DocFoundry.app is not liable for indirect, incidental, or consequential damages arising from participation in the Program.

---

## 11. Governing Law

These Terms will be governed by the laws of [Your Jurisdiction], without regard to conflict-of-laws principles.

---

If you have questions regarding the Affiliate Program, contact:

**[support@docfoundry.app](mailto:support@docfoundry.app)**

---

# ✅ 3. Figma Layout for the Affiliate Dashboard (Blueprint)

Below is a **Figma-ready layout spec** you can paste into your design tool.

It includes components, sections, spacing, structure — everything the designer or dev engine needs.

---

# **Affiliate Dashboard – Figma Layout Specification**

## **Page: Affiliate Dashboard**

### Structure:

```
Header
 ├─ Logo (small)
 ├─ “Affiliate Dashboard”
 └─ Profile menu (avatar, dropdown)

Main Content
 ├─ Overview Widgets (4 cards)
 ├─ Referral Links
 ├─ Commissions Table
 ├─ Referred Customers Table
 ├─ Payouts Section
 └─ Media Kit Section
```

---

## **1. Top Bar (Header)**

Height: 64px

Background: White (or dark mode equivalent)

Layout:

- Left: DocFoundry logo (24px height), page title “Affiliate Dashboard”
- Right: User avatar (circle), dropdown menu

---

## **2. Overview Widgets (4 Stats Cards)**

### Grid:

- 4 columns on desktop
- 2 columns tablet
- 1 column mobile
- Gap: 20px

### Cards (identical structure):

- Card size: 260–300px wide
- Shadow: subtle (2–4dp)
- Border radius: 12px
- Padding: 20px

### Widgets:

1. **Total Earnings**
   - Big number (€)
   - Subtext: “Lifetime commissions earned”
2. **Pending Balance**
   - Big number
   - Subtext: “Awaiting clearance”
3. **Cleared & Payable**
   - Big number
   - “Available to request payout”
4. **Referred Customers**
   - Big number
   - “Paying customers this month”

Icon: optional (top-right corner, 24px)

---

## **3. Referral Links Section**

### Title:

**Your Affiliate Links**

### Layout:

- Button “+ Create new link” (right-aligned)
- Table with columns:
  - Link Name
  - Destination URL
  - Clicks
  - Signups
  - Conversions
  - Copy Link (button)
  - Actions (edit/delete)

### Modal: Create Link

Fields:

- Link Name
- Destination URL (dropdown w/ presets: Homepage, Pricing, Features)
- Optional Campaign ID

  Button: “Generate Link”

---

## **4. Commissions Section**

### Title:

**Commissions**

### Table Columns:

- Date
- Customer (masked: e.g., jo••••@example.com)
- Event Type (initial / renewal / upgrade)
- Amount
- Status (pending / cleared / reversed / paid)

  Status chip colors:

- Pending → yellow
- Cleared → green
- Reversed → red
- Paid → blue

---

## **5. Referred Customers Section**

### Title:

**Your Referred Customers**

Columns:

- Customer (masked)
- Plan
- Signup Date
- Status (trial / active / canceled)
- Total billed

---

## **6. Payouts Section**

### Title:

**Payouts**

#### Subcard: Current Payable Balance

- Big amount
- Button: **Request payout**

#### Table: Payout History

Columns:

- Date
- Amount
- Method (PayPal / Wise)
- Status (requested / approved / paid / rejected)

#### Payout Method Modal:

Fields:

- Select Method (dropdown)
- PayPal email
- Wise email / Recipient ID

---

## **7. Media Kit Section**

### Title:

**Promo Materials**

Grid of assets:

- Logo pack (download)
- Product screenshots
- Example email templates
- Example social media copy
- PDF: “How to promote DocFoundry”

Each asset:

- 160×160 card, thumbnail + download button.

---

## **8. Mobile Version Considerations**

- Overview cards → vertical stack
- Tables → collapse into card layouts
- Dropdown menus for filtering
- Fixed “Request payout” button for mobile ease

---

## Want me to also generate:

✅ Tailwind component library for this dashboard

✅ The actual Figma prototype (described layer-by-layer)

✅ The API spec to match the dashboard

Just say the word.
